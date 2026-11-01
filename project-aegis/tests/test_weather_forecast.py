from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import requests
from fastapi.testclient import TestClient

from backend import main
from backend.weather_forecast import (
    ATTRIBUTION,
    ForecastUnavailable,
    clear_forecast_cache,
    get_forecast,
)


def provider_response():
    return {
        "timezone": "Asia/Kolkata",
        "utc_offset_seconds": 19800,
        "current": {"time": "2026-11-01T10:00"},
        "hourly": {
            "time": ["2026-11-01T10:00", "2026-11-01T11:00"],
            "temperature_2m": [28, 29],
            "relative_humidity_2m": [68, 65],
            "precipitation": [0.2, 1.1],
            "precipitation_probability": [10, 35],
            "wind_speed_10m": [8, 11],
        },
        "daily": {
            "time": ["2026-11-01"],
            "precipitation_sum": [4.1],
            "temperature_2m_min": [24],
            "temperature_2m_max": [31],
            "wind_speed_10m_max": [14],
        },
    }


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class WeatherForecastTests(unittest.TestCase):
    def setUp(self):
        clear_forecast_cache()

    def tearDown(self):
        clear_forecast_cache()

    def test_forecast_keeps_provider_and_point_values_separate_from_warnings(self):
        result = get_forecast(
            25.5941, 85.1376,
            http_get=lambda *args, **kwargs: FakeResponse(provider_response()),
            now=100,
        )
        forecast = result["forecast"]
        self.assertEqual(forecast["source"], "Open-Meteo")
        self.assertEqual(forecast["hourly"]["precipitation_mm"], [0.2, 1.1])
        self.assertEqual(forecast["daily"]["temperature_2m_max_c"], [31])
        self.assertEqual(forecast["attribution"], ATTRIBUTION)
        self.assertIsNone(forecast["model_run_time"])
        self.assertEqual(forecast["official_warning_status"], "not_configured")
        self.assertEqual(result["official_warnings"]["status"], "not_configured")
        self.assertIn("This does not mean there is no risk", result["official_warnings"]["message"])

    def test_cache_rounds_grid_and_avoids_repeated_upstream_calls(self):
        calls = []

        def fake_get(*args, **kwargs):
            calls.append(kwargs["params"])
            return FakeResponse(provider_response())

        first = get_forecast(25.5941, 85.1376, http_get=fake_get, now=100)
        second = get_forecast(25.5944, 85.1378, http_get=fake_get, now=200)
        self.assertEqual(len(calls), 1)
        self.assertEqual(first["target"], second["target"])
        self.assertEqual(second["forecast"]["cache_status"], "fresh")

    def test_expired_cache_is_marked_stale_when_provider_is_unavailable(self):
        get_forecast(
            25.5941, 85.1376,
            http_get=lambda *args, **kwargs: FakeResponse(provider_response()),
            now=100,
        )

        def fail(*args, **kwargs):
            raise requests.Timeout("provider timed out")

        result = get_forecast(25.5941, 85.1376, http_get=fail, now=1000)
        self.assertEqual(result["forecast"]["cache_status"], "stale")
        self.assertIn("previously fetched", result["forecast"]["stale_reason"])

    def test_provider_failure_without_cache_is_explicit(self):
        def fail(*args, **kwargs):
            raise requests.ConnectionError("offline")

        with self.assertRaises(ForecastUnavailable):
            get_forecast(25.5941, 85.1376, http_get=fail, now=100)


class ResourceCategoryApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        with main._nearby_cache_lock:
            main._nearby_cache.clear()

    def tearDown(self):
        self.client.close()
        with main._nearby_cache_lock:
            main._nearby_cache.clear()

    def test_resource_categories_disclose_map_data_limits(self):
        response = self.client.get("/api/resource-categories")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        ids = {category["id"] for category in payload["categories"]}
        self.assertTrue({"hospital", "shelter", "water", "pharmacy", "fire_station", "blood_bank"} <= ids)
        self.assertEqual(payload["license"], "ODbL")
        self.assertEqual(payload["trust_tier"]["code"], "B")
        self.assertIn("Coverage varies", payload["notice"])

    def test_nearby_payload_has_source_license_edit_date_and_unverified_tier(self):
        payload = {
            "elements": [{
                "type": "node", "id": 123, "lat": 25.59, "lon": 85.13,
                "timestamp": "2026-10-30T10:00:00Z",
                "tags": {"name": "Example Clinic", "amenity": "hospital"},
            }]
        }

        def fake_post(*args, **kwargs):
            return FakeResponse(payload)

        with patch("backend.main.requests.post", side_effect=fake_post):
            response = self.client.get(
                "/api/nearby",
                params={"lat": 25.5941, "lon": 85.1376, "kind": "hospital"},
            )
        self.assertEqual(response.status_code, 200)
        item = response.json()["results"][0]
        self.assertEqual(item["source"], "OpenStreetMap")
        self.assertEqual(item["license"], "Open Database License (ODbL)")
        self.assertEqual(item["last_edited_at"], "2026-10-30T10:00:00Z")
        self.assertEqual(item["trust_tier"]["code"], "B")
        self.assertEqual(item["availability"], "unverified")
        self.assertTrue(item["source_url"].endswith("/node/123"))

    def test_unknown_resource_kind_is_rejected_without_querying_provider(self):
        response = self.client.get(
            "/api/nearby",
            params={"lat": 25.5941, "lon": 85.1376, "kind": "invented_category"},
        )
        self.assertEqual(response.status_code, 400)

    def test_nearby_uses_stale_cache_when_overpass_is_down(self):
        payload = {"elements": [{
            "type": "node", "id": 456, "lat": 25.59, "lon": 85.13,
            "tags": {"name": "Mapped clinic", "amenity": "hospital"},
        }]}
        with patch("backend.main.requests.post", return_value=FakeResponse(payload)):
            first = self.client.get(
                "/api/nearby",
                params={"lat": 25.5941, "lon": 85.1376, "kind": "hospital"},
            )
        self.assertEqual(first.status_code, 200)
        with main._nearby_cache_lock:
            for entry in main._nearby_cache.values():
                entry["cached_at"] = 0

        with patch("backend.main.requests.post", side_effect=requests.ConnectionError("offline")):
            second = self.client.get(
                "/api/nearby",
                params={"lat": 25.5941, "lon": 85.1376, "kind": "hospital"},
            )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["cache_status"], "stale")
        self.assertEqual(second.json()["results"][0]["name"], "Mapped clinic")

    def test_weather_endpoint_is_a_cached_provider_adapter(self):
        expected = {"forecast": {"source": "Open-Meteo"}, "official_warnings": {"status": "not_configured"}}
        with patch("backend.main.get_weather_forecast", return_value=expected):
            response = self.client.get(
                "/api/weather-forecast",
                params={"lat": 25.5941, "lon": 85.1376},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)

    def test_region_pack_index_reports_size_and_download_is_confined(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            filename = "patna-core-2026-11-01.geojson.gz"
            (root / filename).write_bytes(b"compressed-pack")
            (root / "patna-core-2026-11-01.quality.json").write_text(json.dumps({
                "region_id": "patna-core", "version": "2026-11-01",
                "feature_count": 12, "license": "ODbL",
            }), encoding="utf-8")
            with patch("backend.main.RESOURCE_PACK_DIR", root):
                index = self.client.get("/api/resource-packs")
                download = self.client.get(f"/api/resource-packs/{filename}")
                traversal = self.client.get("/api/resource-packs/..%2fsecret.geojson.gz")
        self.assertEqual(index.status_code, 200)
        self.assertEqual(index.json()["packs"][0]["pack_bytes"], len(b"compressed-pack"))
        self.assertEqual(index.json()["packs"][0]["feature_count"], 12)
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.content, b"compressed-pack")
        self.assertIn(traversal.status_code, {400, 404})


if __name__ == "__main__":
    unittest.main()
