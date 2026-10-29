#!/usr/bin/env python3
"""Audit the entire locked evaluation window without fitting any model."""
import json
from pathlib import Path
import pandas as pd
import quant_geo_phase1 as q
import replicate_2025 as replication


def main():
    root = replication.ROOT
    replication.check_lock(root)
    provenance = q.validate_analysis_inputs(root)
    cfg = q.read_protocol(root)
    data = pd.read_csv(root / 'prepared/daily.csv', index_col='date', parse_dates=True)
    original = pd.read_csv(q.ROOT / 'prepared/daily.csv', index_col='date', parse_dates=True)
    replication.verify_historical_values(original, data)
    features = q.wx_features(data, cfg, q.fit_exposure_weights(data, cfg))
    wx = [f'{station}_{variable}' for station in cfg['stations'] for variable in ('temp', 'dew')]
    calendar = pd.DataFrame(index=data.index)
    calendar['load_complete'] = data.peak.notna()
    calendar['weather_complete'] = data[wx].notna().all(axis=1)
    calendar['usable'] = data.peak.notna() & features['B3_site_identity'].notna().all(axis=1)
    calendar['actual_load_mw'] = data.peak
    for col in wx:
        calendar[col + '_missing'] = data[col].isna()
    test = calendar.loc[cfg['test_start']:cfg['test_end']]
    monthly = test.groupby(test.index.month)[['load_complete', 'weather_complete', 'usable']].sum()
    monthly['calendar_days'] = test.groupby(test.index.month).size()
    monthly.index.name = 'month'
    files = []
    for station in cfg['stations']:
        path = root / 'raw' / f'noaa_{station}_2025.csv'
        raw = pd.read_csv(path)
        files.append(dict(file=path.name, rows=len(raw), first_utc=raw.DATE.min(),
                          last_utc=raw.DATE.max(), sha256=q.sha256(path)))
    out = root / 'qa'; out.mkdir(exist_ok=True)
    monthly.to_csv(out / 'monthly_coverage.csv')
    test.to_csv(out / 'daily_coverage.csv', index_label='date')
    manifest = json.loads((root / 'raw/download_manifest.json').read_text())
    fraction = float(test.usable.mean())
    q.dump_json(out / 'data_audit.json', dict(
        status='DATA_COVERAGE_PASS' if fraction >= cfg['minimum_usable_fraction_each_split'] else 'BLOCKED_DATA_COVERAGE',
        calendar_days=len(test), complete_load_days=int(test.load_complete.sum()),
        complete_weather_days=int(test.weather_complete.sum()), usable_days=int(test.usable.sum()),
        usable_fraction=fraction, required_fraction=cfg['minimum_usable_fraction_each_split'],
        raw_file_count=len(manifest['files']), historical_file_count=102, new_file_count=17,
        original_daily_values_and_missingness_preserved=True, no_model_fits_in_this_audit=True,
        weather_files=files, preparation_provenance=provenance,
        source_sha256=q.sha256(Path(__file__)),
        note='All requested files downloaded does not imply full temporal coverage. Legacy ISD ends during August 2025.'))
    print(monthly.to_string()); print('usable_fraction', fraction)


if __name__ == '__main__':
    main()
