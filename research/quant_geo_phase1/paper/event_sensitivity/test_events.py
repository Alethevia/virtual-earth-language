import unittest
from analyse import episodes, summarize


def row(day, gain, actual=10):
    return dict(date=day, actual=actual, **{f'{f}__{b}':actual-(gain if b=='B2_distribution' else 0)
        for f in ('hgb','ridge') for b in ('B2_distribution','B3_site_identity')})


class EventTests(unittest.TestCase):
    def test_missing_and_low_dates_break_runs(self):
        rows=[row('2024-01-01',1),row('2024-01-02',1),row('2024-01-04',1),
              row('2024-01-05',1,actual=1),row('2024-01-06',1)]
        self.assertEqual([len(r) for r in episodes(rows,10)],[2,1,1])

    def test_deletion_uses_remaining_days_not_event_weights(self):
        runs=[[row('2024-01-01',2),row('2024-01-02',4)],[row('2024-02-01',9)]]
        summary, detail=summarize(runs,'hgb')
        self.assertEqual(summary['mean_gain_mw'],5)
        self.assertEqual(summary['equal_run_mean_gain_mw'],6)
        self.assertEqual([r['remaining_mean_gain_mw'] for r in detail],[9,3])

    def test_duplicate_and_nan_rejected(self):
        with self.assertRaises(ValueError):
            episodes([row('2024-01-01',1)]*2,10)
        with self.assertRaises(ValueError):
            episodes([row('2024-01-01',float('nan'))],10)

    def test_one_run_cannot_be_deleted(self):
        with self.assertRaises(ValueError):
            summarize([[row('2024-01-01',1)]],'hgb')


if __name__=='__main__':
    unittest.main()
