# 🛰️ LASARsat Transit Tracker

**Automated generation of LASARsat transit tables for multiple locations, integrated with local weather forecasts.**

[![Status](https://github.com/Al33xF/LASARsat-Transit-Table/actions/workflows/update.yml/badge.svg?branch=main)](https://github.com/Al33xF/LASARsat-Transit-Table/actions/workflows/update.yml)
![Frequency](https://img.shields.io/badge/Updates-Daily%20%40%2002%3A15%20UTC-blue)
![Format](https://img.shields.io/badge/Format-.xlsx-green)

[![Heavens-Above](https://img.shields.io/badge/Data_Provider-Heavens--Above-1a237e?style=for-the-badge&logo=satellite&logoColor=white)](https://heavens-above.com/)
[![Clear Outside](https://img.shields.io/badge/Weather_Provider-Clear_Outside-43a047?style=for-the-badge&logo=leaf&logoColor=white)](https://clearoutside.com/)
---

## 📥 Download Latest Tables

The transit tables are automatically generated every morning to ensure the most accurate weather data and orbital elements. 

*(Clicking a link below will immediately download the latest version generated this morning).*

### 📍 HaP Teplice
[👉 **Download Teplice Report (.xlsx)**](https://github.com/Al33xF/LASARsat-Transit-Table/raw/main/output/HaP_Teplice_Prelety.xlsx)

### 📍 Izaña station
[👉 **Download Izaña Report (.xlsx)**](https://github.com/Al33xF/LASARsat-Transit-Table/raw/main/output/Izana_Prelety.xlsx)

---

## ℹ️ About This Tool

This project automates the planning of **LASARsat** observations for multiple observatories and locations.

Satellite pass predictions decay over time due to atmospheric drag, and weather forecasts change rapidly. To solve this, this repository uses an automated script that runs **every day at 02:15 UTC**.

It performs the following steps for each location configured in `locations.json`:
1.  **Retrieve Orbit Data:** Fetches precise pass timings for LASARsat from *Heavens-Above*.
2.  **Retrieve Weather:** Fetches the specific cloud cover forecast from *Clear Outside*.
3.  **Cross-Reference:** Matches the exact time of the pass with the weather forecast for that hour.
4.  **Publish:** Generates a formatted Excel file saved to the `output/` folder.

### Adding a new location
To add a new tracking location, simply edit the `locations.json` file in the root directory. No code changes are required!

---

## ⚡ Powered By

*   **[Heavens-Above](https://heavens-above.com/)** – Satellite ephemeris and transit calculations.
*   **[Clear Outside](https://clearoutside.com/)** – Astronomer-centric weather forecasting.

---

*Automated by GitHub Actions.*