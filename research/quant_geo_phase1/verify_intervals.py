#!/usr/bin/env python3
"""Cross-check hour labels against NYISO's independent five-minute load archive.

This is numerical source validation, not an official written timing definition.
The five fixed dates cover different years, seasons and both 2024 DST changes.
No model predictions or test-set errors are used to choose the dates/alignment.
"""
import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import quant_geo_phase1 as q

DATES = ['20190115', '20220715', '20240310', '20240715', '20241103']


def compare_frames(actual, integrated):
    samples = q.parse_nyiso_frame(actual.rename(columns={'Load': 'Integrated Load'}))
    target = q.parse_nyiso_frame(integrated)
    samples['hour'] = samples.utc.dt.floor('h')
    hourly = samples.groupby(['hour', 'zone']).load.agg(['mean', 'count'])
    hourly = hourly[hourly['count'] >= 10]['mean']
    target = target.set_index(['utc', 'zone']).load.rename('integrated')
    comparisons = [target]
    for shift in (-1, 0, 1):
        x = hourly.reset_index()
        x['hour'] += pd.Timedelta(hours=shift)
        comparisons.append(x.set_index(['hour', 'zone'])['mean'].rename(str(shift)))
    # Compare all hypotheses on exactly the same interior hour-zone pairs.
    joined = pd.concat(comparisons, axis=1).dropna()
    if len(joined) < 200:
        raise ValueError('Insufficient matched hour-zone observations for label verification.')
    errors = {str(s): float(np.abs(joined.integrated - joined[str(s)]).mean()) for s in (-1, 0, 1)}
    return dict(matched_hour_zone_pairs=len(joined), mean_absolute_difference_mw=errors,
                hour_beginning_consistent=errors['0'] < .25 * min(errors['-1'], errors['1']))


def main(root: Path = q.ROOT):
    folder = root / 'raw' / 'interval_check'
    folder.mkdir(parents=True, exist_ok=True)
    evidence, sources = [], []
    session = requests.Session()
    session.mount('https://', HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])))
    for day in DATES:
        month = day[:6]
        url = f'https://mis.nyiso.com/public/csv/pal/{month}01pal_csv.zip'
        path = folder / f'{month}01pal_csv.zip'
        if not path.exists():
            response = session.get(url, timeout=(30, 90))
            response.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                if f'{day}pal.csv' not in z.namelist():
                    raise ValueError('Unexpected five-minute archive structure.')
            path.write_bytes(response.content)
        integrated_path = root / 'raw' / f'nyiso_{month}.zip'
        with zipfile.ZipFile(path) as a, zipfile.ZipFile(integrated_path) as b:
            row = compare_frames(pd.read_csv(a.open(f'{day}pal.csv')),
                                 pd.read_csv(b.open(f'{day}palIntegrated.csv')))
        evidence.append(dict(date=day, **row))
        sources.append(dict(five_minute_url=url, five_minute_sha256=q.sha256(path),
                            integrated_file=integrated_path.name,
                            integrated_sha256=q.sha256(integrated_path)))
    report = dict(status='NUMERICAL_INTERVAL_CROSSCHECK', convention='hour_beginning',
                  verified=all(x['hour_beginning_consistent'] for x in evidence),
                  protocol_sha256=q.sha256(root / 'protocol.json'), dates=evidence, sources=sources,
                  method='Approximate five-minute means compared with integrated load on identical hour-zone pairs; UTC offsets taken from EST/EDT labels.',
                  limitations='Numerical corroboration from official raw data, not an explicit NYISO written definition. Sampling and integration weights differ; equality is not expected.')
    q.dump_json(root / 'qa' / 'interval_convention_20261029.json', report)
    print(report)
    if not report['verified']:
        raise ValueError('Interval convention did not pass; investigate before modelling.')


if __name__ == '__main__':
    main()
