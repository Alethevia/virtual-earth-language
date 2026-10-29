"""Synthetic safeguards; not empirical research results."""
import unittest
import numpy as np
import pandas as pd
from diagnose_errors import episode_ids, summarize
from replicate_2025 import check_lock, verify_predictions


class FollowupTests(unittest.TestCase):
    def test_missing_calendar_day_breaks_episode(self):
        dates = pd.to_datetime(['2024-06-01', '2024-06-02', '2024-06-04'])
        self.assertEqual(episode_ids(dates).tolist(), [1, 1, 2])

    def test_under_over_accounting(self):
        frame = pd.DataFrame(dict(e2=[3., 2.], e3=[1., 4.], gain=[2., -2.],
                                  u2=[3., 0.], u3=[1., 0.], o2=[0., 2.], o3=[0., 4.]))
        result = summarize(frame)
        self.assertEqual(result['gain_sum_mw'], 0)
        self.assertEqual(result['b2_mae'], result['b2_underprediction'] + result['b2_overprediction'])

    def test_modified_predictions_rejected(self):
        frame = pd.DataFrame({'actual': [1.], 'model': [2.]}, index=pd.to_datetime(['2024-01-01']))
        self.assertEqual(verify_predictions(frame, frame.copy()), 0)
        changed = frame.copy(); changed['model'] += 1
        with self.assertRaises(AssertionError):
            verify_predictions(changed, frame)
        with self.assertRaises(ValueError):
            verify_predictions(frame.rename(columns={'model': 'different'}), frame)

    def test_locked_inputs_match(self):
        self.assertEqual(check_lock()['test_year'], 2025)


if __name__ == '__main__':
    unittest.main()
