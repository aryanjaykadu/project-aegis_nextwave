"""Fast, network-free API regression tests for high-risk Aegis workflows."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend import main, operations, storage


class AegisApiTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_db = storage.DB_PATH
        storage.DB_PATH = Path(self.tempdir.name) / "test-aegis.db"
        self.original_auth = os.environ.get("AEGIS_AUTH_ENABLED")
        self.original_lan_mode = os.environ.get("AEGIS_LAN_MODE")
        os.environ["AEGIS_AUTH_ENABLED"] = "false"
        os.environ["AEGIS_LAN_MODE"] = "false"
        self.original_incidents = list(operations.INCIDENTS)
        self.original_alerts = list(operations.ALERTS)
        operations.INCIDENTS.clear()
        operations.ALERTS.clear()
        self.client = TestClient(main.app, client=("127.0.0.1", 50000))

    def tearDown(self):
        self.client.close()
        operations.INCIDENTS.clear()
        operations.INCIDENTS.extend(self.original_incidents)
        operations.ALERTS.clear()
        operations.ALERTS.extend(self.original_alerts)
        storage.DB_PATH = self.original_db
        if self.original_auth is None:
            os.environ.pop("AEGIS_AUTH_ENABLED", None)
        else:
            os.environ["AEGIS_AUTH_ENABLED"] = self.original_auth
        if self.original_lan_mode is None:
            os.environ.pop("AEGIS_LAN_MODE", None)
        else:
            os.environ["AEGIS_LAN_MODE"] = self.original_lan_mode
        self.tempdir.cleanup()

    def test_feedback_is_persisted_and_has_receipt_id(self):
        response = self.client.post(
            "/api/feedback",
            json={"category": "bug", "message": "Map source panel is clipped", "page": "/"},
        )
        self.assertEqual(response.status_code, 200)
        receipt = response.json()
        self.assertEqual(receipt["status"], "recorded")
        self.assertTrue(receipt["id"].startswith("FDB-"))
        self.assertEqual(storage.load("feedback")[0]["message"], "Map source panel is clipped")

    def test_feedback_rejects_empty_or_invalid_categories(self):
        too_short = self.client.post("/api/feedback", json={"message": "x"})
        invalid_category = self.client.post(
            "/api/feedback", json={"category": "dispatch", "message": "A sufficiently long report"}
        )
        self.assertEqual(too_short.status_code, 422)
        self.assertEqual(invalid_category.status_code, 422)

    def test_incident_idempotency_returns_existing_record(self):
        payload = {
            "description": "Water entered the lane",
            "lat": 25.59,
            "lon": 85.13,
            "idempotency_key": "test-stable-key-001",
        }
        first = self.client.post("/api/incidents", json=payload)
        second = self.client.post("/api/incidents", json=payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(len(operations.INCIDENTS), 1)

    def test_invalid_incident_coordinates_are_rejected(self):
        response = self.client.post(
            "/api/incidents",
            json={"description": "Invalid location", "lat": 250, "lon": 85},
        )
        self.assertEqual(response.status_code, 422)

    def test_network_clients_cannot_use_demo_operator_privileges(self):
        scope = {
            "type": "http",
            "method": "PATCH",
            "path": "/api/incidents/example",
            "headers": [],
            "query_string": b"",
            "server": ("aegis.local", 8000),
            "client": ("192.168.1.42", 50000),
            "scheme": "http",
        }
        with self.assertRaises(HTTPException) as raised:
            main.require_operator(main.Request(scope))
        self.assertEqual(raised.exception.status_code, 503)

    def test_simulation_response_is_bounded_and_explicitly_scenario_only(self):
        response = self.client.get("/api/simulate", params={"rainfall_delta": 50, "river_delta": 1})
        self.assertEqual(response.status_code, 200)
        self.assertIn(response.json()["severity"], {"low", "moderate", "high", "critical"})
        self.assertEqual(response.json()["risk_score"], 0.8)
        invalid = self.client.get("/api/simulate", params={"river_delta": 50})
        self.assertEqual(invalid.status_code, 422)

    def test_model_what_if_uses_training_ranges_and_rejects_unsupported_targets(self):
        response = self.client.get('/api/model/input-ranges')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['available'])
        ranges = response.json()['ranges']
        self.assertEqual(set(ranges), {
            'rainfall_local_mm', 'river_discharge_m3s', 'soil_moisture_local', 'rainfall_local_mm_sum7d'
        })
        inputs = {key: (value['min'] + value['max']) / 2 for key, value in ranges.items()}
        payload = {'lat': 25.5941, 'lon': 85.1376, 'inputs': inputs}
        result = self.client.post('/api/model/what-if', json=payload)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(set(result.json()['probabilities']), {'24', '48', '72'})
        self.assertIn('not a forecast', result.json()['notice'])
        outside = self.client.post('/api/model/what-if', json={**payload, 'lat': 30})
        self.assertEqual(outside.status_code, 422)
        unsupported = self.client.post('/api/model/what-if', json={**payload, 'inputs': {'river_level_m': 1.0}})
        self.assertEqual(unsupported.status_code, 422)

    def test_live_sms_test_requires_authentication(self):
        response = self.client.post("/api/notifications/test", json={"channel": "sms"})
        self.assertEqual(response.status_code, 503)

    def test_community_reports_are_rounded_signaled_and_deletable_by_reporter(self):
        payload = {"lat": 25.59419, "lon": 85.13769, "description": "Water across the lane",
                   "category": "water_level", "reporter_key": "author-report-key-000"}
        created = self.client.post('/api/observations', json=payload)
        self.assertEqual(created.status_code, 200)
        report = created.json()
        self.assertEqual(report['lat'], 25.594)
        self.assertEqual(report['lon'], 85.138)
        self.assertNotIn('reporter_id', report)
        vote = self.client.post(f"/api/observations/{report['id']}/signal",
                                json={"reporter_key":"another-reporter-key-000", "signal":"confirm"})
        self.assertEqual(vote.status_code, 200)
        self.assertEqual(vote.json()['confirmations'], 1)
        deleted = self.client.post('/api/observations/delete-own', json={"reporter_key":"author-report-key-000"})
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.json()['deleted'], 1)
        self.assertEqual(self.client.get('/api/observations').json()['observations'], [])

    def test_alert_requires_draft_then_approval_and_live_auth_for_delivery(self):
        draft = self.client.post(
            "/api/alerts",
            json={"title": "River update", "message": "Follow official district instructions.", "area": "Patna", "severity": "high", "issuing_authority": "District administration", "source_url": "https://example.gov.in/alert"},
        )
        self.assertEqual(draft.status_code, 200)
        alert_id = draft.json()["id"]
        blocked = self.client.post(f"/api/alerts/{alert_id}/send", json={})
        self.assertEqual(blocked.status_code, 409)
        self_approval = self.client.patch(f"/api/alerts/{alert_id}", json={"status": "approved"})
        self.assertEqual(self_approval.status_code, 409)
        operations.ALERTS[0]["created_by"] = "different-operator"
        approved = self.client.patch(f"/api/alerts/{alert_id}", json={"status": "approved"})
        self.assertEqual(approved.status_code, 200)
        delivery = self.client.post(f"/api/alerts/{alert_id}/send", json={})
        self.assertEqual(delivery.status_code, 503)
        self.assertEqual(operations.ALERTS[0]["status"], "approved")


if __name__ == "__main__":
    unittest.main()
