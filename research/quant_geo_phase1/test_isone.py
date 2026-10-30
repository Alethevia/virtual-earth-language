import unittest
import numpy as np
import pandas as pd
import isone_replication as iso


class ISOTimingAndIsolationTests(unittest.TestCase):
    def frame(self, year=2024):
        days = pd.date_range(f'{year}-01-01', f'{year}-12-31')
        rows = []
        for date in days:
            labels = list(range(1, 25))
            if year >= 2024 and iso.q.expected_hours(date) == 23:
                labels.remove(2)
            if year >= 2024 and iso.q.expected_hours(date) == 25:
                labels.insert(2, '02X')
            rows.extend(dict(Date=date, Hr_End=h, RT_Demand=1.) for h in labels)
        return pd.DataFrame(rows)

    def test_dst_is_published_24_hour_convention(self):
        data = iso.validate_hours(self.frame(2019), 2019)
        self.assertEqual(len(data.loc['2019-03-10']), 24)
        self.assertEqual(len(data.loc['2019-11-03']), 24)
        self.assertEqual(len(data), 365*24)

    def test_native_dst_and_harmonization(self):
        data = iso.validate_hours(self.frame(), 2024)
        self.assertEqual(len(data.loc['2024-03-10']), 23)
        self.assertEqual(len(data.loc['2024-11-03']), 25)
        numeric = data[['RT_Demand']].copy()
        numeric.loc[(pd.Timestamp('2024-03-10'), '01'), 'RT_Demand'] = 5.
        numeric.loc[(pd.Timestamp('2024-11-03'), '02X'), 'RT_Demand'] = 9.
        output = iso.normalize_load_hours(numeric, 2024)
        self.assertEqual(len(output), 366*24)
        self.assertEqual(output.loc[(pd.Timestamp('2024-03-10'), '02'), 'RT_Demand'], 3.)
        self.assertEqual(output.loc[(pd.Timestamp('2024-11-03'), '02'), 'RT_Demand'], 5.)

    def test_extra_hour_on_wrong_day_stops(self):
        frame = self.frame()
        frame.loc[(frame.Date == pd.Timestamp('2024-01-02')) & (frame.Hr_End == 2), 'Hr_End'] = '02X'
        with self.assertRaisesRegex(ValueError, 'Missing or unexpected'):
            iso.validate_hours(frame, 2024)

    def test_missing_hour_stops(self):
        with self.assertRaisesRegex(ValueError, 'Missing'):
            iso.validate_hours(self.frame().iloc[1:], 2024)

    def test_duplicate_hour_stops(self):
        frame = self.frame()
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            iso.validate_hours(pd.concat([frame, frame.iloc[:1]]), 2024)

    def test_wrong_year_stops(self):
        with self.assertRaisesRegex(ValueError, 'Wrong annual'):
            iso.validate_hours(self.frame(), 2025)

    def test_sum_before_max(self):
        idx = pd.MultiIndex.from_product([[pd.Timestamp('2024-01-01')], [1, 2]], names=['date', 'hour'])
        result = iso.aggregate_load(pd.DataFrame({'ME': [10., 1.], 'NH': [1., 10.]}, index=idx))
        self.assertEqual(result.peak.iloc[0], 11.)
        self.assertEqual(result.zone_ME.iloc[0], 5.5)

    def test_exposure_never_uses_validation_or_test(self):
        cfg = dict(start='2019-01-01', train_end='2022-12-31', stations={'A': {'zones': ['ME']}, 'B': {'zones': ['NH']}})
        frame = pd.DataFrame({'zone_ME': [1., 10000., 90000.], 'zone_NH': [3., 1., 1.]}, index=pd.to_datetime(['2022-12-31', '2023-01-01', '2025-01-01']))
        np.testing.assert_allclose(iso.q.fit_exposure_weights(frame, cfg), [.25, .75])

    def test_bootstrap_full_year_even_when_boundary_days_missing(self):
        diff = pd.Series([2., 4.], index=pd.to_datetime(['2025-06-01', '2025-06-02']))
        cfg = dict(bootstrap_replicates=100, seed=11)
        result = iso.full_calendar_interval(diff, 2025, 14, cfg)
        self.assertEqual(result['calendar_days'], 365)
        self.assertEqual(result['paired_mean_improvement'], 3.)
        with self.assertRaisesRegex(ValueError, 'Invalid'):
            iso.full_calendar_interval(diff, 2024, 14, cfg)


if __name__ == '__main__':
    unittest.main()
