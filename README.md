# 🛰️ LASARsat Transit Tracker (HaP Teplice)

**Automated generation of LASARsat transit tables for HaP Teplice, integrated with local weather forecasts.**

[![Status](https://github.com/Al33xF/LASARsat-Transit-Table/actions/workflows/update.yml/badge.svg?branch=main)](https://github.com/Al33xF/LASARsat-Transit-Table/actions/workflows/update.yml)
![Frequency](https://img.shields.io/badge/Updates-Daily%20%40%2002%3A15%20UTC-blue)
![Format](https://img.shields.io/badge/Format-.xlsx-green)

[![Heavens-Above](https://img.shields.io/badge/Data_Provider-Heavens--Above-1a237e?style=for-the-badge&logo=satellite&logoColor=white)](https://heavens-above.com/)
[![Clear Outside](https://img.shields.io/badge/Weather_Provider-Clear_Outside-43a047?style=for-the-badge&logo=leaf&logoColor=white)](https://clearoutside.com/)
---

## 📥 Download Latest Table

The transit table is automatically generated every morning to ensure the most accurate weather data and orbital elements.

### [👉 **Download Latest Report (Prelety.xlsx)**](https://github.com/Al33xF/LASARsat-Transit-Table/raw/main/Prelety.xlsx)

*(Clicking this link will immediately download the version generated this morning).*

---

## ℹ️ About This Tool

This project automates the planning of **LASARsat** observations for the **Teplice Observatory (HaP Teplice)**.

Satellite pass predictions decay over time due to atmospheric drag, and weather forecasts change rapidly. To solve this, this repository uses an automated script that runs **every day at 02:15 UTC**.

It performs the following steps:
1.  **Retrieve Orbit Data:** Fetches the precise pass timings for LASARsat from *Heavens-Above*.
2.  **Retrieve Weather:** Fetches the cloud cover forecast for Teplice from *Clear Outside*.
3.  **Cross-Reference:** Matches the exact time of the pass with the specific weather forecast for that hour.
4.  **Publish:** Generates a formatted Excel file ready for use.

---

## ⚡ Powered By

*   **[Heavens-Above](https://heavens-above.com/)** – Satellite ephemeris and transit calculations.
*   **[Clear Outside](https://clearoutside.com/)** – Astronomer-centric weather forecasting.

---

*Automated by GitHub Actions.*
