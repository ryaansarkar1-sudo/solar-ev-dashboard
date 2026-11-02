"""
Solar EV Backup Charging - SAM (PySAM) simulations
===================================================
Runs NREL's System Advisor Model (PVWatts) under different conditions and
answers: "how much power / energy can our deployable panels generate, and how
many km of EV range does that give?"

HOW TO USE
  1. Put one or more SAM weather files (.csv) in the  weather/  folder.
  2. Edit the SETTINGS section below (panel area, efficiency, etc.).
  3. Run:   python run_simulations.py
  4. Results appear in the  results/  folder (CSV tables + PNG charts).
"""

import glob
import os

import matplotlib.pyplot as plt
import pandas as pd
import PySAM.Pvwattsv8 as pvwatts

# ----------------------------------------------------------------------------
# SETTINGS  (edit these)
# ----------------------------------------------------------------------------
WEATHER_DIR = "weather"
RESULTS_DIR = "results"

# Panel set-up (deployable panels on a car)
PANEL_AREA_M2 = 2.0          # total deployed panel area
PANEL_EFFICIENCY = 0.22      # 22% = good commercial panel
STC_IRRADIANCE = 1000        # W/m2 (standard test condition, don't change)
SYSTEM_KW_DC = PANEL_AREA_M2 * PANEL_EFFICIENCY * STC_IRRADIANCE / 1000  # kW

# Baseline conditions used when we vary just ONE thing at a time
BASE_TILT = 20               # degrees from horizontal
BASE_AZIMUTH = "auto"        # "auto" = face the equator (north in Australia, south in the US)
                             # or set a number: 0 = north, 90 = east, 180 = south, 270 = west
BASE_LOSSES = 14.0           # % total system losses (PVWatts default)
BASE_ARRAY_TYPE = 0          # 0 = fixed open rack, 1 = fixed roof mount,
                             # 2 = 1-axis tracker, 4 = 2-axis tracker
BASE_DC_AC_RATIO = 1.1

# EV assumptions (Tesla Model 3 is roughly 150 Wh/km real-world)
EV_WH_PER_KM = 150
EV_BATTERY_KWH = 60

# Values to sweep
TILTS = [0, 10, 20, 30, 40, 50, 60]
AZIMUTHS = [0, 45, 90, 135, 180, 225, 270, 315]
LOSSES = [5, 10, 14, 20, 25, 30]
AREAS_M2 = [1, 2, 3, 4, 6]
ARRAY_TYPES = {0: "Fixed open rack", 1: "Fixed roof mount",
               2: "1-axis tracking", 4: "2-axis tracking"}
# ----------------------------------------------------------------------------


def file_latitude(weather_file):
    """Read the latitude from line 2 of a SAM weather csv."""
    with open(weather_file, encoding="utf-8-sig") as f:
        names = f.readline().strip().split(",")
        values = f.readline().strip().split(",")
    return float(values[names.index("Latitude")])


def run_pvwatts(weather_file, kw_dc=SYSTEM_KW_DC, tilt=BASE_TILT,
                azimuth=BASE_AZIMUTH, losses=BASE_LOSSES,
                array_type=BASE_ARRAY_TYPE):
    """Run one PVWatts simulation and return a dict of key results."""
    if azimuth == "auto":
        azimuth = 180 if file_latitude(weather_file) >= 0 else 0
    m = pvwatts.default("PVWattsNone")
    m.SolarResource.solar_resource_file = weather_file
    m.SystemDesign.system_capacity = kw_dc
    m.SystemDesign.tilt = tilt
    m.SystemDesign.azimuth = azimuth
    m.SystemDesign.losses = losses
    m.SystemDesign.array_type = array_type
    m.SystemDesign.dc_ac_ratio = BASE_DC_AC_RATIO
    m.execute()

    annual_kwh = m.Outputs.ac_annual
    daily_kwh = annual_kwh / 365
    hourly_w = list(m.Outputs.ac)
    return {
        "annual_kwh": annual_kwh,
        "avg_daily_kwh": daily_kwh,
        "peak_power_w": max(hourly_w),
        "capacity_factor_%": m.Outputs.capacity_factor,
        "avg_daily_range_km": daily_kwh * 1000 / EV_WH_PER_KM,
        "daily_pct_of_battery": 100 * daily_kwh / EV_BATTERY_KWH,
        "monthly_kwh": list(m.Outputs.ac_monthly),
        "hourly_w": hourly_w,
    }


def site_name(path):
    return os.path.splitext(os.path.basename(path))[0]


def save_bar(df, x, y, title, xlabel, ylabel, filename, hue=None):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    if hue:
        df.pivot(index=x, columns=hue, values=y).plot(kind="bar", ax=ax)
    else:
        df.plot(kind="bar", x=x, y=y, ax=ax, legend=False, color="#378ADD")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    plt.xticks(rotation=0)
    plt.tight_layout()
    fig.savefig(os.path.join(RESULTS_DIR, filename), dpi=150)
    plt.close(fig)


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(WEATHER_DIR, "*.csv")))
    if not files:
        raise SystemExit(
            f"No weather files found in '{WEATHER_DIR}/'. "
            "Add at least one SAM weather .csv (see README)."
        )

    print(f"System size: {SYSTEM_KW_DC:.2f} kW DC "
          f"({PANEL_AREA_M2} m2 at {PANEL_EFFICIENCY:.0%} efficiency)")
    print(f"Weather files found: {[site_name(f) for f in files]}\n")

    # 1) Compare LOCATIONS / weather files -----------------------------------
    rows, monthly = [], {}
    for f in files:
        r = run_pvwatts(f)
        monthly[site_name(f)] = r["monthly_kwh"]
        rows.append({"location": site_name(f),
                     **{k: v for k, v in r.items()
                        if k not in ("monthly_kwh", "hourly_w")}})
    loc = pd.DataFrame(rows).round(2)
    loc.to_csv(os.path.join(RESULTS_DIR, "1_locations.csv"), index=False)
    print("1) LOCATIONS\n", loc.to_string(index=False), "\n")
    save_bar(loc, "location", "avg_daily_kwh", "Average daily energy by location",
             "Location", "kWh / day", "1_locations.png")

    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    mdf = pd.DataFrame(monthly, index=months)
    mdf.to_csv(os.path.join(RESULTS_DIR, "2_monthly_energy.csv"))
    ax = mdf.plot(marker="o", figsize=(8, 4.5), title="Monthly energy (kWh)")
    ax.set_ylabel("kWh / month")
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "2_monthly_energy.png"), dpi=150)
    plt.close()

    # The remaining sweeps use the FIRST weather file as the test site.
    # (Change this line to pick a different one.)
    site = next((f for f in files if "sydney" in f.lower()), files[0])
    print(f"Sweeps below use site: {site_name(site)}\n")

    # 2) TILT angle ----------------------------------------------------------
    df = pd.DataFrame([{"tilt_deg": t, **{k: v for k, v in run_pvwatts(site, tilt=t).items()
                        if k in ("avg_daily_kwh", "avg_daily_range_km")}} for t in TILTS]).round(2)
    df.to_csv(os.path.join(RESULTS_DIR, "3_tilt.csv"), index=False)
    print("3) TILT\n", df.to_string(index=False), "\n")
    save_bar(df, "tilt_deg", "avg_daily_kwh", "Daily energy vs panel tilt",
             "Tilt (degrees)", "kWh / day", "3_tilt.png")

    # 3) AZIMUTH (which way the panels face) ---------------------------------
    df = pd.DataFrame([{"azimuth_deg": a, **{k: v for k, v in run_pvwatts(site, azimuth=a).items()
                        if k in ("avg_daily_kwh", "avg_daily_range_km")}} for a in AZIMUTHS]).round(2)
    df.to_csv(os.path.join(RESULTS_DIR, "4_azimuth.csv"), index=False)
    print("4) AZIMUTH\n", df.to_string(index=False), "\n")
    save_bar(df, "azimuth_deg", "avg_daily_kwh", "Daily energy vs panel direction",
             "Azimuth (0=N, 90=E, 180=S, 270=W)", "kWh / day", "4_azimuth.png")

    # 4) SYSTEM LOSSES (wiring, dirt, inverter, heat) ------------------------
    df = pd.DataFrame([{"losses_%": l, **{k: v for k, v in run_pvwatts(site, losses=l).items()
                        if k in ("avg_daily_kwh", "avg_daily_range_km")}} for l in LOSSES]).round(2)
    df.to_csv(os.path.join(RESULTS_DIR, "5_losses.csv"), index=False)
    print("5) LOSSES\n", df.to_string(index=False), "\n")
    save_bar(df, "losses_%", "avg_daily_kwh", "Daily energy vs system losses",
             "Total losses (%)", "kWh / day", "5_losses.png")

    # 5) PANEL AREA (answers "how much panel do we need?") -------------------
    out = []
    for a in AREAS_M2:
        kw = a * PANEL_EFFICIENCY * STC_IRRADIANCE / 1000
        r = run_pvwatts(site, kw_dc=kw)
        out.append({"area_m2": a, "kw_dc": round(kw, 2),
                    "avg_daily_kwh": r["avg_daily_kwh"],
                    "avg_daily_range_km": r["avg_daily_range_km"],
                    "peak_power_w": r["peak_power_w"]})
    df = pd.DataFrame(out).round(2)
    df.to_csv(os.path.join(RESULTS_DIR, "6_panel_area.csv"), index=False)
    print("6) PANEL AREA\n", df.to_string(index=False), "\n")
    save_bar(df, "area_m2", "avg_daily_range_km", "Daily range gained vs panel area",
             "Panel area (m2)", "km / day", "6_panel_area.png")

    # 6) MOUNT / TRACKING TYPE ----------------------------------------------
    out = []
    for code, name in ARRAY_TYPES.items():
        r = run_pvwatts(site, array_type=code)
        out.append({"mount_type": name, "avg_daily_kwh": r["avg_daily_kwh"],
                    "avg_daily_range_km": r["avg_daily_range_km"]})
    df = pd.DataFrame(out).round(2)
    df.to_csv(os.path.join(RESULTS_DIR, "7_mount_type.csv"), index=False)
    print("7) MOUNT TYPE\n", df.to_string(index=False), "\n")
    save_bar(df, "mount_type", "avg_daily_kwh", "Daily energy by mount / tracking type",
             "Mount type", "kWh / day", "7_mount_type.png")

    # 7) TYPICAL DAY power curve (peak summer vs winter day) ----------------
    r = run_pvwatts(site)
    hourly = pd.Series(r["hourly_w"])
    summer_day = hourly[172 * 24: 173 * 24].reset_index(drop=True)   # ~21 Jun
    winter_day = hourly[355 * 24: 356 * 24].reset_index(drop=True)   # ~21 Dec
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(summer_day, label="Day 173 (~21 Jun)")
    ax.plot(winter_day, label="Day 356 (~21 Dec)")
    ax.set_title("Power output across a day")
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("AC power (W)")
    ax.legend()
    plt.tight_layout()
    fig.savefig(os.path.join(RESULTS_DIR, "8_daily_power_curve.png"), dpi=150)
    plt.close(fig)

    print("Done. Open the 'results' folder for CSV tables and PNG charts.")


if __name__ == "__main__":
    main()
