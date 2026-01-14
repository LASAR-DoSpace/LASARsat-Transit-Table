import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from datetime import datetime,timedelta

url = "https://heavens-above.com/PassSummary.aspx?satid=62391&lat=50.638328&lng=13.846724&loc=HaP+Teplice&alt=275&tz=UCT&showall=t&next=t"
weather_url = "https://clearoutside.com/forecast/50.64/13.85?view=midnight"

event_map = {
    "Rises": "start_0",
    "Reaches altitude 10°": "start_10",
    "Maximum altitude": "max",
    "Drops below altitude 10°": "end_10",
    "Enters shadow": "shadow_entry",
    "Exits shadow": "shadow_exit",
    "Sets": "end_0"
}
columns=[
    "Datum","Max výška","Doba nad 10°","Osvětleno nad 10°","Vychází","Dosahuje 10°","Nejvyšší poloha","Klesne pod 10°","Zapadá","Výška při stínu","Čas stínu","Výška Slunce","Scénář","Priorita", "Oblačnost","Nízká","Střední","Vysoká"]

session = requests.Session()

def get_links():
    links=[]
    tags=[]

    resp = session.get(url)
    print("Fetching links page...")
    if resp.status_code != 200:
        print("Failed to fetch links page")
        return links,tags
    else:
        print("Links page fetched successfully")
        html = resp.text

        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("table.standardTable tr.clickableRow")

        for row in rows:
            a = row.find("a")
            if a and a.get("href"):
                link = "https://heavens-above.com/" + a["href"].lstrip("/")
                links.append(link)
                tags.append(row.find_all("td")[-1].get_text(strip=True))
        
        return links,tags

def pass_page(link,tag):
    req=session.get(link)
    if req.status_code!=200:
        print(f"Failed to fetch pass page: {link}")
        return []
    else:
        html=req.text
    soup = BeautifulSoup(html, "html.parser")

    date_span = soup.find('span', id='ctl00_cph1_lblDate')
    date_text = date_span.get_text().strip() if date_span else ""

    date_obj = datetime.strptime(date_text, "%d %B %Y")
    date = date_obj.strftime("%d.%m.%Y")

    rows = soup.find('table', class_='standardTable').find_all('tr')
    events={}
    SunHeights=[]
    for row in rows[1:]:

        cols=row.find_all('td')
        if not cols: continue

        event_name=cols[0].get_text(strip=True)
        time=cols[1].get_text(strip=True)
        height=cols[2].get_text(strip=True)
        SunHeight=float(cols[6].get_text(strip=True).replace("°","").replace(",","."))
        SunHeights.append(SunHeight)
        if SunHeight>-6:
            return []
        if event_name in event_map:
            key=event_map[event_name]
            if key=="max" and height=="10°":
                events["start_10"]={
                    "time_str":time,
                    "time_obj": datetime.strptime(time, "%H:%M:%S"),
                    "height":height
                }
                events["end_10"]={
                    "time_str":time,
                    "time_obj": datetime.strptime(time, "%H:%M:%S"),
                    "height":height
                }
            events[key]={
                "time_str":time,
                "time_obj": datetime.strptime(time, "%H:%M:%S"),
                "height":height
            }
        else:
            print(f"Unknown event: {event_name}")
    
    def get_val(key, field):
        return events.get(key, {}).get(field, "")
    def get_time_obj(key):
        return events.get(key, {}).get("time_obj", None)
    
    max_height = get_val('max', 'height')
    t0_s = get_val('start_0', 'time_str')
    t10_s = get_val('start_10', 'time_str')
    t10_s_obj = get_time_obj('start_10')
    t_max = get_val('max', 'time_str')
    t_max_obj=get_time_obj('max')
    t10_e = get_val('end_10', 'time_str')
    t10_e_obj = get_time_obj('end_10')
    t0_e = get_val('end_0', 'time_str')

    shadow_height = ""
    shadow_time = ""
    shadow_obj = None

    if 'shadow_entry' in events:
        shadow_height = get_val('shadow_entry', 'height')
        shadow_time = get_val('shadow_entry', 'time_str')
        shadow_obj = get_time_obj('shadow_entry')
    elif 'shadow_exit' in events:
        shadow_height = get_val('shadow_exit', 'height')
        shadow_time = get_val('shadow_exit', 'time_str')
        shadow_obj = get_time_obj('shadow_exit')
    elif tag=='night (unlit)':
        shadow_height="0°"
        shadow_time=t0_s
        shadow_obj=get_time_obj('start_0')
    else: 
        shadow_height="-"
        shadow_time="-"
        shadow_obj=t_max_obj+timedelta(minutes=10)

    def calc_delta(start_key, end_key,in_seconds=False):
        t1 = get_time_obj(start_key)
        t2 = get_time_obj(end_key)
        if t1 and t2:
            diff = t2 - t1
            total_seconds = int(diff.total_seconds())
            if start_key=='start_10' and end_key=='end_10' and total_seconds<0:
                total_seconds+=86400
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            if in_seconds:
                return total_seconds
            else:
                return f"{minutes:02d}:{seconds:02d}"
        return ""

    delta_t10=calc_delta('start_10', 'end_10')
    delta_t10_sunlight="-"
    
    if 'shadow_entry' in events:
        delta_t10_sunlight_seconds=np.minimum(np.maximum(calc_delta('start_10', 'shadow_entry',in_seconds=True),0),calc_delta('start_10', 'end_10',in_seconds=True))
        delta_t10_sunlight=f"{delta_t10_sunlight_seconds//60:02d}:{delta_t10_sunlight_seconds%60:02d}"
    elif 'shadow_exit' in events:
        delta_t10_sunlight_seconds=np.minimum(np.maximum(calc_delta('shadow_exit', 'end_10',in_seconds=True),0),calc_delta('start_10', 'end_10',in_seconds=True))
        delta_t10_sunlight=f"{delta_t10_sunlight_seconds//60:02d}:{delta_t10_sunlight_seconds%60:02d}"
    else:
        delta_t10_sunlight="00:00"

    avg_sun_height=f"{np.mean(SunHeights):.1f}°"


    classification="A+B"

    if 'shadow_entry' in events:
        if shadow_obj<t10_s_obj:
            classification="B"
        elif shadow_obj>t10_e_obj:
            classification="A"
    elif 'shadow_exit' in events:
        if shadow_obj<t10_s_obj:
            classification="A"
        elif shadow_obj>t10_e_obj:
            classification="B"
    elif tag=='night (unlit)':
        classification="B"

    priority=""

    if((int(max_height.replace("°","").replace(",","."))>=25 and calc_delta('start_10', 'end_10',in_seconds=True)>=300) and classification=="A"):
        priority="1"
    elif ((int(max_height.replace("°","").replace(",","."))>=20 or calc_delta('start_10', 'end_10',in_seconds=True)>=240) and classification!="B"):
        priority="2"
    elif ((int(max_height.replace("°","").replace(",","."))>=15 or calc_delta('start_10', 'end_10',in_seconds=True)>=240)):
        priority="3"
    else:
        priority="4"


    return [date,max_height,delta_t10,delta_t10_sunlight,t0_s,t10_s,t_max,t10_e,t0_e,shadow_height,shadow_time,avg_sun_height,classification,priority]

def fetch_weather():
    forecast={}
    req=requests.get(weather_url) 
    if req.status_code==200:
        print("Fetched weather data")
        html=req.text

        soup=BeautifulSoup(html,"html.parser")

        fc = soup.find("div", id="forecast")

        generated_text = soup.find("h2").get_text()

        base_date = datetime.strptime( generated_text.split("Generated: ")[1][:8], "%d/%m/%y" )

        for day_index, day in enumerate(fc.find_all("div", class_="fc_day")): 
            current_date = base_date + timedelta(days=day_index) 

            rating_items = day.select(".fc_hour_ratings li") 

            ratings = [] 
            for li in rating_items: 
                if "fc_bad" in li["class"]: ratings.append("bad") 
                elif "fc_ok" in li["class"]: ratings.append("ok") 
                elif "fc_good" in li["class"]: ratings.append("good") 
            cloud_rows = day.select(".fc_detail_row") 
            def extract_clouds(label): 
                for row in cloud_rows: 
                    if label in row.get_text(): return [int(li.get_text()) for li in row.select("li")]  
                return [] 
            total = extract_clouds("Total Clouds") 
            low = extract_clouds("Low Clouds") 
            medium = extract_clouds("Medium Clouds") 
            high = extract_clouds("High Clouds")
            
            data_len=min([len(ratings),len(total),len(low),len(medium),len(high)])
            for hour in range(data_len):
                dt = current_date.replace(hour=hour) 
                key = dt.strftime("%Y-%m-%d %H:00") 
                forecast[key] = { "rating": ratings[hour], "total_clouds": total[hour], "low_clouds": low[hour], "medium_clouds": medium[hour], "high_clouds": high[hour], } 
    else: 
        print("Failed to fetch weather data")

    return forecast

def create_table(links,tags,forecast):
    table=[[]]
    for link in links:
        row=pass_page(link,tags[links.index(link)])
        if row!=[]:
            if datetime.strptime(row[0], "%d.%m.%Y").date()>=(datetime.now()+timedelta(days=7)).date():
                break
            date_str=row[0]
            time_str=row[6]

            dt = datetime.strptime(f"{date_str} {time_str[:2]}","%d.%m.%Y %H") 
            key = dt.strftime("%Y-%m-%d %H:00")

            if key in forecast:
                w = forecast[key]
                row.extend([
                    w["total_clouds"],
                    w["low_clouds"],
                    w["medium_clouds"],
                    w["high_clouds"]
                ])
            else:
                row.extend(["", "", "", ""])

            table.append(row)

    counter={}
    format_table=[]

    for row in table[1:]:
        dt=datetime.strptime(row[0],"%d.%m.%Y")
        key=dt.strftime("%Y%m%d")

        if key not in counter:
            counter[key]=0
        counter[key]+=1
        format_table.append([f"{key}--{counter[key]:02d}"]+row[1:])

    return format_table

def write_to_csv(df):
    df.to_csv("Prelety.csv")
    print("Saved to Prelety.csv")

def write_to_Excel(df):
    writer = pd.ExcelWriter("Prelety.xlsx", engine='xlsxwriter')
    workbook = writer.book

    df["Výška Slunce"] = df["Výška Slunce"].astype(str).str.replace("°", "").str.replace(",", ".").replace("", "0").astype(float)

    df["Max výška"] = df["Max výška"].astype(str).str.replace("°", "").str.replace(",", ".").astype(float)

    df.to_excel(writer, sheet_name="Přelety", index=False)
    worksheet = writer.sheets["Přelety"]

    header_format = workbook.add_format({
        'bold': True, 'text_wrap': True, 'valign': 'top',
        'fg_color': '#D7E4BC', 'border': 1
    })

    center_fmt = workbook.add_format({'align': 'center', 'valign': 'vcenter'})
    thick_right = workbook.add_format({'right': 2, 'align': 'center', 'valign': 'vcenter'})

    degree_fmt = workbook.add_format({'num_format': '0.0"°"', 'align': 'center', 'valign': 'vcenter'})

    degree_thick_right_fmt = workbook.add_format({'num_format': '0.0"°"', 'right': 2,'align': 'center', 'valign': 'vcenter'})

    fmt_good = workbook.add_format({"bg_color": "#6AD26A", "font_color": "#333333","align": "center", "valign": "vcenter"})
    fmt_ok = workbook.add_format({"bg_color": "#F0B070", "font_color": "#333333","align": "center", "valign": "vcenter"})
    fmt_bad = workbook.add_format({"bg_color": "#F0707F", "font_color": "#333333","align": "center", "valign": "vcenter"})

    col_widths = {
        0: 11.5,   
        1: 11.5, 2: 11.5, 3: 15.8,
        4: 13.5, 5: 13.5, 6: 13.5, 7: 13.5, 8: 13.5,
        9: 12.5, 10: 8,
        11: 12,
        12: 7, 13: 7,
        14: 9, 15: 9, 16: 9, 17: 9
    }

    for i, col in enumerate(df.columns):
        fmt = center_fmt

        if col in ["Max výška", "Výška Slunce"]:
            fmt = degree_fmt

        if i in [0, 3, 8, 10, 11,13]:
            fmt = degree_thick_right_fmt if col == "Výška Slunce" else thick_right

        worksheet.set_column(i, i, col_widths.get(i, 11.5), fmt)

    idx_sun = df.columns.get_loc("Výška Slunce")

    fmt_astro = workbook.add_format({
        "bg_color": "#0B1D4D",
        "font_color": "#FFFFFF",
        "align": "center",
        "valign": "vcenter"
    })

    fmt_astro_twilight = workbook.add_format({
        "bg_color": "#3A2F6B",
        "font_color": "#FFFFFF",
        "align": "center",
        "valign": "vcenter"
    })

    fmt_nautical = workbook.add_format({
        "bg_color": "#E6D690",
        "font_color": "#000000",
        "align": "center",
        "valign": "vcenter"
    })

    fmt_civil = workbook.add_format({
        "bg_color": "#F5F5F5",
        "font_color": "#000000",
        "align": "center",
        "valign": "vcenter"
    })

    # ≤ -18°
    worksheet.conditional_format(1, idx_sun, len(df), idx_sun, {
        "type": "cell",
        "criteria": "<=",
        "value": -18,
        "format": fmt_astro
    })

    # -18 .. -12
    worksheet.conditional_format(1, idx_sun, len(df), idx_sun, {
        "type": "cell",
        "criteria": "between",
        "minimum": -18,
        "maximum": -12,
        "format": fmt_astro_twilight
    })

    # -12 .. -6
    worksheet.conditional_format(1, idx_sun, len(df), idx_sun, {
        "type": "cell",
        "criteria": "between",
        "minimum": -12,
        "maximum": -6,
        "format": fmt_nautical
    })

    # > -6
    worksheet.conditional_format(1, idx_sun, len(df), idx_sun, {
        "type": "cell",
        "criteria": ">",
        "value": -6,
        "format": fmt_civil
    })


    fmt_p1 = workbook.add_format({"bg_color": "#63BE7B", "font_color": "#000000","align": "center","valign": "vcenter"})
    fmt_p2 = workbook.add_format({"bg_color": "#C6EFCE","font_color": "#000000","align": "center","valign": "vcenter"})
    fmt_p3 = workbook.add_format({"bg_color": "#FFEB9C","font_color": "#000000","align": "center","valign": "vcenter"})
    fmt_p4 = workbook.add_format({"bg_color": "#FFC7CE","font_color": "#000000","align": "center","valign": "vcenter"})

    idx_prio = df.columns.get_loc("Priorita")
    worksheet.conditional_format(1, idx_prio, len(df), idx_prio, {
        'type': 'cell', 'criteria': '==', 'value': '"1"', 'format': fmt_p1
    })
    worksheet.conditional_format(1, idx_prio, len(df), idx_prio, {
        'type': 'cell', 'criteria': '==', 'value': '"2"', 'format': fmt_p2
    })
    worksheet.conditional_format(1, idx_prio, len(df), idx_prio, {
        'type': 'cell', 'criteria': '==', 'value': '"3"', 'format': fmt_p3
    })
    worksheet.conditional_format(1, idx_prio, len(df), idx_prio, {
        'type': 'cell', 'criteria': '==', 'value': '"4"', 'format': fmt_p4
    })



    idx_total = df.columns.get_loc("Oblačnost")
    idx_low   = df.columns.get_loc("Nízká")
    idx_mid   = df.columns.get_loc("Střední")
    idx_high  = df.columns.get_loc("Vysoká")

    CLOUD_COLORS = {
    0:   "#FFFFFF",
    5:   "#F6F9FC",
    10:  "#EEF3F9",
    15:  "#E6EEF7",
    20:  "#DDE8F4",
    25:  "#D4E2F1",
    30:  "#CCDCEE",
    35:  "#C4D7EC",
    40:  "#BBD1E9",
    45:  "#B2CBE6",
    50:  "#AAC5E3",
    55:  "#A2C0E1",
    60:  "#99BADE",
    65:  "#90B4DB",
    70:  "#88AED8",
    75:  "#80A9D6",
    80:  "#77A3D3",
    85:  "#6E9DD0",
    90:  "#6697CD",
    95:  "#5E92CB",
    100: "#558CC8"
    }

    cloud_formats = {
    k: workbook.add_format({
        "bg_color": v,
        "font_color": "#333333",
        "align": "center",
        "valign": "vcenter"
    })
    for k, v in CLOUD_COLORS.items()
    }

    for col_name in ["Nízká", "Střední", "Vysoká"]:
        col = df.columns.get_loc(col_name)

        for r in range(len(df)):
            val = df.iloc[r][col_name]
            if val == "" or pd.isna(val):
                continue

            cls= min(100, max(0, int(round((100-int(val)) / 5) * 5)))
            worksheet.write(r + 1, col, val, cloud_formats[cls])




    idx_total = df.columns.get_loc("Oblačnost")
    for r in range(len(df)):
        date_str = df.iloc[r]["Datum"]
        hour = df.iloc[r]["Nejvyšší poloha"][:2]

        key = datetime.strptime(
            f"{date_str[:8]} {hour}",
            "%Y%m%d %H"
        ).strftime("%Y-%m-%d %H:00")

        rating = forecast.get(key, {}).get("rating")
        val = df.iloc[r, idx_total]

        if rating == "good":
            worksheet.write(r + 1, idx_total, val, fmt_good)
        elif rating == "ok":
            worksheet.write(r + 1, idx_total, val, fmt_ok)
        elif rating == "bad":
            worksheet.write(r + 1, idx_total, val, fmt_bad)

    fmt_sep = workbook.add_format({'top': 2})
    fmt_sep_right = workbook.add_format({'top': 2, 'right': 2})

    thick_right_cols = [0, 3, 8, 10, 11, 13]

    for col in range(len(df.columns)):
        current_fmt = fmt_sep_right if col in thick_right_cols else fmt_sep

        worksheet.conditional_format(1, col, len(df), col, {
            'type':     'formula',
            'criteria': '=RIGHT($A2,4)="--01"',
            'format':   current_fmt
        })

    worksheet.freeze_panes(1, 0)
    for col_num, value in enumerate(df.columns):
        worksheet.write(0, col_num, value, header_format)

    writer.close()
    print("Saved to Prelety.xlsx")


if __name__ == "__main__":
    links,tags=get_links()
    forecast=fetch_weather()
    table=create_table(links,tags,forecast)


    df=pd.DataFrame(table,columns=columns)
    write_to_csv(df)

    write_to_Excel(df)
