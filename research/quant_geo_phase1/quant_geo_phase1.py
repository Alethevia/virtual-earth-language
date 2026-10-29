#!/usr/bin/env python3
"""Quantitative geography experiment 001, with explicit empirical/synthetic separation.

Commands:
  python quant_geo_phase1.py download
  python quant_geo_phase1.py prepare
  python quant_geo_phase1.py analyse
  python -m unittest -v test_quant_geo_phase1.py

The first three commands need official downloaded data. Empirical reports require
verified provenance. Tests use artificial fixtures only. Same-day realized weather
makes this a retrospective conditional-prediction experiment, NOT a trading or
operational day-ahead forecasting test. Read PROTOCOL.md before interpreting output.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import numpy as np
import pandas as pd
import requests
import sklearn
from pandas.tseries.holiday import USFederalHolidayCalendar
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parent


def read_protocol(root: Path = ROOT) -> dict:
    return json.loads((root / 'protocol.json').read_text(encoding='utf-8'))


def dump_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def zone_name(value: str) -> str:
    return re.sub(r'[^A-Z0-9]', '', str(value).upper())


def expected_hours(date: pd.Timestamp, tz: str = 'America/New_York') -> int:
    day = pd.Timestamp(date).normalize()
    a = day.tz_localize(tz).tz_convert('UTC')
    b = (day + pd.Timedelta(days=1)).tz_localize(tz).tz_convert('UTC')
    return int((b - a) / pd.Timedelta(hours=1))


def source_requests(cfg: dict):
    first, last = pd.Timestamp(cfg['start']), pd.Timestamp(cfg['end'])
    for month in pd.date_range(first, last, freq='MS'):
        name = f'{month:%Y%m}01palIntegrated_csv.zip'
        yield 'nyiso', f'https://mis.nyiso.com/public/csv/palIntegrated/{name}', f'nyiso_{month:%Y%m}.zip'
    for key, station in cfg['stations'].items():
        for year in range(first.year, last.year + 1):
            # Include the following UTC morning to cover the last New York day.
            query = urlencode(dict(dataset='global-hourly', stations=station['id'],
                startDate=f'{year}-01-01T00:00:00Z', endDate=f'{year+1}-01-01T05:59:59Z',
                dataTypes='TMP,DEW', format='csv', includeStationName='true',
                includeStationLocation='true'))
            yield 'noaa', 'https://www.ncei.noaa.gov/access/services/data/v1?' + query, f'noaa_{key}_{year}.csv'


def validate_payload(kind: str, content: bytes) -> None:
    if kind == 'nyiso':
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            names = [n for n in z.namelist() if n.lower().endswith('.csv')]
            if not names:
                raise ValueError('NYISO ZIP contains no CSV members.')
            sample = pd.read_csv(z.open(names[0]), nrows=3)
            required = {'Time Stamp', 'Time Zone', 'Name', 'Integrated Load'}
    else:
        sample = pd.read_csv(io.BytesIO(content), nrows=3)
        required = {'DATE', 'TMP', 'DEW'}
    if sample.empty or not required.issubset(sample.columns):
        raise ValueError(f'{kind}: empty data or changed schema; got {list(sample.columns)}')


def download(root: Path = ROOT) -> None:
    cfg = read_protocol(root)
    raw = root / 'raw'; raw.mkdir(parents=True, exist_ok=True)
    manifest_path = raw / 'download_manifest.json'
    old = json.loads(manifest_path.read_text()) if manifest_path.exists() else {'files': []}
    known = {row['file']: row for row in old.get('files', [])}
    manifest = {'status': 'INCOMPLETE', 'protocol_sha256': sha256(root / 'protocol.json'), 'files': []}
    session = requests.Session()
    session.headers['User-Agent'] = 'QuantGeoResearch001/1.0 (public academic data access)'
    try:
        for kind, url, name in source_requests(cfg):
            path = raw / name
            if path.exists() and name in known and sha256(path) == known[name]['sha256']:
                validate_payload(kind, path.read_bytes())
                manifest['files'].append(known[name]); print('cached', name, flush=True)
                continue
            error = None
            for attempt in range(3):
                try:
                    response = session.get(url, timeout=(15, 100))
                    response.raise_for_status()
                    validate_payload(kind, response.content)
                    temp = path.with_suffix(path.suffix + '.part')
                    temp.write_bytes(response.content); temp.replace(path)
                    row = dict(file=name, source=url, final_url=response.url, bytes=path.stat().st_size,
                               sha256=sha256(path), retrieved_utc=datetime.now(timezone.utc).isoformat())
                    manifest['files'].append(row)
                    dump_json(manifest_path, manifest)
                    print('downloaded', name, path.stat().st_size, flush=True)
                    error = None
                    break
                except (requests.RequestException, ValueError, zipfile.BadZipFile, pd.errors.ParserError) as exc:
                    error = exc
                    if attempt < 2:
                        time.sleep(2 ** attempt)
            if error is not None:
                raise RuntimeError(f'Download failed for {name}; no substitute or invented values were used: {error}')
        manifest['status'] = 'COMPLETE'
        dump_json(manifest_path, manifest)
    except Exception as exc:
        manifest['error'] = str(exc); dump_json(manifest_path, manifest)
        raise


def parse_nyiso_frame(frame: pd.DataFrame) -> pd.DataFrame:
    required = {'Time Stamp', 'Time Zone', 'Name', 'Integrated Load'}
    if not required.issubset(frame):
        raise ValueError('Missing NYISO fields.')
    offset = frame['Time Zone'].astype(str).str.strip().map({'EST': 5, 'EDT': 4})
    if offset.isna().any():
        raise ValueError('Unrecognized NYISO time-zone label; do not infer silently.')
    local_naive = pd.to_datetime(frame['Time Stamp'], errors='raise')
    utc = (local_naive + pd.to_timedelta(offset, unit='h')).dt.tz_localize('UTC')
    values = pd.to_numeric(frame['Integrated Load'], errors='coerce')
    if (values.dropna() < 0).any():
        raise ValueError('Negative load encountered; inspect raw data rather than clip.')
    return pd.DataFrame({'utc': utc, 'zone': frame['Name'].map(zone_name), 'load': values})


def daily_load(hourly: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, dict]:
    zones = [z for s in cfg['stations'].values() for z in s['zones']]
    if len(zones) != len(set(zones)):
        raise ValueError('Each load zone must belong to exactly one weather proxy.')
    frame = hourly[hourly.zone.isin(zones)].copy()
    if set(frame.zone.unique()) != set(zones):
        raise ValueError(f'Missing required zones: {set(zones) - set(frame.zone.unique())}')
    counts = frame.groupby(['utc', 'zone']).load.nunique(dropna=False)
    if (counts > 1).any():
        raise ValueError('Conflicting duplicate load values; cannot choose a revision silently.')
    n_duplicate = int(frame.duplicated(['utc', 'zone']).sum())
    frame = frame.drop_duplicates(['utc', 'zone'])
    wide = frame.pivot(index='utc', columns='zone', values='load').sort_index().reindex(columns=zones)
    idx = pd.date_range(cfg['start'], cfg['end'], freq='D')
    local_dates = wide.index.tz_convert(cfg['time_zone']).tz_localize(None).normalize()
    complete = wide.notna().all(axis=1)
    total = wide.sum(axis=1, min_count=len(zones)).where(complete)
    peak = total.groupby(local_dates).max().reindex(idx)
    hours = complete.groupby(local_dates).sum().reindex(idx, fill_value=0)
    expected = pd.Series([expected_hours(d, cfg['time_zone']) for d in idx], index=idx)
    good = hours.eq(expected)
    out = pd.DataFrame({'peak': peak.where(good), 'load_hours': hours, 'expected_hours': expected}, index=idx)
    # Mean hourly zonal demand, rather than a sum of noncoincident zonal peaks.
    for zone in zones:
        out['zone_' + zone] = wide[zone].groupby(local_dates).mean().reindex(idx).where(good)
    return out, dict(duplicate_rows_removed=n_duplicate, complete_load_days=int(good.sum()),
                     incomplete_load_days=int((~good).sum()))


def parse_weather_frame(frame: pd.DataFrame, allowed_flags=('1', '5')) -> pd.DataFrame:
    if not {'DATE', 'TMP', 'DEW'}.issubset(frame):
        raise ValueError('Missing NOAA hourly fields.')
    out = pd.DataFrame({'utc': pd.to_datetime(frame['DATE'], utc=True, errors='raise')})
    for raw, col in [('TMP', 'temp'), ('DEW', 'dew')]:
        split = frame[raw].astype(str).str.split(',', n=1, expand=True)
        if split.shape[1] != 2:
            raise ValueError(f'Unexpected NOAA {raw} encoding.')
        numeric = pd.to_numeric(split[0], errors='coerce')
        valid = split[1].str.strip().isin(allowed_flags) & numeric.abs().lt(9999)
        out[col] = (numeric / 10).where(valid)
    # An impossible dewpoint is rejected rather than corrected using future data.
    bad = out['dew'] > out['temp'] + 0.5
    out.loc[bad, 'dew'] = np.nan
    return out


def daily_weather(frame: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    frame = frame.copy()
    frame['hour'] = frame['utc'].dt.floor('h')
    hourly = frame.groupby('hour')[['temp', 'dew']].mean().sort_index()
    days = hourly.index.tz_convert(cfg['time_zone']).tz_localize(None).normalize()
    means = hourly.groupby(days).mean(); counts = hourly.groupby(days).count()
    expected = pd.Series([expected_hours(d, cfg['time_zone']) for d in means.index], index=means.index)
    for col in ('temp', 'dew'):
        enough = counts[col] >= np.ceil(expected * cfg['minimum_weather_hour_fraction'])
        means[col] = means[col].where(enough)
        means[col + '_hours'] = counts[col]
    return means


def fit_exposure_weights(data: pd.DataFrame, cfg: dict) -> np.ndarray:
    # The cutoff is intentionally fixed at the original training period even when
    # final models are refit on train+validation.
    train = data.loc[cfg['start']:cfg['train_end']]
    values = []
    for s in cfg['stations'].values():
        cols = ['zone_' + z for z in s['zones']]
        values.append(float(train[cols].sum(axis=1, min_count=len(cols)).mean()))
    values = np.array(values)
    if not np.isfinite(values).all() or (values < 0).any() or values.sum() <= 0:
        raise ValueError('Cannot derive positive training-only load exposure weights.')
    return values / values.sum()


def prepare(root: Path = ROOT) -> None:
    cfg = read_protocol(root); raw = root / 'raw'
    mp = raw / 'download_manifest.json'
    if not mp.exists():
        raise FileNotFoundError('No complete official dataset. Run download; self-test fixtures are not empirical data.')
    manifest = json.loads(mp.read_text())
    if manifest.get('status') != 'COMPLETE':
        raise ValueError('Raw download is incomplete; no empirical analysis will run.')
    if manifest['protocol_sha256'] != sha256(root / 'protocol.json'):
        raise ValueError('Protocol has changed since downloading. Freeze a new version first.')
    records = {r['file']: r for r in manifest['files']}
    for _, _, name in source_requests(cfg):
        if name not in records or sha256(raw / name) != records[name]['sha256']:
            raise ValueError(f'Missing or modified raw data: {name}')
    loads = []
    for kind, _, name in source_requests(cfg):
        if kind != 'nyiso':
            continue
        with zipfile.ZipFile(raw / name) as z:
            for member in z.namelist():
                if member.lower().endswith('.csv'):
                    loads.append(parse_nyiso_frame(pd.read_csv(z.open(member))))
    data, audit = daily_load(pd.concat(loads, ignore_index=True), cfg)
    metadata = {}
    for key, s in cfg['stations'].items():
        rows = []
        for year in range(pd.Timestamp(cfg['start']).year, pd.Timestamp(cfg['end']).year + 1):
            f = pd.read_csv(raw / f'noaa_{key}_{year}.csv', dtype={'STATION': str})
            if 'STATION' in f and set(f.STATION.dropna().str.zfill(11)) != {s['id']}:
                raise ValueError(f'Station ID mismatch for {key}')
            name_cols = [col for col in ('NAME', 'STATION_NAME') if col in f]
            if name_cols:
                names = sorted(f[name_cols[0]].dropna().astype(str).unique())
                if not any(s['expected_name'] in re.sub(r'[^A-Z]', '', n.upper()) for n in names):
                    raise ValueError(f'Station name mismatch: {key}: {names}')
                metadata[key] = dict(id=s['id'], names=names)
            else:
                raise ValueError(f'NOAA did not return station-name metadata for {key}; verify identity before proceeding.')
            rows.append(parse_weather_frame(f, tuple(cfg['weather_qc_flags'])))
        wx = pd.concat(rows, ignore_index=True).drop_duplicates(['utc', 'temp', 'dew'])
        daily = daily_weather(wx, cfg).rename(columns=lambda col: f'{key}_{col}')
        data = data.join(daily)
    out = root / 'prepared'; out.mkdir(exist_ok=True)
    data.index.name = 'date'; data.to_csv(out / 'daily.csv')
    audit.update(stations=metadata, start=cfg['start'], end=cfg['end'],
                 complete_weather_days=int(data[[f'{k}_{v}' for k in cfg['stations'] for v in ('temp','dew')]].notna().all(axis=1).sum()),
                 protocol_sha256=sha256(root / 'protocol.json'), raw_manifest_sha256=sha256(mp))
    dump_json(out / 'audit.json', audit)
    dump_json(out / 'provenance.json', dict(daily_sha256=sha256(out / 'daily.csv'),
                                           protocol_sha256=sha256(root / 'protocol.json'),
                                           source_sha256=sha256(Path(__file__)),
                                           raw_manifest_sha256=sha256(mp),
                                           audit_sha256=sha256(out / 'audit.json'),
                                           status='OFFICIAL_ARCHIVE_PREPARED'))
    print(json.dumps(audit, ensure_ascii=False, indent=2))


def calendar_lags(data: pd.DataFrame) -> pd.DataFrame:
    if not data.index.equals(pd.date_range(data.index.min(), data.index.max(), freq='D')):
        raise ValueError('Reindex to a complete calendar before forming lags.')
    idx = data.index
    x = pd.DataFrame(index=idx)
    for lag in (1, 7, 14):
        x[f'load_lag_{lag}'] = data.peak.shift(lag)
    x['load_prev7_mean'] = data.peak.shift(1).rolling(7, min_periods=7).mean()
    for k in (1, 2, 3):
        x[f'doy_sin_{k}'] = np.sin(2 * np.pi * k * (idx.dayofyear - 1) / 365.2425)
        x[f'doy_cos_{k}'] = np.cos(2 * np.pi * k * (idx.dayofyear - 1) / 365.2425)
    for d in range(7):
        x[f'dow_{d}'] = (idx.dayofweek == d).astype(int)
    holiday = USFederalHolidayCalendar().holidays(idx.min(), idx.max())
    x['federal_holiday'] = idx.isin(holiday).astype(int)
    x['linear_time_years'] = (idx - pd.Timestamp('2019-01-01')).days / 365.2425
    return x


def wx_features(data: pd.DataFrame, cfg: dict, weights: np.ndarray,
                permutation_seed: int | None = None) -> dict[str, pd.DataFrame]:
    keys = list(cfg['stations']); theta = float(cfg['degree_threshold_c'])
    temp = data[[k + '_temp' for k in keys]].to_numpy(float)
    dew = data[[k + '_dew' for k in keys]].to_numpy(float)
    if temp.shape[1] != len(weights) or not np.isclose(np.sum(weights), 1):
        raise ValueError('Weight dimensions or normalization incorrect.')
    base = calendar_lags(data)
    aggregate = base.copy()
    equal = np.full(len(keys), 1 / len(keys))
    for label, w in [('equal', equal), ('exposure', weights)]:
        t, d = temp @ w, dew @ w
        aggregate[f'{label}_temp'] = t; aggregate[f'{label}_dew'] = d
        for cut in (10.0, theta, 25.0):
            aggregate[f'{label}_cool_after_mean_{cut:.3f}'] = np.maximum(t - cut, 0)
            aggregate[f'{label}_heat_after_mean_{cut:.3f}'] = np.maximum(cut - t, 0)
    distribution = aggregate.copy()
    for label, arr in [('temp', temp), ('dew', dew)]:
        for name, value in [('std', np.std(arr, axis=1)), ('min', np.min(arr, axis=1)),
                            ('max', np.max(arr, axis=1)), ('q25', np.quantile(arr, .25, axis=1)),
                            ('q75', np.quantile(arr, .75, axis=1))]:
            distribution[f'{label}_{name}'] = value
    for label, w in [('equal', equal), ('exposure', weights)]:
        for cut in (10.0, theta, 25.0):
            distribution[f'{label}_cool_before_mean_{cut:.3f}'] = np.maximum(temp - cut, 0) @ w
            distribution[f'{label}_heat_before_mean_{cut:.3f}'] = np.maximum(cut - temp, 0) @ w
            distribution[f'{label}_fraction_above_{cut:.3f}'] = (temp > cut).astype(float) @ w
    identity = distribution.copy()
    labelled_t, labelled_d = temp.copy(), dew.copy()
    if permutation_seed is not None:
        # One independently generated within-day permutation, shared by T and dew.
        # B2 remains unchanged. This deliberately tests extra identity channels only.
        for j, date in enumerate(data.index):
            rng = np.random.default_rng(int(permutation_seed) + int(date.toordinal()))
            order = rng.permutation(len(keys))
            labelled_t[j] = temp[j, order]; labelled_d[j] = dew[j, order]
    for a, key in enumerate(keys):
        identity[f'site_{key}_temp_anomaly'] = labelled_t[:, a] - temp.mean(axis=1)
        identity[f'site_{key}_dew_anomaly'] = labelled_d[:, a] - dew.mean(axis=1)
        for cut in (theta, 25.0):
            identity[f'site_{key}_cool_{cut:.3f}'] = np.maximum(labelled_t[:, a] - cut, 0)
            identity[f'site_{key}_heat_{cut:.3f}'] = np.maximum(cut - labelled_t[:, a], 0)
    return dict(B0_calendar_lags=base, B1_aggregated=aggregate,
                B2_distribution=distribution, B3_site_identity=identity)


def split_masks(index: pd.DatetimeIndex, cfg: dict) -> dict[str, np.ndarray]:
    return dict(train=(index >= cfg['start']) & (index <= cfg['train_end']),
                validation=(index >= cfg['validation_start']) & (index <= cfg['validation_end']),
                test=(index >= cfg['test_start']) & (index <= cfg['test_end']))


def model_candidates(family: str, seed: int):
    if family == 'hgb':
        for leaves in (7, 15):
            for penalty in (1.0, 10.0):
                params = dict(max_iter=200, learning_rate=.05, max_leaf_nodes=leaves,
                              min_samples_leaf=20, l2_regularization=penalty,
                              early_stopping=False, random_state=seed)
                yield params, HistGradientBoostingRegressor(**params)
    elif family == 'ridge':
        for alpha in (.1, 1.0, 10.0, 100.0):
            yield dict(alpha=alpha), make_pipeline(StandardScaler(), Ridge(alpha=alpha))
    else:
        raise ValueError(f'Unknown family: {family}')


def fit_selected(x: pd.DataFrame, y: pd.Series, masks: dict, family: str, seed: int):
    choices = []
    for params, model in model_candidates(family, seed):
        model.fit(x.loc[masks['train']], y.loc[masks['train']])
        pred = model.predict(x.loc[masks['validation']])
        loss = float(np.mean(np.abs(y.loc[masks['validation']].to_numpy() - pred)))
        choices.append((loss, params, model))
    choices.sort(key=lambda row: row[0])
    loss, params, model = choices[0]
    refit = masks['train'] | masks['validation']
    model.fit(x.loc[refit], y.loc[refit])
    predictions = model.predict(x.loc[masks['test']])
    return predictions, dict(validation_MAE=loss, parameters=params, features=x.shape[1])


def score(y: np.ndarray, pred: np.ndarray, tail_threshold: float) -> dict:
    err = np.asarray(y) - np.asarray(pred)
    tail = np.asarray(y) >= tail_threshold
    return dict(n=int(len(y)), MAE=float(np.abs(err).mean()), RMSE=float(np.sqrt(np.mean(err**2))),
                high_load_n=int(tail.sum()),
                high_load_MAE=float(np.abs(err[tail]).mean()) if tail.any() else None,
                high_load_underprediction=float(np.maximum(err[tail], 0).mean()) if tail.any() else None)


def paired_block_interval(differences: pd.Series, block_days: int, replicates: int, seed: int) -> dict:
    # Preserve calendar spacing, including NaN days outside the high-load subset.
    idx = pd.date_range(differences.index.min(), differences.index.max(), freq='D')
    a = differences.reindex(idx).to_numpy(float)
    n = len(a)
    if not np.isfinite(a).any() or n < block_days:
        raise ValueError('Insufficient data for block bootstrap.')
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(replicates):
        starts = rng.integers(0, n, math.ceil(n / block_days))
        chosen = np.concatenate([(s + np.arange(block_days)) % n for s in starts])[:n]
        sample = a[chosen]
        if np.isfinite(sample).any():
            means.append(float(np.nanmean(sample)))
    return dict(block_days=block_days, paired_mean_improvement=float(np.nanmean(a)),
                lower_95=float(np.quantile(means, .025)), upper_95=float(np.quantile(means, .975)),
                effective_bootstrap_replicates=len(means),
                note='Exploratory paired circular-block interval; not causal and not a multiple-testing correction.')


def validate_analysis_inputs(root: Path) -> dict:
    prepared = root / 'prepared'
    provpath = prepared / 'provenance.json'
    if not provpath.exists():
        raise FileNotFoundError('No verified empirical dataset; cannot report empirical performance.')
    prov = json.loads(provpath.read_text())
    if prov['status'] != 'OFFICIAL_ARCHIVE_PREPARED' or prov['daily_sha256'] != sha256(prepared / 'daily.csv'):
        raise ValueError('Prepared-data provenance check failed.')
    if prov['protocol_sha256'] != sha256(root / 'protocol.json'):
        raise ValueError('Protocol changed; do not silently tune after observing a test set.')
    if prov.get('source_sha256') != sha256(Path(__file__)):
        raise ValueError('Preparation code changed; rerun prepare before analysis.')
    if prov.get('raw_manifest_sha256') != sha256(root / 'raw' / 'download_manifest.json'):
        raise ValueError('Raw-data manifest changed after preparation.')
    if prov.get('audit_sha256') != sha256(prepared / 'audit.json'):
        raise ValueError('Preparation audit changed after preparation.')
    evidence_path = root / 'qa' / 'interval_convention_20261029.json'
    if not evidence_path.exists():
        raise ValueError('Run verify_intervals.py before interpreting empirical models.')
    evidence = json.loads(evidence_path.read_text())
    if (evidence.get('verified') is not True or evidence.get('convention') != 'hour_beginning'
            or evidence.get('protocol_sha256') != prov['protocol_sha256']):
        raise ValueError('Interval convention evidence is missing, failed, or belongs to another protocol.')
    return prov


def analyse(root: Path = ROOT) -> None:
    cfg = read_protocol(root); prepared = root / 'prepared'
    provenance = validate_analysis_inputs(root)
    data = pd.read_csv(prepared / 'daily.csv', index_col='date', parse_dates=True)
    data = data.reindex(pd.date_range(cfg['start'], cfg['end'], freq='D'))
    weights = fit_exposure_weights(data, cfg)
    fs = wx_features(data, cfg, weights)
    valid = data.peak.notna() & fs['B3_site_identity'].notna().all(axis=1)
    fullmasks = split_masks(data.index, cfg)
    coverage = {name: dict(eligible=int(mask.sum()), usable=int((valid & mask).sum()),
                           fraction=float((valid & mask).sum()/mask.sum())) for name, mask in fullmasks.items()}
    out = root / 'results'; out.mkdir(exist_ok=True)
    dump_json(out / 'coverage.json', coverage)
    if any(v['fraction'] < cfg['minimum_usable_fraction_each_split'] for v in coverage.values()):
        raise ValueError('Coverage below frozen threshold. Audit missingness before fitting; do not choose new stations from test performance.')
    threshold = float(data.loc[fullmasks['train'], 'peak'].quantile(cfg['tail_quantile_training_only']))
    y = data.loc[valid, 'peak']; masks = split_masks(y.index, cfg)
    pred = pd.DataFrame({'actual': y.loc[masks['test']]})
    metrics, tuning, boot = [], {}, []
    for family in ('hgb', 'ridge'):
        for name, x in fs.items():
            estimate, selection = fit_selected(x.loc[valid], y, masks, family, cfg['seed'])
            label = family + '__' + name; pred[label] = estimate; tuning[label] = selection
            metrics.append(dict(family=family, representation=name, **score(pred.actual.to_numpy(), estimate, threshold)))
            print(label, metrics[-1], flush=True)
        e2 = (pred.actual - pred[family + '__B2_distribution']).abs()
        e3 = (pred.actual - pred[family + '__B3_site_identity']).abs()
        for block in cfg['bootstrap_block_days']:
            diff = (e2 - e3).where(pred.actual >= threshold)
            boot.append(dict(family=family, **paired_block_interval(diff, block, cfg['bootstrap_replicates'], cfg['seed'])))
    for seed in cfg['permutation_seeds']:
        px = wx_features(data, cfg, weights, permutation_seed=seed)['B3_site_identity']
        estimate, selection = fit_selected(px.loc[valid], y, masks, 'hgb', cfg['seed'])
        name = 'identity_scramble_' + str(seed); label = 'hgb__' + name
        pred[label] = estimate; tuning[label] = selection
        metrics.append(dict(family='hgb', representation=name, **score(pred.actual.to_numpy(), estimate, threshold)))
    metric = pd.DataFrame(metrics)
    def get(f, n):
        return metric[(metric.family == f) & (metric.representation == n)].iloc[0]
    b2, b3 = get('hgb','B2_distribution'), get('hgb','B3_site_identity')
    r2, r3 = get('ridge','B2_distribution'), get('ridge','B3_site_identity')
    gain = float(1 - b3.high_load_MAE/b2.high_load_MAE) if b2.high_load_MAE else 0.0
    b14 = next(r for r in boot if r['family']=='hgb' and r['block_days']==14)
    shuffled = metric[(metric.family=='hgb') & metric.representation.str.startswith('identity_scramble')]
    conditions = dict(enough_tail_days=int(b3.high_load_n)>=cfg['minimum_test_high_load_days'],
                      at_least_five_percent_tail_gain=gain>=cfg['practical_screen_relative_tail_MAE_gain'],
                      primary_interval_positive=b14['lower_95']>0,
                      ridge_tail_direction_agrees=bool(r3.high_load_MAE < r2.high_load_MAE),
                      beats_four_of_five_scrambles=int((shuffled.high_load_MAE > b3.high_load_MAE).sum()) >= 4,
                      overall_MAE_not_more_than_two_percent_worse=bool(b3.MAE <= b2.MAE*1.02))
    report = dict(status='EMPIRICAL_SCREEN_ONLY', scope=cfg['scope'], estimand=cfg['estimand'],
        high_load_threshold_training_only=threshold, exposure_weights=dict(zip(cfg['stations'], map(float,weights))),
        primary_relative_tail_MAE_improvement=gain, screen_conditions=conditions,
        screening_pass=all(conditions.values()),
        limitations=['One system and one held-out year; not geographic transfer validation.',
          'Realized contemporaneous weather, not historical forecast vintages.',
          'Historical files may be revised; this is not a point-in-time trading dataset.',
          'Coarse five-station exposure mapping, not population-weighted coverage.',
          'Hour-beginning labels corroborated against five-minute official archives, not an explicit written NYISO timing definition.',
          'Passing an analyst-defined screen does not establish novelty, causality, deployability, or trading profit.'],
        protocol_sha256=sha256(root/'protocol.json'), source_sha256=sha256(Path(__file__)),
        data_sha256=sha256(prepared/'daily.csv'), preparation_provenance=provenance,
        interval_evidence_sha256=sha256(root/'qa'/'interval_convention_20261029.json'),
        versions=dict(python=sys.version.split()[0],numpy=np.__version__,pandas=pd.__version__,sklearn=sklearn.__version__))
    metric.to_csv(out/'metrics.csv',index=False)
    pred.index.name='date'; pred.to_csv(out/'test_predictions.csv')
    dump_json(out/'model_selection.json',tuning); dump_json(out/'block_intervals.json',boot)
    dump_json(out/'empirical_report.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command', choices=['download','prepare','analyse'])
    ap.add_argument('--root', type=Path, default=ROOT)
    args = ap.parse_args()
    with threadpool_limits(limits=1):
        {'download':download,'prepare':prepare,'analyse':analyse}[args.command](args.root)


if __name__ == '__main__':
    main()
