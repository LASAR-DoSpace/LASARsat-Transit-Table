import os
import json
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from skyfield.api import load, wgs84, EarthSatellite

columns = [
    "Datum", "Max výška", "Doba nad 10°", "Osvětleno nad 10°", "Vychází", 
    "Dosahuje 10°", "Nejvyšší poloha", "Klesne pod 10°", "Zapadá", 
    "Výška při stínu", "Čas stínu", "Výška Slunce", "Scénář", "Priorita", 
    "Oblačnost", "Nízká", "Střední", "Vysoká"
]

session = requests.Session()


def fetch_tle(sat_id):
    """Fetch latest TLE from CelesTrak for a given NORAD catalog ID."""
    print(f"Fetching TLE for NORAD ID {sat_id} from CelesTrak...")
    url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={sat_id}&FORMAT=TLE"
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    lines = [line.strip() for line in resp.text.strip().splitlines() if line.strip()]
    
    if len(lines) == 3:
        name, line1, line2 = lines[0], lines[1], lines[2]
    elif len(lines) == 2:
        name, line1, line2 = f"NORAD {sat_id}", lines[0], lines[1]
    else:
        raise ValueError(f"Unexpected TLE format returned by CelesTrak:\n{resp.text}")
        
    print(f"Successfully loaded TLE for: {name}")
    return name, line1, line2


def find_passes(sat, eph, ts, loc, max_days=7):
    """
    Compute all passes above 10° where the Sun altitude remains <= -6° (dark/twilight).
    Accurately computes shadow entry/exit and sunlight durations.
    """
    observer = wgs84.latlon(loc['lat'], loc['lng'], elevation_m=loc.get('alt', 0))
    sun = eph['sun']
    earth = eph['earth']
    obs_position = earth + observer

    now_utc = datetime.now(timezone.utc)
    t0 = ts.from_datetime(now_utc)
    t1 = ts.from_datetime(now_utc + timedelta(days=max_days + 1))

    # Find horizon crossings (0° threshold)
    times, events = sat.find_events(observer, t0, t1, altitude_degrees=0.0)

    # Group into complete passes (0 = rise, 1 = culminate, 2 = set)
    raw_passes = []
    current_rise = None
    current_culm = None

    for t_ev, ev_type in zip(times, events):
        if ev_type == 0:
            current_rise = t_ev
            current_culm = None
        elif ev_type == 1 and current_rise is not None:
            current_culm = t_ev
        elif ev_type == 2 and current_rise is not None and current_culm is not None:
            raw_passes.append((current_rise, current_culm, t_ev))
            current_rise = None
            current_culm = None

    passes = []
    cutoff_date = (datetime.now() + timedelta(days=max_days)).date()

    for t0_rise, t_culm, t0_set in raw_passes:
        dt_culm = t_culm.utc_datetime()
        if dt_culm.date() >= cutoff_date:
            continue

        # Check peak altitude
        alt_max = (sat - observer).at(t_culm).altaz()[0].degrees
        if alt_max < 10.0:
            continue

        # Bisect for 10° rising threshold
        ta, tb = t0_rise.tt, t_culm.tt
        for _ in range(15):
            tm = (ta + tb) / 2
            if (sat - observer).at(ts.tt_jd(tm)).altaz()[0].degrees < 10.0:
                ta = tm
            else:
                tb = tm
        t10_rise = ts.tt_jd((ta + tb) / 2)

        # Bisect for 10° setting threshold
        ta, tb = t_culm.tt, t0_set.tt
        for _ in range(15):
            tm = (ta + tb) / 2
            if (sat - observer).at(ts.tt_jd(tm)).altaz()[0].degrees > 10.0:
                ta = tm
            else:
                tb = tm
        t10_set = ts.tt_jd((ta + tb) / 2)

        # Solar altitudes at key moments
        key_times = [t0_rise, t10_rise, t_culm, t10_set, t0_set]
        sun_alts = [
            obs_position.at(t_pt).observe(sun).apparent().altaz()[0].degrees
            for t_pt in key_times
        ]

        # Heavens-Above condition: exclude daytime / civil twilight passes (Sun > -6°)
        if any(s > -6.0 for s in sun_alts):
            continue

        avg_sun_height = f"{np.mean(sun_alts):.1f}°"

        # Shadow analysis: sample pass between rise and set
        sample_step_sec = 2.0
        total_pass_sec = max(int(round((t0_set.tt - t0_rise.tt) * 86400)), 2)
        num_samples = max(int(total_pass_sec // sample_step_sec), 5)
        t_sample_arr = ts.tt_jd(np.linspace(t0_rise.tt, t0_set.tt, num_samples))
        sunlit_samples = sat.at(t_sample_arr).is_sunlit(eph)

        delta_t10_sec = int(round((t10_set.tt - t10_rise.tt) * 86400))
        delta_t10 = f"{delta_t10_sec // 60:02d}:{delta_t10_sec % 60:02d}"

        shadow_height = "-"
        shadow_time = "-"
        delta_t10_sunlight_sec = 0
        classification = "A+B"

        if np.all(sunlit_samples):
            # Satellite is illuminated for the entire pass
            classification = "A"
            delta_t10_sunlight_sec = delta_t10_sec
        elif not np.any(sunlit_samples):
            # Satellite is unlit for the entire pass
            classification = "B"
            shadow_height = "0°"
            shadow_time = t0_rise.utc_strftime("%H:%M:%S")
            delta_t10_sunlight_sec = 0
        else:
            # Shadow entry or shadow exit occurs
            flip_indices = np.where(sunlit_samples[:-1] != sunlit_samples[1:])[0]
            idx = flip_indices[0]
            is_entry = sunlit_samples[idx] and not sunlit_samples[idx + 1]

            # Refine transition timestamp
            ta, tb = t_sample_arr[idx].tt, t_sample_arr[idx + 1].tt
            for _ in range(12):
                tm = (ta + tb) / 2
                in_sun = sat.at(ts.tt_jd(tm)).is_sunlit(eph)
                if in_sun == sunlit_samples[idx]:
                    ta = tm
                else:
                    tb = tm

            t_shadow = ts.tt_jd((ta + tb) / 2)
            shadow_time = t_shadow.utc_strftime("%H:%M:%S")
            sh_alt = (sat - observer).at(t_shadow).altaz()[0].degrees
            shadow_height = f"{round(sh_alt)}°"

            t10_r_tt = t10_rise.tt
            t10_s_tt = t10_set.tt
            t_sh_tt = t_shadow.tt

            if is_entry:
                if t_sh_tt <= t10_r_tt:
                    classification = "B"
                    delta_t10_sunlight_sec = 0
                elif t_sh_tt >= t10_s_tt:
                    classification = "A"
                    delta_t10_sunlight_sec = delta_t10_sec
                else:
                    classification = "A+B"
                    delta_t10_sunlight_sec = int(round((t_sh_tt - t10_r_tt) * 86400))
            else:  # shadow exit
                if t_sh_tt <= t10_r_tt:
                    classification = "A"
                    delta_t10_sunlight_sec = delta_t10_sec
                elif t_sh_tt >= t10_s_tt:
                    classification = "B"
                    delta_t10_sunlight_sec = 0
                else:
                    classification = "A+B"
                    delta_t10_sunlight_sec = int(round((t10_s_tt - t_sh_tt) * 86400))

        delta_t10_sunlight_sec = max(0, min(delta_t10_sunlight_sec, delta_t10_sec))
        delta_t10_sunlight = f"{delta_t10_sunlight_sec // 60:02d}:{delta_t10_sunlight_sec % 60:02d}"

        # Determine priority
        max_height_val = round(alt_max)
        if max_height_val >= 25 and delta_t10_sec >= 300 and classification == "A":
            priority = "1"
        elif (max_height_val >= 20 or delta_t10_sec >= 240) and classification != "B":
            priority = "2"
        elif max_height_val >= 15 or delta_t10_sec >= 240:
            priority = "3"
        else:
            priority = "4"

        date_str = dt_culm.strftime("%d.%m.%Y")
        max_height_str = f"{round(alt_max)}°"
        t0_s = t0_rise.utc_strftime("%H:%M:%S")
        t10_s = t10_rise.utc_strftime("%H:%M:%S")
        t_max = t_culm.utc_strftime("%H:%M:%S")
        t10_e = t10_set.utc_strftime("%H:%M:%S")
        t0_e = t0_set.utc_strftime("%H:%M:%S")

        passes.append([
            date_str, max_height_str, delta_t10, delta_t10_sunlight,
            t0_s, t10_s, t_max, t10_e, t0_e,
            shadow_height, shadow_time, avg_sun_height,
            classification, priority
        ])

    return passes


def fetch_weather(weather_url):
    """Scrapes 7-day hourly forecast from Clear Outside."""
    forecast = {}
    resp = requests.get(weather_url)
    if resp.status_code == 200:
        print("Fetched weather data")
        soup = BeautifulSoup(resp.text, "html.parser")
        fc = soup.find("div", id="forecast")
        if not fc:
            return forecast

        generated_tag = soup.find("h2")
        if not generated_tag or "Generated: " not in generated_tag.get_text():
            return forecast

        generated_text = generated_tag.get_text()
        base_date = datetime.strptime(generated_text.split("Generated: ")[1][:8], "%d/%m/%y")

        for day_index, day in enumerate(fc.find_all("div", class_="fc_day")):
            current_date = base_date + timedelta(days=day_index)
            rating_items = day.select(".fc_hour_ratings li")
            ratings = []
            for li in rating_items:
                classes = li.get("class", [])
                if "fc_bad" in classes:
                    ratings.append("bad")
                elif "fc_ok" in classes:
                    ratings.append("ok")
                elif "fc_good" in classes:
                    ratings.append("good")
                else:
                    ratings.append("")

            cloud_rows = day.select(".fc_detail_row")

            def extract_clouds(label):
                for r in cloud_rows:
                    if label in r.get_text():
                        return [int(li.get_text()) for li in r.select("li") if li.get_text().isdigit()]
                return []

            total = extract_clouds("Total Clouds")
            low = extract_clouds("Low Clouds")
            medium = extract_clouds("Medium Clouds")
            high = extract_clouds("High Clouds")

            data_len = min(len(ratings), len(total), len(low), len(medium), len(high))
            for hour in range(data_len):
                dt = current_date.replace(hour=hour)
                key = dt.strftime("%Y-%m-%d %H:00")
                forecast[key] = {
                    "rating": ratings[hour],
                    "total_clouds": total[hour],
                    "low_clouds": low[hour],
                    "medium_clouds": medium[hour],
                    "high_clouds": high[hour],
                }
    else:
        print("Failed to fetch weather data")

    return forecast


def create_table(raw_passes, forecast):
    """Combines satellite pass geometry with weather data and applies pass IDs."""
    table = []
    for row in raw_passes:
        date_str = row[0]
        time_str = row[6]  # peak altitude time (HH:MM:SS)

        dt = datetime.strptime(f"{date_str} {time_str[:2]}", "%d.%m.%Y %H")
        key = dt.strftime("%Y-%m-%d %H:00")

        row_copy = list(row)
        if key in forecast:
            w = forecast[key]
            row_copy.extend([
                w["total_clouds"],
                w["low_clouds"],
                w["medium_clouds"],
                w["high_clouds"]
            ])
        else:
            row_copy.extend(["", "", "", ""])

        table.append(row_copy)

    counter = {}
    format_table = []
    for row in table:
        dt = datetime.strptime(row[0], "%d.%m.%Y")
        key = dt.strftime("%Y%m%d")

        if key not in counter:
            counter[key] = 0
        counter[key] += 1
        format_table.append([f"{key}--{counter[key]:02d}"] + row[1:])

    return format_table


def write_to_csv(df, csv_path):
    df.to_csv(csv_path, index=False)
    print(f"Saved to {csv_path}")


def write_to_Excel(df, excel_path):
    if df.empty:
        print(f"Skipping Excel export for {excel_path} (DataFrame is empty).")
        return

    writer = pd.ExcelWriter(excel_path, engine='xlsxwriter')
    workbook = writer.book

    df_copy = df.copy()
    df_copy["Výška Slunce"] = (
        df_copy["Výška Slunce"]
        .astype(str)
        .str.replace("°", "")
        .str.replace(",", ".")
        .replace("", "0")
        .astype(float)
    )
    df_copy["Max výška"] = (
        df_copy["Max výška"]
        .astype(str)
        .str.replace("°", "")
        .str.replace(",", ".")
        .astype(float)
    )

    df_copy.to_excel(writer, sheet_name="Přelety", index=False)
    worksheet = writer.sheets["Přelety"]

    header_format = workbook.add_format({
        'bold': True, 'text_wrap': True, 'valign': 'top',
        'fg_color': '#D7E4BC', 'border': 1
    })

    center_fmt = workbook.add_format({'align': 'center', 'valign': 'vcenter'})
    thick_right = workbook.add_format({'right': 2, 'align': 'center', 'valign': 'vcenter'})
    degree_fmt = workbook.add_format({'num_format': '0.0"°"', 'align': 'center', 'valign': 'vcenter'})
    degree_thick_right_fmt = workbook.add_format({'num_format': '0.0"°"', 'right': 2, 'align': 'center', 'valign': 'vcenter'})

    fmt_good = workbook.add_format({"bg_color": "#6AD26A", "font_color": "#333333", "align": "center", "valign": "vcenter"})
    fmt_ok = workbook.add_format({"bg_color": "#F0B070", "font_color": "#333333", "align": "center", "valign": "vcenter"})
    fmt_bad = workbook.add_format({"bg_color": "#F0707F", "font_color": "#333333", "align": "center", "valign": "vcenter"})

    col_widths = {
        0: 11.5,
        1: 11.5, 2: 11.5, 3: 15.8,
        4: 13.5, 5: 13.5, 6: 13.5, 7: 13.5, 8: 13.5,
        9: 12.5, 10: 8,
        11: 12,
        12: 7, 13: 7,
        14: 9, 15: 9, 16: 9, 17: 9
    }

    for i, col in enumerate(df_copy.columns):
        fmt = center_fmt
        if col in ["Max výška", "Výška Slunce"]:
            fmt = degree_fmt
        if i in [0, 3, 8, 10, 11, 13]:
            fmt = degree_thick_right_fmt if col == "Výška Slunce" else thick_right

        worksheet.set_column(i, i, col_widths.get(i, 11.5), fmt)

    idx_sun = df_copy.columns.get_loc("Výška Slunce")

    fmt_astro = workbook.add_format({"bg_color": "#0B1D4D", "font_color": "#FFFFFF", "align": "center", "valign": "vcenter"})
    fmt_astro_twilight = workbook.add_format({"bg_color": "#3A2F6B", "font_color": "#FFFFFF", "align": "center", "valign": "vcenter"})
    fmt_nautical = workbook.add_format({"bg_color": "#E6D690", "font_color": "#000000", "align": "center", "valign": "vcenter"})
    fmt_civil = workbook.add_format({"bg_color": "#F5F5F5", "font_color": "#000000", "align": "center", "valign": "vcenter"})

    worksheet.conditional_format(1, idx_sun, len(df_copy), idx_sun, {
        "type": "cell", "criteria": "<=", "value": -18, "format": fmt_astro
    })
    worksheet.conditional_format(1, idx_sun, len(df_copy), idx_sun, {
        "type": "cell", "criteria": "between", "minimum": -18, "maximum": -12, "format": fmt_astro_twilight
    })
    worksheet.conditional_format(1, idx_sun, len(df_copy), idx_sun, {
        "type": "cell", "criteria": "between", "minimum": -12, "maximum": -6, "format": fmt_nautical
    })
    worksheet.conditional_format(1, idx_sun, len(df_copy), idx_sun, {
        "type": "cell", "criteria": ">", "value": -6, "format": fmt_civil
    })

    fmt_p1 = workbook.add_format({"bg_color": "#63BE7B", "font_color": "#000000", "align": "center", "valign": "vcenter"})
    fmt_p2 = workbook.add_format({"bg_color": "#C6EFCE", "font_color": "#000000", "align": "center", "valign": "vcenter"})
    fmt_p3 = workbook.add_format({"bg_color": "#FFEB9C", "font_color": "#000000", "align": "center", "valign": "vcenter"})
    fmt_p4 = workbook.add_format({"bg_color": "#FFC7CE", "font_color": "#000000", "align": "center", "valign": "vcenter"})

    idx_prio = df_copy.columns.get_loc("Priorita")
    worksheet.conditional_format(1, idx_prio, len(df_copy), idx_prio, {'type': 'cell', 'criteria': '==', 'value': '"1"', 'format': fmt_p1})
    worksheet.conditional_format(1, idx_prio, len(df_copy), idx_prio, {'type': 'cell', 'criteria': '==', 'value': '"2"', 'format': fmt_p2})
    worksheet.conditional_format(1, idx_prio, len(df_copy), idx_prio, {'type': 'cell', 'criteria': '==', 'value': '"3"', 'format': fmt_p3})
    worksheet.conditional_format(1, idx_prio, len(df_copy), idx_prio, {'type': 'cell', 'criteria': '==', 'value': '"4"', 'format': fmt_p4})

    CLOUD_COLORS = {
        0: "#FFFFFF", 5: "#F6F9FC", 10: "#EEF3F9", 15: "#E6EEF7", 20: "#DDE8F4",
        25: "#D4E2F1", 30: "#CCDCEE", 35: "#C4D7EC", 40: "#BBD1E9", 45: "#B2CBE6",
        50: "#AAC5E3", 55: "#A2C0E1", 60: "#99BADE", 65: "#90B4DB", 70: "#88AED8",
        75: "#80A9D6", 80: "#77A3D3", 85: "#6E9DD0", 90: "#6697CD", 95: "#5E92CB", 100: "#558CC8"
    }

    cloud_formats = {
        k: workbook.add_format({"bg_color": v, "font_color": "#333333", "align": "center", "valign": "vcenter"})
        for k, v in CLOUD_COLORS.items()
    }

    for col_name in ["Nízká", "Střední", "Vysoká"]:
        col = df_copy.columns.get_loc(col_name)
        for r in range(len(df_copy)):
            val = df_copy.iloc[r][col_name]
            if val == "" or pd.isna(val):
                continue
            cls = min(100, max(0, int(round((100 - int(val)) / 5) * 5)))
            worksheet.write(r + 1, col, val, cloud_formats[cls])

    idx_total = df_copy.columns.get_loc("Oblačnost")
    for r in range(len(df_copy)):
        date_str = df_copy.iloc[r]["Datum"]
        hour = df_copy.iloc[r]["Nejvyšší poloha"][:2]
        key = datetime.strptime(f"{date_str[:8]} {hour}", "%Y%m%d %H").strftime("%Y-%m-%d %H:00")

        rating = forecast.get(key, {}).get("rating")
        val = df_copy.iloc[r, idx_total]

        if rating == "good":
            worksheet.write(r + 1, idx_total, val, fmt_good)
        elif rating == "ok":
            worksheet.write(r + 1, idx_total, val, fmt_ok)
        elif rating == "bad":
            worksheet.write(r + 1, idx_total, val, fmt_bad)

    fmt_sep = workbook.add_format({'top': 2})
    fmt_sep_right = workbook.add_format({'top': 2, 'right': 2})
    thick_right_cols = [0, 3, 8, 10, 11, 13]

    for col in range(len(df_copy.columns)):
        current_fmt = fmt_sep_right if col in thick_right_cols else fmt_sep
        worksheet.conditional_format(1, col, len(df_copy), col, {
            'type': 'formula',
            'criteria': '=RIGHT($A2,4)="--01"',
            'format': current_fmt
        })

    worksheet.freeze_panes(1, 0)
    for col_num, value in enumerate(df_copy.columns):
        worksheet.write(0, col_num, value, header_format)

    writer.close()
    print(f"Saved to {excel_path}")


if __name__ == "__main__":
    SAT_ID = 62391
    os.makedirs("output", exist_ok=True)

    # Load Skyfield components (caches de421.bsp locally)
    ts = load.timescale()
    eph = load('de421.bsp')

    # Fetch latest TLE from CelesTrak once
    sat_name, line1, line2 = fetch_tle(SAT_ID)
    satellite = EarthSatellite(line1, line2, sat_name, ts)

    with open("locations.json", "r") as f:
        locations = json.load(f)

    for loc in locations:
        print(f"\nProcessing location: {loc['name']}...")
        weather_url = f"https://clearoutside.com/forecast/{loc['lat']:.2f}/{loc['lng']:.2f}?view=midnight"

        raw_passes = find_passes(satellite, eph, ts, loc, max_days=7)
        forecast = fetch_weather(weather_url)

        table = create_table(raw_passes, forecast)
        df = pd.DataFrame(table, columns=columns)

        write_to_csv(df, f"output/{loc['name']}.csv")
        write_to_Excel(df, f"output/{loc['name']}.xlsx")