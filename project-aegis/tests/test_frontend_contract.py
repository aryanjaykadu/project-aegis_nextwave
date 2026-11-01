"""Static contracts for core safety, mobile, and offline frontend controls."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")
FEATURES = (Path(__file__).resolve().parents[1] / "frontend" / "aegis-features.js").read_text(encoding="utf-8")
WORKER = (Path(__file__).resolve().parents[1] / "frontend" / "service-worker.js").read_text(encoding="utf-8")


class FrontendContractTests(unittest.TestCase):
    def test_scenario_sliders_keep_native_controls_and_original_contract(self):
        rain = re.search(r'<input[^>]*id="rain-slider"[^>]*>', HTML)
        river = re.search(r'<input[^>]*id="river-slider"[^>]*>', HTML)
        self.assertIsNotNone(rain)
        self.assertIsNotNone(river)
        self.assertIn('min="0" max="200" value="25"', rain.group(0))
        self.assertIn("rain-output", rain.group(0))
        self.assertIn('min="0" max="5" step="0.1" value="0.5"', river.group(0))
        self.assertIn("river-output", river.group(0))

    def test_phone_layout_keeps_zoom_accessibility_and_safe_area(self):
        self.assertIn("viewport-fit=cover", HTML)
        self.assertNotIn("user-scalable=no", HTML)
        self.assertRegex(HTML, r"@media\s*\(max-width:\s*768px\)")
        self.assertIn("env(safe-area-inset-bottom)", HTML)

    def test_operator_feedback_and_timeline_controls_are_present(self):
        for control_id in (
            "operator-auth-dialog",
            "alert-dialog",
            "feedback-dialog",
            "feedback-inbox-dialog",
            "evidence-dialog",
        ):
            self.assertIn(f'id="{control_id}"', HTML)
        self.assertIn("sessionStorage", HTML)
        self.assertIn("showEvidenceTimeline", HTML)

    def test_offline_queue_uses_stable_idempotency_keys(self):
        self.assertIn("aegis-pending-incidents", HTML)
        self.assertIn("newIdempotencyKey()", HTML)
        self.assertIn("writePendingReports", HTML)

    def test_forecast_dialog_separates_provider_model_and_aegis_estimate(self):
        for required in (
            'id="forecast-dialog"',
            'id="forecast-official-warning"',
            'id="forecast-model-meta"',
            'id="forecast-aegis-estimate"',
            'id="forecast-time-slider"',
            "This does not mean there is no risk.",
            "No spatial forecast layer",
            "/api/weather-forecast",
        ):
            self.assertIn(required, HTML)

    def test_forecast_display_has_retry_and_offline_cache_path(self):
        self.assertIn("OFFLINE CACHED", HTML)
        self.assertIn("No cached forecast for this location", HTML)
        self.assertIn('onclick="loadForecast()">RETRY', HTML)

    def test_resource_browser_has_expanded_categories_and_source_links(self):
        for value in ("blood_bank", "ambulance", "fire_station", "ev_charging", "railway_station", "substation"):
            self.assertIn(value, FEATURES)
        self.assertIn("DOWNLOAD FOR OFFLINE USE", FEATURES)
        self.assertIn("aegis-resource-pack-index-v1", FEATURES)
        self.assertIn("aegis-region-packs-v1", WORKER)
        self.assertIn("CALL · MAP DATA", FEATURES)
        self.assertIn("SOURCE", FEATURES)


if __name__ == "__main__":
    unittest.main()
