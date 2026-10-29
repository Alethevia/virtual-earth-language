#!/usr/bin/env python3
"""Post-hoc accounting of frozen 2024 predictions. No model fitting or tuning."""
from pathlib import Path
import numpy as np
import pandas as pd
import quant_geo_phase1 as q


def summarize(frame):
    n = len(frame)
    return dict(n=n, b2_mae=float(frame.e2.mean()) if n else None,
                b3_mae=float(frame.e3.mean()) if n else None,
                gain_mw=float(frame.gain.mean()) if n else None,
                gain_sum_mw=float(frame.gain.sum()),
                b2_underprediction=float(frame.u2.mean()) if n else None,
                b3_underprediction=float(frame.u3.mean()) if n else None,
                b2_overprediction=float(frame.o2.mean()) if n else None,
                b3_overprediction=float(frame.o3.mean()) if n else None,
                b3_better_days=int((frame.gain > 0).sum()))


def episode_ids(dates):
    """A missing or non-high-load calendar day breaks an episode."""
    return pd.Series(dates, index=dates).diff().ne(pd.Timedelta(days=1)).cumsum()


def main(root: Path = q.ROOT):
    q.validate_analysis_inputs(root)
    evidence = root / 'qa' / 'empirical_20261029'
    pred = pd.read_csv(evidence / 'test_predictions.csv', index_col='date', parse_dates=True)
    data = pd.read_csv(root / 'prepared' / 'daily.csv', index_col='date', parse_dates=True)
    report = __import__('json').loads((evidence / 'empirical_report.json').read_text())
    if report['data_sha256'] != q.sha256(root / 'prepared' / 'daily.csv'):
        raise ValueError('Daily data do not match the frozen prediction experiment.')
    np.testing.assert_allclose(pred.actual, data.loc[pred.index, 'peak'], rtol=0, atol=1e-8)
    cfg = q.read_protocol(root)
    threshold = report['high_load_threshold_training_only']
    out = root / 'qa' / 'diagnostics_20261029'; out.mkdir(exist_ok=True)
    summary, monthly, episodes, daily = [], [], [], []
    for family in ('hgb', 'ridge'):
        frame = pred[['actual']].copy()
        frame['p2'] = pred[family + '__B2_distribution']
        frame['p3'] = pred[family + '__B3_site_identity']
        for k in (2, 3):
            error = frame.actual - frame['p' + str(k)]
            frame['e' + str(k)] = error.abs()
            frame['u' + str(k)] = error.clip(lower=0)
            frame['o' + str(k)] = (-error).clip(lower=0)
        frame['gain'] = frame.e2 - frame.e3
        frame['high_load'] = frame.actual >= threshold
        tail = frame[frame.high_load]
        for name, subset in [('all', frame), ('non_high', frame[~frame.high_load]), ('high', tail)]:
            summary.append(dict(family=family, subset=name, **summarize(subset)))
        for month in range(1, 13):
            for name, subset in [('all', frame), ('high', tail)]:
                monthly.append(dict(family=family, month=month, subset=name,
                                    **summarize(subset[subset.index.month == month])))
        for _, subset in tail.groupby(episode_ids(tail.index)):
            episodes.append(dict(family=family, start=str(subset.index.min().date()),
                                 end=str(subset.index.max().date()), **summarize(subset)))
        frame['family'] = family
        daily.append(frame)
    pd.DataFrame(summary).to_csv(out / 'error_accounting.csv', index=False)
    pd.DataFrame(monthly).to_csv(out / 'monthly.csv', index=False)
    pd.DataFrame(episodes).to_csv(out / 'high_load_episodes.csv', index=False)
    pd.concat(daily).to_csv(out / 'daily_errors.csv', index_label='date')
    # Preserve excluded days, including their known load, rather than calling them low risk.
    test = data.loc[cfg['test_start']:cfg['test_end']]
    missing = test.loc[~test.index.isin(pred.index)].copy()
    missing['known_high_load'] = missing.peak.ge(threshold).where(missing.peak.notna())
    missing.to_csv(out / 'excluded_days.csv', index_label='date')
    accounting = pd.DataFrame(summary)
    for family in ('hgb', 'ridge'):
        rows = accounting[accounting.family == family].set_index('subset')
        assert rows.loc['all', 'n'] == rows.loc[['non_high', 'high'], 'n'].sum()
        np.testing.assert_allclose(rows.loc['all', 'gain_sum_mw'],
                                   rows.loc[['non_high', 'high'], 'gain_sum_mw'].sum(), atol=1e-8)
    q.dump_json(out / 'provenance.json', dict(
        status='POST_HOC_DESCRIPTIVE_ONLY', model_fits=0,
        source_sha256=q.sha256(Path(__file__)),
        predictions_sha256=q.sha256(evidence / 'test_predictions.csv'),
        daily_sha256=q.sha256(root / 'prepared' / 'daily.csv'),
        threshold_mw=threshold, excluded_days=len(missing),
        excluded_known_high_load_days=int(missing.known_high_load.fillna(False).sum()),
        limitations=['Observed 2024 after the original evaluation; no confirmatory subgroup tests.',
                     'Error accounting does not establish a physical or causal mechanism.',
                     'Episodes are consecutive observed high-load days, not independent samples.',
                     'All months and episodes retained; no selection of favorable dates.']))
    print(accounting.to_string(index=False))
    print(pd.DataFrame(episodes).to_string(index=False))


if __name__ == '__main__':
    main()
