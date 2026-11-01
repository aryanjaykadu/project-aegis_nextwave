"""Build Patna daily predictors with documented India flood-event labels.

Weather/discharge inputs are fetched from Open-Meteo's archive and Flood APIs.
Positive labels come only from the India Flood Inventory; unlisted dates are
not asserted to be flood-free. Run with --offline to rebuild from the saved
daily weather CSV without making network requests.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
WEATHER_PATH = DATA_DIR / "patna_daily_hydroclimate.csv"
EVENTS_PATH = DATA_DIR / "india_flood_inventory_v3.csv"
OUTPUT_PATH = DATA_DIR / "patna_training_dataset.csv"
LAT, LON = 25.5941, 85.1376
START_DATE, END_DATE = "2015-01-01", "2023-12-31"


def fetch_weather() -> pd.DataFrame:
    session = requests.Session()
    session.headers["User-Agent"] = "Project-Aegis/2.1 (research prototype; public dataset preparation)"
    weather = session.get(
        "https://archive-api.open-meteo.com/v1/archive",
        params={
            "latitude": LAT,
            "longitude": LON,
            "start_date": START_DATE,
            "end_date": END_DATE,
            "daily": "precipitation_sum,soil_moisture_0_to_7cm_mean",
            "timezone": "Asia/Kolkata",
        },
        timeout=90,
    )
    weather.raise_for_status()
    wd = weather.json()["daily"]
    wdf = pd.DataFrame(
        {
            "date": wd["time"],
            "rainfall_local_mm": wd["precipitation_sum"],
            "soil_moisture_local": wd.get("soil_moisture_0_to_7cm_mean"),
        }
    )
    if wdf["soil_moisture_local"].isna().all():
        raise RuntimeError("Open-Meteo returned no daily soil moisture; refusing to silently invent it.")

    river = session.get(
        "https://flood-api.open-meteo.com/v1/flood",
        params={
            "latitude": LAT,
            "longitude": LON,
            "start_date": START_DATE,
            "end_date": END_DATE,
            "daily": "river_discharge",
            "timezone": "Asia/Kolkata",
        },
        timeout=120,
    )
    river.raise_for_status()
    rd = river.json()["daily"]
    rdf = pd.DataFrame({"date": rd["time"], "river_discharge_m3s": rd["river_discharge"]})
    df = wdf.merge(rdf, on="date", how="inner").sort_values("date")
    df["date"] = pd.to_datetime(df["date"])
    df["rainfall_local_mm"] = pd.to_numeric(df["rainfall_local_mm"], errors="coerce")
    df["soil_moisture_local"] = pd.to_numeric(df["soil_moisture_local"], errors="coerce")
    df["river_discharge_m3s"] = pd.to_numeric(df["river_discharge_m3s"], errors="coerce")
    df = df.dropna(subset=["date", "rainfall_local_mm", "soil_moisture_local", "river_discharge_m3s"])
    df.to_csv(WEATHER_PATH, index=False)
    return df


def load_weather(offline: bool) -> pd.DataFrame:
    if not offline:
        return fetch_weather()
    if not WEATHER_PATH.exists():
        raise FileNotFoundError(f"{WEATHER_PATH} is missing; run without --offline once to fetch it.")
    return pd.read_csv(WEATHER_PATH, parse_dates=["date"])


def documented_patna_events() -> pd.DataFrame:
    if not EVENTS_PATH.exists():
        raise FileNotFoundError(f"{EVENTS_PATH} is missing; run scripts/download_public_datasets.py first.")
    events = pd.read_csv(EVENTS_PATH, low_memory=False)
    district = events.get("Districts", pd.Series(index=events.index, dtype=str)).fillna("")
    state = events.get("State", pd.Series(index=events.index, dtype=str)).fillna("")
    events = events[district.str.contains(r"\bPatna\b", case=False, regex=True) & state.str.contains("Bihar", case=False)].copy()
    events["start"] = pd.to_datetime(events["Start Date"], format="%d-%m-%Y %H:%M", errors="coerce")
    events["duration_days"] = pd.to_numeric(events.get("Duration(Days)"), errors="coerce").fillna(1).clip(1, 180)
    events = events.dropna(subset=["start"])
    events["end"] = events["start"] + pd.to_timedelta(events["duration_days"] - 1, unit="D")
    return events[["start", "end", "UEI"]].drop_duplicates().sort_values("start")


def build_dataset(weather: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    df = weather.copy().sort_values("date").reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    events = events[(events["end"] >= df["date"].min()) & (events["start"] <= df["date"].max())].copy()
    df["rainfall_local_mm_sum7d"] = df["rainfall_local_mm"].rolling(7, min_periods=1).sum()
    month_angle = (df["date"].dt.month - 1) * (2 * np.pi / 12)
    df["month_sin"] = np.sin(month_angle)
    df["month_cos"] = np.cos(month_angle)
    for hours in (24, 48, 72):
        window_days = hours // 24
        df[f"documented_flood_within_{hours}h"] = [
            int(any(event.start <= day + pd.Timedelta(days=window_days) and event.end >= day for event in events.itertuples()))
            for day in df["date"]
        ]
    df["label_definition"] = "documented Patna event active now or beginning within horizon"
    df.to_csv(OUTPUT_PATH, index=False)
    metadata = {
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "weather_source": "Open-Meteo Historical Weather Archive API and Flood API",
        "weather_urls": ["https://archive-api.open-meteo.com/v1/archive", "https://flood-api.open-meteo.com/v1/flood"],
        "weather_location": {"name": "Patna, Bihar, India", "latitude": LAT, "longitude": LON},
        "weather_period": {"start": str(df.date.min().date()), "end": str(df.date.max().date())},
        "weather_variables": ["daily precipitation sum (mm)", "daily soil moisture (0–7 cm, m³/m³)", "daily river discharge (m³/s)"],
        "event_source": "India Flood Inventory v3, IIT Delhi HydroSense Lab, Zenodo record 16994648 (v4 record; event file v3)",
        "event_doi": "10.5281/zenodo.16994648",
        "event_file": EVENTS_PATH.name,
        "event_license": "Dataset record does not expose a clear license field; cite the source and review terms before redistribution or commercial reuse.",
        "event_filter": "Events whose State contains Bihar and Districts lists Patna; event dates parsed as day-month-year.",
        "patna_events_in_inventory": int(len(events)),
        "label_caveat": "Inventory positives are documented historical events. An unlisted date is not proof of no flood. Sparse labels and one weather grid point make this an exploratory research dataset, not an operational forecast dataset.",
        "prepared_rows": int(len(df)),
    }
    (DATA_DIR / "patna_training_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Saved {len(df):,} daily Patna rows and {len(events):,} documented Patna events to {OUTPUT_PATH}")
    for hours in (24, 48, 72):
        print(f"  {hours}h event-window positives: {int(df[f'documented_flood_within_{hours}h'].sum()):,}")
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="Use the already-downloaded Patna weather series.")
    args = parser.parse_args()
    weather = load_weather(args.offline)
    events = documented_patna_events()
    build_dataset(weather, events)


if __name__ == "__main__":
    main()
