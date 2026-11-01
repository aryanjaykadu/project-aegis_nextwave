"""Cached Open-Meteo forecast adapter; never merges forecasts with Aegis estimates."""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ATTRIBUTION = "Weather data by Open-Meteo.com"
ATTRIBUTION_URL = "https://open-meteo.com/"
LICENSE_URL = "https://open-meteo.com/en/licence"
TERMS_URL = "https://open-meteo.com/en/terms"
CACHE_TTL_SECONDS = 900
_cache: dict[tuple[float, float], tuple[float, dict[str, Any]]] = {}
_cache_lock = threading.Lock()


class ForecastUnavailable(Exception):
    """Raised when neither a fresh upstream forecast nor a cache entry exists."""


def _finite_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _series(values: Any, expected: int) -> list[float | None]:
    if not isinstance(values, list):
        return [None] * expected
    return [_finite_or_none(value) for value in values[:expected]] + [None] * max(0, expected - len(values))


def _format_response(raw: dict[str, Any], lat: float, lon: float, fetched_at: str) -> dict[str, Any]:
    hourly = raw.get("hourly") or {}
    daily = raw.get("daily") or {}
    hourly_times = hourly.get("time") or []
    daily_times = daily.get("time") or []
    current_time = (raw.get("current") or {}).get("time")
    current_time_utc = None
    if current_time:
        try:
            offset_seconds = int(raw.get("utc_offset_seconds") or 0)
            local = datetime.fromisoformat(str(current_time))
            if local.tzinfo is None:
                local = local.replace(tzinfo=timezone(timedelta(seconds=offset_seconds)))
            current_time_utc = local.astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError, OverflowError):
            current_time_utc = None
    return {
        "target": {"lat": lat, "lon": lon},
        "forecast": {
            "source": "Open-Meteo",
            "product": "Best-match weather forecast",
            "model_run_time": None,
            "model_run_time_note": "The provider response does not expose a model run timestamp.",
            "provider_current_time": current_time,
            "provider_current_time_utc": current_time_utc,
            "fetched_at": fetched_at,
            "freshness_threshold_minutes": 360,
            "timezone": raw.get("timezone") or "Asia/Kolkata",
            "hourly": {
                "time": hourly_times,
                "temperature_2m_c": _series(hourly.get("temperature_2m"), len(hourly_times)),
                "apparent_temperature_c": _series(hourly.get("apparent_temperature"), len(hourly_times)),
                "uv_index": _series(hourly.get("uv_index"), len(hourly_times)),
                "precipitation_mm": _series(hourly.get("precipitation"), len(hourly_times)),
                "precipitation_probability_percent": _series(hourly.get("precipitation_probability"), len(hourly_times)),
                "wind_speed_10m_kmh": _series(hourly.get("wind_speed_10m"), len(hourly_times)),
                "relative_humidity_2m_percent": _series(hourly.get("relative_humidity_2m"), len(hourly_times)),
            },
            "daily": {
                "time": daily_times,
                "precipitation_sum_mm": _series(daily.get("precipitation_sum"), len(daily_times)),
                "temperature_2m_min_c": _series(daily.get("temperature_2m_min"), len(daily_times)),
                "temperature_2m_max_c": _series(daily.get("temperature_2m_max"), len(daily_times)),
                "wind_speed_10m_max_kmh": _series(daily.get("wind_speed_10m_max"), len(daily_times)),
            },
            "attribution": ATTRIBUTION,
            "attribution_url": ATTRIBUTION_URL,
            "license": "CC BY 4.0 (per Open-Meteo license page; verify terms for deployment)",
            "license_url": LICENSE_URL,
            "terms_url": TERMS_URL,
            "usage_note": "Free API use is limited to non-commercial purposes under the provider terms.",
            "uncertainty_note": "This response does not provide an uncertainty range. It is a model forecast, not an observation.",
            "official_warning_status": "not_configured",
            "map_layer_status": "not_available",
        },
        "official_warnings": {
            "status": "not_configured",
            "message": "No official warning feed is connected here. No active official warning found in the sources we check. This does not mean there is no risk.",
        },
    }


def get_forecast(lat: float, lon: float, *, http_get=requests.get, now: float | None = None) -> dict[str, Any]:
    """Fetch a point forecast through a 15-minute rounded-grid cache."""
    cache_key = (round(lat, 2), round(lon, 2))
    current = time.time() if now is None else now
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and current - cached[0] < CACHE_TTL_SECONDS:
            result = dict(cached[1])
            result["forecast"] = {**result["forecast"], "cache_status": "fresh"}
            return result

    params = {
        "latitude": cache_key[0],
        "longitude": cache_key[1],
        "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
        "hourly": "temperature_2m,apparent_temperature,uv_index,relative_humidity_2m,precipitation,precipitation_probability,wind_speed_10m",
        "daily": "precipitation_sum,temperature_2m_min,temperature_2m_max,wind_speed_10m_max",
        "forecast_days": 7,
        "timezone": "Asia/Kolkata",
    }
    try:
        response = http_get(FORECAST_URL, params=params, timeout=8)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("hourly"), dict) or not isinstance(payload.get("daily"), dict):
            raise ValueError("Forecast provider returned an incomplete response.")
        fetched_at = datetime.now(timezone.utc).isoformat()
        result = _format_response(payload, cache_key[0], cache_key[1], fetched_at)
        result["forecast"]["cache_status"] = "live"
        with _cache_lock:
            _cache[cache_key] = (current, result)
        return result
    except (requests.RequestException, ValueError, TypeError) as exc:
        with _cache_lock:
            cached = _cache.get(cache_key)
        if cached:
            result = dict(cached[1])
            result["forecast"] = {
                **result["forecast"],
                "cache_status": "stale",
                "stale_reason": "Live forecast unavailable; showing a previously fetched forecast.",
            }
            return result
        raise ForecastUnavailable("Forecast provider is unavailable and no cached forecast exists.") from exc


def clear_forecast_cache() -> None:
    with _cache_lock:
        _cache.clear()
