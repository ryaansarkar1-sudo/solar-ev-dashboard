"""
Download a full year of REAL Sydney sunlight data and save it in the format
SAM / PySAM needs. Run this once:

    py get_sydney_weather.py

It creates:  weather/sydney_open_meteo_2025.csv
Data source: Open-Meteo (free, no account needed).
"""

import os

import pandas as pd
import requests

YEAR = 2025                      # a full past year
LAT, LON, ELEV = -33.8688, 151.2093, 58
UTC_OFFSET = 10                  # Sydney standard time (SAM wants a fixed offset, no daylight saving)
OUT_DIR = "weather"
OUT_FILE = os.path.join(OUT_DIR, f"sydney_open_meteo_{YEAR}.csv")

URL = "https://archive-api.open-meteo.com/v1/archive"


def download():
    params = {
        "latitude": LAT,
        "longitude": LON,
        # a little extra either side so the local-time year is complete
        "start_date": f"{YEAR - 1}-12-30",
        "end_date": f"{YEAR + 1}-01-02",
        "hourly": "shortwave_radiation,direct_normal_irradiance,diffuse_radiation,"
                  "temperature_2m,wind_speed_10m",
        "wind_speed_unit": "ms",
        "timezone": "GMT",
    }
    r = requests.get(URL, params=params, timeout=120)
    r.raise_for_status()
    return r.json()["hourly"]


def build_dataframe(hourly):
    df = pd.DataFrame(hourly)
    df["time"] = pd.to_datetime(df["time"])
    df = df.set_index("time").interpolate(limit_direction="both").fillna(0)

    # Open-Meteo values are the average of the hour ENDING at the timestamp.
    # SAM wants the hour START in local standard time, stamped at minute 30.
    df.index = df.index + pd.Timedelta(hours=UTC_OFFSET - 1)
    df = df[df.index.year == YEAR]
    if len(df) != 8760:
        raise SystemExit(f"Expected 8760 hourly rows but got {len(df)}. "
                         "Try a different YEAR at the top of the script.")
    out = pd.DataFrame({
        "Year": df.index.year, "Month": df.index.month, "Day": df.index.day,
        "Hour": df.index.hour, "Minute": 30,
        "GHI": df["shortwave_radiation"].clip(lower=0).round(1).values,
        "DNI": df["direct_normal_irradiance"].clip(lower=0).round(1).values,
        "DHI": df["diffuse_radiation"].clip(lower=0).round(1).values,
        "Tdry": df["temperature_2m"].round(1).values,
        "Wspd": df["wind_speed_10m"].round(1).values,
    })
    return out


def write_sam_csv(out):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_FILE, "w", newline="") as f:
        f.write("Source,Location ID,City,State,Country,Latitude,Longitude,Time Zone,Elevation\n")
        f.write(f"Open-Meteo,0,Sydney,NSW,Australia,{LAT},{LON},{UTC_OFFSET},{ELEV}\n")
        out.to_csv(f, index=False, lineterminator="\n")


def main():
    print("Downloading Sydney weather for", YEAR, "...")
    out = build_dataframe(download())
    write_sam_csv(out)
    ghi_kwh = out["GHI"].sum() / 1000
    print(f"Saved: {OUT_FILE}")
    print(f"Sanity check: {ghi_kwh:.0f} kWh/m2 of sunlight over the year "
          "(Sydney is normally about 1600-1800).")


if __name__ == "__main__":
    main()
