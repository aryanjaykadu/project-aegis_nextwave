from datetime import datetime, timezone, timedelta
import unittest

from backend.feature_logic import community_trust, confidence_assessment


class AddedFeatureLogicTests(unittest.TestCase):
    def test_confidence_is_low_with_missing_inputs_and_outside_coverage(self):
        result = confidence_assessment(observed_fields=1, fresh_fields=1, target_in_region=False, trained_model=True,
                                       median_filled=True, weather_available=True, discharge_available=False)
        self.assertEqual(result['label'], 'low')
        self.assertIn('capped at medium', result['formula'])
        self.assertIn('not assessable', result['agreement'])

    def test_confidence_never_claims_high(self):
        result = confidence_assessment(observed_fields=3, fresh_fields=2, target_in_region=True, trained_model=True,
                                       median_filled=False, weather_available=True, discharge_available=True)
        self.assertEqual(result['label'], 'medium')

    def test_trust_score_uses_confirm_dispute_history_and_age(self):
        now = datetime.now(timezone.utc)
        report = {'created_at': (now - timedelta(hours=12)).isoformat(), 'reporter_id': 'hash-a',
                  'confirmations': 2, 'disputes': 1}
        rows = [report, {'reporter_id': 'hash-a', 'confirmations': 1, 'disputes': 0}]
        score, age = community_trust(report, rows, now=now)
        self.assertEqual(score, 52)
        self.assertEqual(age, 12)

    def test_trust_is_bounded(self):
        now = datetime.now(timezone.utc)
        report = {'created_at': (now - timedelta(days=60)).isoformat(), 'confirmations': 0, 'disputes': 100}
        score, _ = community_trust(report, [report], now=now)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)


if __name__ == '__main__':
    unittest.main()
