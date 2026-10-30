#!/usr/bin/env python3
"""Independently recompute ISO-NE scores and calendar-bootstrap summaries."""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent / 'isone_v1'


def main():
    cfg = json.loads((ROOT/'protocol.json').read_text())
    status = json.loads((ROOT/'execution_status.json').read_text())
    data = pd.read_csv(ROOT/'qa/daily_model_input.csv', index_col='date', parse_dates=True)
    pred = pd.read_csv(ROOT/'qa/test_predictions.csv', index_col='date', parse_dates=True)
    metrics = pd.read_csv(ROOT/'qa/metrics.csv')
    intervals = json.loads((ROOT/'qa/block_intervals.json').read_text())
    cutoff = float(np.quantile(data.loc['2019-01-01':'2022-12-31', 'peak'].dropna(), .9))
    np.testing.assert_allclose(cutoff, status['threshold_mw'], rtol=0, atol=1e-9)
    flags = pd.read_csv(ROOT/'qa/daily_coverage.csv', index_col='date', parse_dates=True)
    expected = flags.loc['2024-01-01':'2025-12-31'].query('usable').index
    assert pred.index.equals(expected) and pred.index.is_unique
    np.testing.assert_allclose(pred.actual, data.loc[pred.index, 'peak'], rtol=0, atol=1e-9)
    assert len(pred.columns) == 14 and len(metrics) == 26 and len(intervals) == 12
    maximum = 0.0
    for row in metrics.to_dict('records'):
        p = pred.loc[str(row['year'])]
        actual = p.actual.to_numpy(); estimate = p[row['family']+'__'+row['representation']].to_numpy()
        assert np.isfinite(actual).all() and np.isfinite(estimate).all()
        error = actual-estimate; high = actual >= cutoff
        values = {'MAE': np.mean(abs(error)), 'RMSE': np.sqrt(np.mean(error*error)),
                  'high_load_MAE': np.mean(abs(error[high])),
                  'high_load_underprediction': np.mean(np.clip(error[high], 0, None))}
        assert len(actual) == row['n'] and int(high.sum()) == row['high_load_n']
        for key, value in values.items():
            maximum = max(maximum, abs(value-row[key]))
            np.testing.assert_allclose(value, row[key], rtol=0, atol=1e-8)
    bootstrap_maximum = 0.0
    for row in intervals:
        year, family, block = row['year'], row['family'], row['block_days']
        p = pred.loc[str(year)]
        d = abs(p.actual-p[family+'__B2_distribution'])-abs(p.actual-p[family+'__B3_site_identity'])
        d[p.actual < cutoff] = np.nan
        days = pd.date_range(f'{year}-01-01', f'{year}-12-31')
        a = d.reindex(days).to_numpy(); n = len(a)
        rng = np.random.default_rng(cfg['seed'])
        starts = rng.integers(0, n, (cfg['bootstrap_replicates'], math.ceil(n/block)))
        positions = ((starts[:, :, None] + np.arange(block)) % n).reshape(len(starts), -1)[:, :n]
        samples = a[positions]; counts = np.isfinite(samples).sum(axis=1)
        means = np.nansum(samples[counts > 0], axis=1)/counts[counts > 0]
        expected_values = [np.nanmean(a), *np.quantile(means, [.025, .975])]
        stored = [row['paired_mean_improvement'], row['lower_95'], row['upper_95']]
        bootstrap_maximum = max(bootstrap_maximum, float(np.max(np.abs(np.array(expected_values)-stored))))
        np.testing.assert_allclose(expected_values, stored, rtol=0, atol=1e-8)
        assert len(means) == row['effective_bootstrap_replicates'] and n == row['calendar_days']
    # Check the stored input/source hashes without importing the producer module.
    for manifest, base in [(ROOT/'input_lock.json', ROOT), (ROOT/'lock.json', ROOT.parent)]:
        expected_hashes = dict(json.loads(manifest.read_text())['sha256'])
        if manifest.name == 'lock.json':
            amendment = json.loads((ROOT/'amendment_01.json').read_text())
            assert expected_hashes['isone_replication.py'] == amendment['original_source_sha256']
            expected_hashes['isone_replication.py'] = amendment['amended_source_sha256']
        for name, digest in expected_hashes.items():
            assert hashlib.sha256((base/name).read_bytes()).hexdigest() == digest, name
    result = dict(status='VERIFIED', metric_rows=26, error_metrics_recomputed=104,
                  interval_summaries_recomputed=12, interval_statistics_checked=36,
                  metric_max_abs_difference_mw=maximum, interval_max_abs_difference_mw=bootstrap_maximum,
                  exact_test_dates_and_counts=True, source_and_input_hashes_verified=True,
                  limitation='Independent arithmetic implementation, not an independent investigator or raw measurement audit.')
    (ROOT/'qa/independent_verification.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
