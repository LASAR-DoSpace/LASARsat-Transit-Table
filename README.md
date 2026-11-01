# 🛰️ LASARsat Transit Tracker

**Automated pass prediction and observation planner for LASARsat (NORAD ID `62391`), correlated with hourly astronomical weather forecasts.**

[![Status](https://github.com/LASAR-DoSpace/LASARsat-Transit-Table/actions/workflows/update.yml/badge.svg?branch=main)](https://github.com/LASAR-DoSpace/LASARsat-Transit-Table/actions/workflows/update.yml)
![Frequency](https://img.shields.io/badge/Updates-Daily%20%40%2002%3A15%20UTC-blue)
![Format](https://img.shields.io/badge/Format-.xlsx%20%7C%20.csv-green)

[![CelesTrak](https://img.shields.io/badge/Orbit_Data-CelesTrak-0288d1?style=for-the-badge&logo=nasa&logoColor=white)](https://celestrak.org/)
[![Skyfield](https://img.shields.io/badge/Astrometry-Skyfield-5c6bc0?style=for-the-badge&logo=python&logoColor=white)](https://rhodesmill.org/skyfield/)
[![Clear Outside](https://img.shields.io/badge/Weather_Provider-Clear_Outside-43a047?style=for-the-badge&logo=leaf&logoColor=white)](https://clearoutside.com/)

---

## 📥 Download Latest Tables

Pass predictions for Low Earth Orbit (LEO) decay quickly due to atmospheric drag, and cloud forecasts shift daily. This table is recomputed every morning at **02:15 UTC** using the latest CelesTrak TLE and a fresh 7-day weather forecast.

*(Clicking a link below downloads the latest schedule generated this morning).*

### 📍 HaP Teplice
* [👉 **Download Teplice Report (.xlsx)**](https://github.com/LASAR-DoSpace/LASARsat-Transit-Table/raw/data/HaP_Teplice.xlsx)
* [📄 Download Teplice Raw Data (.csv)](https://github.com/LASAR-DoSpace/LASARsat-Transit-Table/raw/data/HaP_Teplice.csv)

### 📍 Izaña Station
* [👉 **Download Izaña Report (.xlsx)**](https://github.com/LASAR-DoSpace/LASARsat-Transit-Table/raw/data/Izana.xlsx)
* [📄 Download Izaña Raw Data (.csv)](https://github.com/LASAR-DoSpace/LASARsat-Transit-Table/raw/data/Izana.csv)

---

## ℹ️ About This Tool

This utility automates observation scheduling and optical laser tracking for **LASARsat** across designated ground stations.

### Pipeline Workflow
Every day at 02:15 UTC, GitHub Actions executes:
1. **Orbital Ephemeris Retrieval:** Pulls the newest Two-Line Element (TLE) set for NORAD `62391` directly from **CelesTrak**.
2. **Orbital Propagation:** Uses **Skyfield** (SGP4 + JPL DE421 ephemeris) to determine topocentric geometric coordinates from 0° horizon to culmination, bisection-interpolating exact 10° elevation crossings.
3. **Twilight & Shadow Analysis:** Computes topocentric solar depression angles (filtering out passes where Sun altitude is $>-6^\circ$) and calculates Earth umbra eclipse transitions (shadow entry and exit).
4. **Weather Integration:** Scrapes 7-day hourly cloud cover metrics (total, low, medium, high) from **Clear Outside**.
5. **Excel Formatting & Publishing:** Applies visual conditional formatting to classify observation feasibility and force-pushes reports to the isolated `data` branch.

---

## ⚡ Powered By

* **[CelesTrak](https://celestrak.org/)** – Official NORAD Two-Line Element (TLE) distribution.
* **[Skyfield](https://rhodesmill.org/skyfield/)** – Precise orbital mechanics, SGP4 propagation, and astronomical ephemerides.
* **[Clear Outside](https://clearoutside.com/)** – Astronomer-centric cloud cover forecasting.

---

*Automated by GitHub Actions.*