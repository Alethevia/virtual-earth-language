#!/usr/bin/env python3
"""Locked temporal replication using unchanged 2023-selected model parameters.

Run after reading replication_2025/PLAN.md. Original 2024 artifacts are read-only.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from threadpoolctl import threadpool_limits

import quant_geo_phase1 as q
import verify_intervals as intervals

ROOT = q.ROOT / 'replication_2025'


def check_lock(root=ROOT):
    lock = json.loads((root / 'lock.json').read_text())
    for name, digest in lock['sha256'].items():
        if q.sha256(q.ROOT / name) != digest:
            raise ValueError('Locked input changed: ' + name)
    cfg = q.read_protocol(root)
    original = q.read_protocol(q.ROOT)
    for key in original:
        if key not in lock['allowed_protocol_changes'] and cfg[key] != original[key]:
            raise ValueError('Unplanned protocol change: ' + key)
    return lock


def download(root=ROOT):
    check_lock(root)
    raw = root / 'raw'; raw.mkdir(parents=True, exist_ok=True)
    old = json.loads((q.ROOT / 'qa/empirical_20261029/download_manifest.json').read_text())
    if not (raw / 'download_manifest.json').exists():
        for row in old['files']:
            source = q.ROOT / 'raw' / row['file']
            if source.exists() and q.sha256(source) == row['sha256']:
                shutil.copy2(source, raw / row['file'])
        # Entries with missing files will be downloaded by the original downloader.
        q.dump_json(raw / 'download_manifest.json', old)
    q.download(root)
    downloaded = json.loads((raw / 'download_manifest.json').read_text())
    hashes = {r['file']: r['sha256'] for r in downloaded['files']}
    if any(hashes[r['file']] != r['sha256'] for r in old['files']):
        raise ValueError('Historical archive changed; stop rather than silently revise the baseline.')


def prepare(root=ROOT):
    check_lock(root)
    q.prepare(root)
    reference = pd.read_csv(q.ROOT / 'prepared/daily.csv', index_col='date', parse_dates=True)
    if q.sha256(q.ROOT / 'prepared/daily.csv') != json.loads(
            (q.ROOT / 'qa/empirical_20261029/empirical_report.json').read_text())['data_sha256']:
        raise ValueError('Original prepared data changed.')
    extended = pd.read_csv(root / 'prepared/daily.csv', index_col='date', parse_dates=True)
    pd.testing.assert_frame_equal(reference, extended.loc[reference.index], check_exact=False, rtol=0, atol=1e-8)


def verify(root=ROOT):
    lock = check_lock(root)
    intervals.DATES = lock['interval_dates']
    intervals.main(root)


def verify_predictions(actual, expected):
    if not actual.index.equals(expected.index) or list(actual.columns) != list(expected.columns):
        raise ValueError('2024 reproduction dates or model columns differ.')
    np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-7)
    return float(np.max(np.abs(actual.to_numpy() - expected.to_numpy())))


def analyse(root=ROOT):
    lock = check_lock(root)
    provenance = q.validate_analysis_inputs(root)
    cfg = q.read_protocol(root)
    data = pd.read_csv(root / 'prepared/daily.csv', index_col='date', parse_dates=True)
    data = data.reindex(pd.date_range(cfg['start'], cfg['end'], freq='D'))
    weights = q.fit_exposure_weights(data, cfg)
    features = q.wx_features(data, cfg, weights)
    valid = data.peak.notna() & features['B3_site_identity'].notna().all(axis=1)
    masks = q.split_masks(data.index, cfg)
    coverage = {k: dict(eligible=int(m.sum()), usable=int((m & valid).sum()),
                        fraction=float((m & valid).sum()/m.sum())) for k, m in masks.items()}
    out = root / 'results'; out.mkdir(exist_ok=True)
    q.dump_json(out / 'coverage.json', coverage)
    if any(v['fraction'] < cfg['minimum_usable_fraction_each_split'] for v in coverage.values()):
        raise ValueError('Coverage failed the unchanged 90% requirement.')
    train = valid & (masks['train'] | masks['validation'])
    test = valid & masks['test']
    threshold = float(data.loc[masks['train'], 'peak'].quantile(cfg['tail_quantile_training_only']))
    original = q.ROOT / 'qa/empirical_20261029'
    selections = json.loads((original / 'model_selection.json').read_text())
    previous = pd.read_csv(original / 'test_predictions.csv', index_col='date', parse_dates=True)
    reproduced = pd.DataFrame({'actual': data.loc[previous.index, 'peak']})
    pred = pd.DataFrame({'actual': data.loc[test, 'peak']})
    metrics = []
    for label, selection in selections.items():
        family, representation = label.split('__')
        if representation.startswith('identity_scramble_'):
            seed = int(representation.rsplit('_', 1)[1])
            x = q.wx_features(data, cfg, weights, permutation_seed=seed)['B3_site_identity']
        else:
            x = features[representation]
        if x.shape[1] != selection['features']:
            raise ValueError('Feature schema changed: ' + label)
        models = [m for p, m in q.model_candidates(family, cfg['seed']) if p == selection['parameters']]
        if len(models) != 1:
            raise ValueError('Saved model parameters do not match the original grid.')
        model = models[0]
        model.fit(x.loc[train], data.loc[train, 'peak'])
        reproduced[label] = model.predict(x.loc[previous.index])
        pred[label] = model.predict(x.loc[test])
        print('fitted fixed pipeline', label, flush=True)
    # Fail before reporting replication metrics if any old prediction changed.
    max_difference = verify_predictions(reproduced, previous)
    for label in selections:
        family, representation = label.split('__')
        metrics.append(dict(family=family, representation=representation,
                            **q.score(pred.actual.to_numpy(), pred[label].to_numpy(), threshold)))
    boot = []
    for family in ('hgb', 'ridge'):
        e2 = (pred.actual - pred[family + '__B2_distribution']).abs()
        e3 = (pred.actual - pred[family + '__B3_site_identity']).abs()
        diff = (e2 - e3).where(pred.actual >= threshold)
        for block in cfg['bootstrap_block_days']:
            boot.append(dict(family=family, **q.paired_block_interval(
                diff, block, cfg['bootstrap_replicates'], cfg['seed'])))
    metric = pd.DataFrame(metrics)
    indexed = metric.set_index(['family', 'representation'])
    b2, b3 = [indexed.loc[('hgb', x)] for x in ('B2_distribution', 'B3_site_identity')]
    r2, r3 = [indexed.loc[('ridge', x)] for x in ('B2_distribution', 'B3_site_identity')]
    gain = float(1 - b3.high_load_MAE / b2.high_load_MAE)
    primary = next(r for r in boot if r['family'] == 'hgb' and r['block_days'] == 14)
    scramble = metric[metric.representation.str.startswith('identity_scramble_')]
    conditions = dict(enough_tail_days=int(b3.high_load_n) >= cfg['minimum_test_high_load_days'],
        at_least_five_percent_tail_gain=gain >= cfg['practical_screen_relative_tail_MAE_gain'],
        primary_interval_positive=primary['lower_95'] > 0,
        ridge_tail_direction_agrees=bool(r3.high_load_MAE < r2.high_load_MAE),
        beats_four_of_five_scrambles=int((scramble.high_load_MAE > b3.high_load_MAE).sum()) >= 4,
        overall_MAE_not_more_than_two_percent_worse=bool(b3.MAE <= b2.MAE * 1.02))
    metric.to_csv(out / 'metrics.csv', index=False)
    pred.to_csv(out / 'test_predictions.csv', index_label='date')
    q.dump_json(out / 'block_intervals.json', boot)
    q.dump_json(out / 'model_selection.json', selections)
    q.dump_json(out / 'empirical_report.json', dict(
        status='LOCKED_TEMPORAL_REPLICATION', model_fits=13, new_hyperparameter_searches=0,
        training_and_refit_end='2023-12-31', test_year=2025,
        high_load_threshold_training_only=threshold, exposure_weights=dict(zip(cfg['stations'], map(float, weights))),
        primary_relative_tail_MAE_improvement=gain, screen_conditions=conditions,
        screening_pass=all(conditions.values()), reproduced_2024_max_abs_difference_mw=max_difference,
        plan_lock=lock, runner_sha256=q.sha256(Path(__file__)), preparation_provenance=provenance,
        interval_evidence_sha256=q.sha256(root / 'qa/interval_convention_20261029.json'),
        versions=dict(python=sys.version.split()[0], numpy=np.__version__, pandas=pd.__version__, sklearn=sklearn.__version__),
        limitations=['Planned after observing 2024; not an external preregistration.',
                     '2025 was not analysed by this workflow before the lock; user-wide prior access is not asserted.',
                     'Same NYISO system and same model family; not independent geographic replication.',
                     'Realized same-day weather and sequential observed load lags; not day-ahead forecasting.',
                     'Archives can be revised; only the current frozen download is evaluated.',
                     'No retuning, selected subgroup claims, causal claims or novelty claims.']))
    print(metric.to_string(index=False)); print(conditions)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command', choices=['download', 'prepare', 'verify', 'analyse'])
    args = ap.parse_args()
    with threadpool_limits(limits=1):
        globals()[args.command]()
