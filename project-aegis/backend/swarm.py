"""Patna-focused flood-event inference with explicit live-data fallbacks."""
from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import joblib
import pandas as pd
import requests
from backend.feature_logic import confidence_assessment

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT / "models" / "aegis_rf_model.pkl"
FEATURES = ["rainfall_local_mm", "river_discharge_m3s", "soil_moisture_local", "rainfall_local_mm_sum7d", "month_sin", "month_cos"]
WHAT_IF_FEATURES = FEATURES[:4]
TRAINING_NOTICE = (
    "Patna research prototype; sparse event labels and uncalibrated probabilities. "
    "Not validated for emergency decisions."
)


@lru_cache(maxsize=1)
def _load_model_artifact():
    return joblib.load(MODEL_PATH)


@lru_cache(maxsize=1)
def model_input_ranges():
    path = ROOT / "data" / "patna_training_dataset.csv"
    if not path.exists():
        raise FileNotFoundError("Local training data is unavailable; model input ranges cannot be verified.")
    frame = pd.read_csv(path, usecols=WHAT_IF_FEATURES)
    ranges = {}
    for feature in WHAT_IF_FEATURES:
        values = pd.to_numeric(frame[feature], errors="coerce").dropna()
        if values.empty:
            raise ValueError(f"No training range is available for {feature}.")
        minimum, maximum = float(values.min()), float(values.max())
        ranges[feature] = {"min": minimum, "max": maximum, "step": max((maximum - minimum) / 100, 0.001)}
    return ranges


def predict_what_if(inputs: dict[str, float]) -> dict[str, Any]:
    ranges = model_input_ranges()
    if not inputs or set(inputs) - set(ranges):
        raise ValueError("Only the numeric features used by the trained model are supported.")
    for feature, value in inputs.items():
        limits = ranges[feature]
        if not isinstance(value, (int, float)) or not __import__("math").isfinite(value):
            raise ValueError(f"{feature} must be a finite number.")
        if not limits["min"] <= value <= limits["max"]:
            raise ValueError(f"{feature} must stay within its observed training range.")

    artifact = _load_model_artifact()
    features = artifact.get("features", FEATURES)
    medians = artifact.get("training_medians", {})
    values = {feature: float(inputs.get(feature, medians.get(feature, 0.0))) for feature in features}
    row = pd.DataFrame([[values[feature] for feature in features]], columns=features)
    models = artifact.get("horizon_models", {}) or {"24": artifact["model"]}
    probabilities = {str(horizon): float(model.predict_proba(row)[0][1]) for horizon, model in models.items()}
    return {"probabilities": probabilities, "inputs": values, "ranges": ranges}


def _as_float(values, index=-1):
    try:
        value = values[index]
        return float(value) if value is not None else None
    except (IndexError, TypeError, ValueError):
        return None


def _recent_hourly_value(times, values, window_hours=None, as_sum=False):
    now = datetime.now(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None)
    candidates = []
    for stamp, value in zip(times or [], values or []):
        try:
            moment = datetime.fromisoformat(str(stamp)).replace(tzinfo=None)
            number = float(value)
        except (TypeError, ValueError):
            continue
        if moment <= now and (window_hours is None or moment >= now - timedelta(hours=window_hours)):
            candidates.append((moment, number))
    if as_sum:
        return sum(value for _, value in candidates) if candidates else None
    return candidates[-1][1] if candidates else None


def _recent_daily_sum(times, values, before_date, count):
    available = []
    for day, value in zip(times or [], values or []):
        try:
            if day < before_date and value is not None:
                available.append(float(value))
        except (TypeError, ValueError):
            continue
    return sum(available[-count:]) if available else None


def _weather(lat: float, lon: float):
    result = {
        "precipitation": None,
        "rainfall_7d": None,
        "soil_moisture": None,
        "river_discharge": None,
        "windspeed": 0.0,
        "temp": 0.0,
    }
    available = {"weather": False, "soil_moisture": False, "river_discharge": False}
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "precipitation,wind_speed_10m,temperature_2m",
                "hourly": "soil_moisture_0_to_1cm,soil_moisture_1_to_3cm,soil_moisture_3_to_9cm,precipitation",
                "daily": "precipitation_sum",
                "past_days": 7,
                "forecast_days": 1,
                "timezone": "Asia/Kolkata",
            },
            timeout=7,
        )
        r.raise_for_status()
        d = r.json()
        current = d.get("current", {})
        daily = d.get("daily", {})
        hourly = d.get("hourly", {})
        times = daily.get("time", [])
        rain_values = daily.get("precipitation_sum", [])
        today = datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()
        rain_24h = _recent_hourly_value(hourly.get("time"), hourly.get("precipitation"), window_hours=24, as_sum=True)
        result["precipitation"] = float(rain_24h if rain_24h is not None else (current.get("precipitation") or 0.0))
        prior_6d = _recent_daily_sum(times, rain_values, today, 6)
        result["rainfall_7d"] = (prior_6d or 0.0) + result["precipitation"] if prior_6d is not None else None
        result["windspeed"] = float(current.get("wind_speed_10m") or 0.0)
        result["temp"] = float(current.get("temperature_2m") or 0.0)
        soil_0_1 = _recent_hourly_value(hourly.get("time"), hourly.get("soil_moisture_0_to_1cm"))
        soil_1_3 = _recent_hourly_value(hourly.get("time"), hourly.get("soil_moisture_1_to_3cm"))
        soil_3_9 = _recent_hourly_value(hourly.get("time"), hourly.get("soil_moisture_3_to_9cm"))
        if all(value is not None for value in (soil_0_1, soil_1_3, soil_3_9)):
            result["soil_moisture"] = (soil_0_1 + 2 * soil_1_3 + 4 * soil_3_9) / 7
        available["weather"] = True
        available["soil_moisture"] = result["soil_moisture"] is not None
    except (requests.RequestException, ValueError, TypeError):
        # Missing feeds stay missing and are filled from local training medians.
        pass

    try:
        r = requests.get(
            "https://flood-api.open-meteo.com/v1/flood",
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "river_discharge",
                "past_days": 2,
                "forecast_days": 1,
                "timezone": "Asia/Kolkata",
            },
            timeout=7,
        )
        r.raise_for_status()
        flood_daily = r.json().get("daily", {})
        flood_dates = flood_daily.get("time", [])
        flood_values = flood_daily.get("river_discharge", [])
        today = datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()
        recent = [float(value) for day, value in zip(flood_dates, flood_values) if day <= today and value is not None]
        result["river_discharge"] = recent[-1] if recent else None
        available["river_discharge"] = result["river_discharge"] is not None
    except (requests.RequestException, ValueError, TypeError):
        pass

    return result, available


def _predict(w: dict[str, Any]):
    try:
        artifact = _load_model_artifact()
        features = artifact.get("features", FEATURES)
        models = artifact.get("horizon_models", {})
        if not models:
            models = {"24": artifact["model"]}
        medians = artifact.get("training_medians", {})
        month = datetime.now(ZoneInfo("Asia/Kolkata")).month
        values = {
            "rainfall_local_mm": w.get("precipitation"),
            "river_discharge_m3s": w.get("river_discharge"),
            "soil_moisture_local": w.get("soil_moisture"),
            "rainfall_local_mm_sum7d": w.get("rainfall_7d"),
            "month_sin": __import__("math").sin((month - 1) * 2 * __import__("math").pi / 12),
            "month_cos": __import__("math").cos((month - 1) * 2 * __import__("math").pi / 12),
        }
        missing_features = [key for key, value in values.items() if value is None]
        values = {key: (medians.get(key, 0.0) if value is None else value) for key, value in values.items()}
        row = pd.DataFrame([[values.get(feature, medians.get(feature, 0.0)) for feature in features]], columns=features)
        probabilities = {str(h): float(model.predict_proba(row)[0][1]) for h, model in models.items()}
        primary = probabilities.get("24", next(iter(probabilities.values())))
        primary_model = models.get("24", next(iter(models.values())))
        estimator = getattr(primary_model, "named_steps", {}).get("model", primary_model)
        importance = getattr(estimator, "feature_importances_", None)
        global_importance = ({str(name): round(float(weight), 5) for name, weight in zip(features, importance)}
                             if importance is not None and len(importance) == len(features) else {})
        meta = {
            "features": features,
            "horizon_probabilities": probabilities,
            "horizon_metrics": artifact.get("horizon_metrics", {}),
            "coverage_region": artifact.get("coverage_region", "Patna, Bihar"),
            "operationally_validated": False,
            "training_notice": artifact.get("training_notice", TRAINING_NOTICE),
            "label_provenance": artifact.get("label_provenance"),
            "probability_calibration": artifact.get("probability_calibration", "uncalibrated"),
            "input_window": "current Open-Meteo weather, recent rainfall and GloFAS discharge; missing fields median-filled",
            "filled_features": missing_features,
            "input_values": {key: round(float(values[key]), 5) for key in features if key in values},
            "global_feature_importance": global_importance,
            "importance_note": "Model-wide tree importance, not a per-scan causal explanation.",
        }
        return primary, "patna_event_extra_trees", meta
    except Exception:
        rain = w.get("precipitation")
        probability = min(1.0, max(0.0, (float(rain or 0.0) / 120.0) + float(w.get("windspeed") or 0.0) / 180.0))
        return probability, "transparent_threshold_fallback", {
            "features": FEATURES,
            "horizon_probabilities": {"24": probability},
            "horizon_metrics": {},
            "coverage_region": "none",
            "operationally_validated": False,
            "training_notice": "Trained Patna model is unavailable. Threshold fallback is illustrative and not an emergency forecast.",
            "probability_calibration": "not calibrated",
            "input_window": "simple rainfall/wind fallback",
            "input_values": {"rainfall_local_mm": w.get("precipitation"), "wind_speed_kmh": w.get("windspeed")},
            "global_feature_importance": {},
            "importance_note": "Fallback uses a fixed illustrative threshold formula; it is not the trained model.",
        }


def run_aegis_swarm(lat: float, lon: float) -> dict[str, Any]:
    weather, availability = _weather(lat, lon)
    probability, source, meta = _predict(weather)
    # This intentionally describes a rough model domain, not a legal district boundary.
    within_patna_area = 25.05 <= lat <= 26.05 and 84.55 <= lon <= 85.75
    meta["target_within_training_region"] = within_patna_area
    warning = meta.get("training_notice", TRAINING_NOTICE)
    if not within_patna_area:
        warning = "Only a single Patna-area weather point was used; this target is outside that approximate area. " + warning
    observed_fields=sum(availability.get(key,False) for key in ("weather","soil_moisture","river_discharge"))
    fresh_fields=sum(availability.get(key,False) for key in ("weather","soil_moisture"))
    meta["confidence"]=confidence_assessment(observed_fields=observed_fields,fresh_fields=fresh_fields,target_in_region=within_patna_area,
        trained_model=source=="patna_event_extra_trees",median_filled=bool(meta.get("filled_features")),
        weather_available=availability.get("weather",False),discharge_available=availability.get("river_discharge",False))
    checked_at=datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()
    meta["data_health"]=[
        {"source":"Open-Meteo weather","status":"fresh" if availability.get("weather") else "missing","checked_at":checked_at,"note":"Provider responded during this scan; upstream observation timestamp is not retained here."},
        {"source":"Open-Meteo soil moisture","status":"fresh" if availability.get("soil_moisture") else "missing","checked_at":checked_at if availability.get("soil_moisture") else None,"note":"Modeled grid value, not an in-situ sensor reading."},
        {"source":"Open-Meteo Flood API modeled discharge","status":"stale" if availability.get("river_discharge") else "missing","checked_at":checked_at if availability.get("river_discharge") else None,"note":"Daily value timestamp is not retained in current adapter; freshness cannot be confirmed."},
        {"source":"Patna event training labels","status":"stale","checked_at":None,"note":"Sparse historical labels; bundled artifact metadata records training provenance."},
    ]
    severity = "critical" if probability >= 0.75 else "high" if probability >= 0.5 else "moderate" if probability >= 0.25 else "low"
    route = [[lat - 0.05, lon - 0.06], [lat + 0.03, lon - 0.08], [lat + 0.07, lon], [lat + 0.03, lon + 0.08], [lat - 0.05, lon + 0.06]]
    exposure = round(max(0, float(weather.get("precipitation") or 0)) * 0.85, 2)
    return {
        "status": "success",
        "alert": f"{severity.upper()} research estimate at {lat:.2f}, {lon:.2f}; verify against official local warnings.",
        "lat": lat,
        "lon": lon,
        "wind_speed": f"{weather['windspeed']:.1f} km/h",
        "rain_sum": f"{(weather.get('precipitation') or 0):.1f} mm",
        "wind": f"{weather['windspeed']:.1f} km/h",
        "rain": f"{(weather.get('precipitation') or 0):.1f} mm",
        "ml_confidence": f"{probability * 100:.1f}%",
        "model_probability": round(probability, 4),
        "severity": severity,
        "inference_source": source,
        "live_weather_available": availability["weather"],
        "weather_data_availability": availability,
        "model_metadata": meta,
        "confidence": meta.get("confidence"),
        "data_health": meta.get("data_health"),
        "geography_warning": warning,
        "operationally_validated": False,
        "agricultural_exposure_lakhs": exposure,
        "exposure_is_illustrative": True,
        "financial_ticker": f"ILLUSTRATIVE ONLY: rainfall-based exposure proxy ₹{exposure} LAKHS; not a verified damage estimate",
        "vlm_assessment": "Satellite image analysis is not connected. No imagery was analyzed for this target.",
        "detour_path": route,
        "microgrid_nodes": [
            {"lat": lat + 0.03, "lon": lon + 0.03, "status": "DEMO: simulated hospital-grid reroute"},
            {"lat": lat - 0.03, "lon": lon - 0.03, "status": "DEMO: simulated node isolation"},
        ],
        "sos_beacons": [
            {"lat": lat + 0.01, "lon": lon + 0.01, "text": "DEMO SOS: simulated example; not a received report."},
            {"lat": lat - 0.015, "lon": lon + 0.02, "text": "DEMO SOS: simulated example; not a received report."},
        ],
        "demo_layers": True,
        "operational_warning": warning,
    }
