#!/usr/bin/env python3
"""Fixed ISO-NE geographic replication; no changes to the NYISO engine."""
import argparse
import json
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import sklearn
from openpyxl import load_workbook
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from threadpoolctl import threadpool_limits

import quant_geo_phase1 as q
import ghcnh_migrate as g

ROOT = q.ROOT / 'isone_v1'


def check_lock(root=ROOT):
    lock = json.loads((root / 'lock.json').read_text())
    expected = dict(lock['sha256'])
    amendment = root/'amendment_01.json'
    if amendment.exists():
        correction = json.loads(amendment.read_text())
        if correction['original_source_sha256'] != expected['isone_replication.py']:
            raise ValueError('Wrong amendment base')
        expected['isone_replication.py'] = correction['amended_source_sha256']
    for name, digest in expected.items():
        if q.sha256(q.ROOT / name) != digest:
            raise ValueError('Locked source changed: ' + name)
    return lock


def retrieve(spec):
    url, path, expected = spec
    if path.exists() and expected:
        if q.sha256(path) != expected['sha256']:
            raise ValueError('Cached archive changed: ' + path.name)
        return expected
    session = requests.Session()
    session.mount('https://', HTTPAdapter(max_retries=Retry(
        total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])))
    response = session.get(url, timeout=(20, 100))
    response.raise_for_status()
    payload = response.content
    if path.suffix == '.parquet' and (payload[:4] != b'PAR1' or payload[-4:] != b'PAR1'):
        raise ValueError('Not a parquet archive')
    if path.suffix == '.xlsx' and payload[:4] != b'PK\x03\x04':
        raise ValueError('Not an XLSX archive')
    path.write_bytes(payload)
    row = dict(file=path.name, source=url, sha256=q.sha256(path), bytes=len(payload),
               retrieved_utc=datetime.now(timezone.utc).isoformat())
    if expected and row['sha256'] != expected['sha256']:
        raise ValueError('Official archive revised: ' + path.name)
    print('downloaded', path.name, row['bytes'], flush=True)
    return row


def download(root=ROOT):
    check_lock(root)
    cfg = q.read_protocol(root)
    raw = root / 'raw'; raw.mkdir(exist_ok=True)
    manifest_path = raw / 'download_manifest.json'
    known = {x['file']: x for x in json.loads(manifest_path.read_text())['files']} if manifest_path.exists() else {}
    specs = [(url, raw / f'{year}_smd_hourly.xlsx', known.get(f'{year}_smd_hourly.xlsx'))
             for year, url in cfg['load_sources'].items()]
    for station in cfg['stations'].values():
        for year in range(2019, 2027):
            name = f"GHCNh_{station['ghcnh_id']}_{year}.parquet"
            specs.append((g.BASE + f'access/by-year/{year}/parquet/' + name, raw / name, known.get(name)))
    manifest = dict(status='INCOMPLETE', protocol_sha256=q.sha256(root/'protocol.json'), files=[])
    with ThreadPoolExecutor(max_workers=3) as pool:
        for row in pool.map(retrieve, specs):
            manifest['files'].append(row)
            q.dump_json(manifest_path, manifest)
    manifest['status'] = 'COMPLETE'
    q.dump_json(manifest_path, manifest)


def validate_hours(frame, year):
    """Validate legacy 24-hour files and the native DST format from 2024."""
    x = frame.copy()
    x['date'] = pd.to_datetime(x['Date'], errors='raise')
    if x.date.isna().any() or not x.date.eq(x.date.dt.normalize()).all():
        raise ValueError('Invalid calendar date')
    if not x.date.dt.year.eq(year).all():
        raise ValueError('Wrong annual file')
    def label(value):
        if str(value).strip() == '02X':
            return '02X'
        number = float(value)
        if not number.is_integer() or not 1 <= number <= 24:
            raise ValueError('Unrecognized hour-ending label')
        return f'{int(number):02d}'
    x['hour'] = x['Hr_End'].map(label)
    if x.duplicated(['date', 'hour']).any():
        raise ValueError('Duplicate hour')
    pairs = []
    for date in pd.date_range(f'{year}-01-01', f'{year}-12-31'):
        hours = [f'{h:02d}' for h in range(1, 25)]
        if year >= 2024:
            count = q.expected_hours(date)
            if count == 23:
                hours.remove('02')
            elif count == 25:
                hours.insert(2, '02X')
        pairs.extend((date, h) for h in hours)
    expected = pd.MultiIndex.from_tuples(pairs, names=['date', 'hour'])
    x = x.set_index(['date', 'hour']).sort_index()
    if not x.index.equals(expected):
        raise ValueError('Missing or unexpected SMD hour')
    return x


def parse_load(path, year, cfg):
    book = load_workbook(path, read_only=True, data_only=True)
    try:
        columns = {}
        for zone in cfg['zones']:
            sheet = book[zone]
            it = sheet.values; header = next(it)
            frame = pd.DataFrame(it, columns=header)
            if not {'Date', 'Hr_End', 'RT_Demand'}.issubset(frame):
                raise ValueError('Missing SMD columns')
            x = validate_hours(frame[['Date', 'Hr_End', 'RT_Demand']], year)
            demand = pd.to_numeric(x.RT_Demand, errors='raise')
            if not np.isfinite(demand).all() or (demand < 0).any():
                raise ValueError('Missing or negative zonal demand')
            columns[zone] = demand
        hourly = pd.DataFrame(columns)
        return aggregate_load(normalize_load_hours(hourly, year))
    finally:
        book.close()


def aggregate_load(hourly):
    # Sum zones within each hour first. A sum of separate zone maxima is wrong.
    total = hourly.sum(axis=1, min_count=hourly.shape[1])
    out = hourly.groupby(level='date').mean().add_prefix('zone_')
    out['peak'] = total.groupby(level='date').max()
    return out


def normalize_load_hours(hourly, year):
    """Harmonize 2024+ DST rows to the documented 2019-2023 convention."""
    if year < 2024:
        return hourly
    out = hourly.copy()
    for date in hourly.index.get_level_values('date').unique():
        count = q.expected_hours(date)
        if count == 23:
            out.loc[(date, '02'), :] = (hourly.loc[(date, '01')] + hourly.loc[(date, '03')])/2
        elif count == 25:
            out.loc[(date, '02'), :] = (hourly.loc[(date, '02')] + hourly.loc[(date, '02X')])/2
            out = out.drop(index=(date, '02X'))
    return out.sort_index()


def coverage(data, cfg):
    weights = q.fit_exposure_weights(data, cfg)
    features = q.wx_features(data, cfg, weights)
    valid = data.peak.notna() & features['B3_site_identity'].notna().all(axis=1)
    masks = q.split_masks(data.index, cfg)
    masks.pop('test')
    for year in (2024, 2025):
        masks[f'test_{year}'] = data.index.year == year
    audit = {name: dict(eligible=int(mask.sum()), usable=int((mask & valid).sum()),
                       fraction=float((mask & valid).sum()/mask.sum())) for name, mask in masks.items()}
    return valid, features, weights, audit


def prepare(root=ROOT):
    check_lock(root); cfg = q.read_protocol(root); raw = root/'raw'; qa = root/'qa'
    manifest = json.loads((raw/'download_manifest.json').read_text())
    if manifest['status'] != 'COMPLETE' or manifest['protocol_sha256'] != q.sha256(root/'protocol.json'):
        raise ValueError('Incomplete or stale manifest')
    for row in manifest['files']:
        if q.sha256(raw/row['file']) != row['sha256']:
            raise ValueError('Raw file changed')
    loads = [parse_load(raw/f'{year}_smd_hourly.xlsx', year, cfg) for year in range(2019, 2026)]
    data = pd.concat(loads).reindex(pd.date_range(cfg['start'], cfg['end']))
    quality = []
    for key, station in cfg['stations'].items():
        rows = []
        for year in range(2019, 2027):
            frame = pd.read_parquet(raw/f"GHCNh_{station['ghcnh_id']}_{year}.parquet")
            frame = frame[(frame.DATE >= cfg['start']) & (frame.DATE < '2026-01-01T05:00:00')]
            rows.append(g.parse(frame, station))
            for element in g.ELEMENTS:
                for (source, code), n in frame.groupby([element+'_Source_Code', element+'_Quality_Code'], dropna=False).size().items():
                    quality.append(dict(station=key, year=year, element=element, source=str(source), code=str(code), rows=int(n)))
        wx = pd.concat(rows, ignore_index=True)
        if wx.utc.duplicated().any():
            raise ValueError('Duplicate weather timestamp across files')
        data = data.join(q.daily_weather(wx, cfg).rename(columns=lambda c: key+'_'+c))
        print('prepared station', key, flush=True)
    valid, _, _, cov = coverage(data, cfg)
    qa.mkdir(exist_ok=True)
    data.to_csv(qa/'daily_model_input.csv', index_label='date')
    pd.DataFrame(quality).to_csv(qa/'quality_codes.csv', index=False)
    q.dump_json(qa/'coverage.json', cov)
    q.dump_json(qa/'download_manifest.json', manifest)
    flags = pd.DataFrame({'actual': data.peak, 'usable': valid})
    flags['high_load'] = flags.actual >= data.loc[:cfg['train_end'], 'peak'].quantile(cfg['tail_quantile_training_only'])
    flags.to_csv(qa/'daily_coverage.csv', index_label='date')
    q.dump_json(root/'input_lock.json', dict(status='PREPARED_BEFORE_MODEL_FITTING',
        created_utc=datetime.now(timezone.utc).isoformat(),
        sha256={name: q.sha256(root/name) for name in ['protocol.json', 'lock.json', 'amendment_01.json', 'AMENDMENT_01.md', 'qa/daily_model_input.csv', 'qa/download_manifest.json', 'qa/coverage.json']}))
    print(json.dumps(cov, indent=2))


def full_calendar_interval(diff, year, block, cfg):
    days = pd.date_range(f'{year}-01-01', f'{year}-12-31')
    if not diff.index.is_unique or not diff.index.isin(days).all():
        raise ValueError('Invalid bootstrap dates')
    return dict(calendar_days=len(days), **q.paired_block_interval(diff.reindex(days), block, cfg['bootstrap_replicates'], cfg['seed']))


def analyse(root=ROOT):
    check_lock(root); cfg = q.read_protocol(root); qa = root/'qa'
    input_lock = json.loads((root/'input_lock.json').read_text())
    for name, digest in input_lock['sha256'].items():
        if q.sha256(root/name) != digest:
            raise ValueError('Prepared input changed: '+name)
    data = pd.read_csv(qa/'daily_model_input.csv', index_col='date', parse_dates=True)
    valid, fs, weights, cov = coverage(data, cfg)
    if any(row['fraction'] < cfg['minimum_usable_fraction_each_split'] for row in cov.values()):
        q.dump_json(root/'execution_status.json', dict(status='BLOCKED_BY_COVERAGE', model_fits=0, coverage=cov))
        raise ValueError('Coverage below frozen minimum; no model fitted')
    y = data.loc[valid, 'peak']; masks = q.split_masks(y.index, cfg)
    threshold = float(data.loc[:cfg['train_end'], 'peak'].quantile(cfg['tail_quantile_training_only']))
    if y.index[masks['train'] | masks['validation']].max() > pd.Timestamp('2023-12-31'):
        raise ValueError('Test data entered model fitting')
    pred = pd.DataFrame({'actual': y.loc[masks['test']]}); selection = {}
    for family in ('hgb', 'ridge'):
        for name, x in fs.items():
            label = family+'__'+name
            pred[label], selection[label] = q.fit_selected(x.loc[valid], y, masks, family, cfg['seed'])
            print('fit', label, flush=True)
    for seed in cfg['permutation_seeds']:
        x = q.wx_features(data, cfg, weights, permutation_seed=seed)['B3_site_identity']
        label = 'hgb__identity_scramble_'+str(seed)
        pred[label], selection[label] = q.fit_selected(x.loc[valid], y, masks, 'hgb', cfg['seed'])
        print('fit', label, flush=True)
    metrics, intervals, screens = [], [], {}
    for year in (2025, 2024):
        p = pred.loc[str(year)]
        for label in selection:
            family, representation = label.split('__')
            metrics.append(dict(year=year, family=family, representation=representation, **q.score(p.actual, p[label], threshold)))
        for family in ('hgb', 'ridge'):
            diff = ((p.actual-p[family+'__B2_distribution']).abs() - (p.actual-p[family+'__B3_site_identity']).abs()).where(p.actual >= threshold)
            for block in cfg['bootstrap_block_days']:
                intervals.append(dict(year=year, family=family, **full_calendar_interval(diff, year, block, cfg)))
        m = pd.DataFrame(metrics).query('year == @year').set_index(['family', 'representation'])
        b2, b3 = (m.loc[('hgb', n)] for n in ('B2_distribution', 'B3_site_identity'))
        r2, r3 = (m.loc[('ridge', n)] for n in ('B2_distribution', 'B3_site_identity'))
        gain = float(1-b3.high_load_MAE/b2.high_load_MAE)
        primary = next(x for x in intervals if x['year']==year and x['family']=='hgb' and x['block_days']==14)
        beaten = int(sum(m.loc[('hgb', 'identity_scramble_'+str(s)), 'high_load_MAE'] > b3.high_load_MAE for s in cfg['permutation_seeds']))
        conditions = dict(enough_tail_days=bool(b3.high_load_n >= cfg['minimum_test_high_load_days']),
            at_least_five_percent_tail_gain=bool(gain >= cfg['practical_screen_relative_tail_MAE_gain']),
            primary_interval_positive=bool(primary['lower_95'] > 0),
            ridge_tail_direction_agrees=bool(r3.high_load_MAE < r2.high_load_MAE),
            beats_four_of_five_scrambles=beaten >= 4,
            overall_MAE_not_more_than_two_percent_worse=bool(b3.MAE <= b2.MAE*1.02))
        screens[str(year)] = dict(role='primary' if year==2025 else 'secondary', relative_tail_gain=gain,
                                 scrambles_beaten=beaten, conditions=conditions, screening_pass=all(conditions.values()))
    pred.to_csv(qa/'test_predictions.csv', index_label='date')
    pd.DataFrame(metrics).to_csv(qa/'metrics.csv', index=False)
    q.dump_json(qa/'block_intervals.json', intervals)
    q.dump_json(qa/'model_selection.json', selection)
    q.dump_json(root/'execution_status.json', dict(status='EMPIRICAL_GEOGRAPHIC_REPLICATION',
        model_fits=65, pipelines=13, fits_per_pipeline=5, training_end='2023-12-31',
        threshold_mw=threshold, exposure_weights=dict(zip(cfg['stations'], map(float, weights))),
        coverage=cov, screens=screens, input_lock=input_lock,
        versions=dict(python=sys.version.split()[0], numpy=np.__version__, pandas=pd.__version__, sklearn=sklearn.__version__)))
    print(json.dumps(screens, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['download', 'prepare', 'analyse'])
    args = parser.parse_args()
    with threadpool_limits(limits=1):
        globals()[args.command]()
