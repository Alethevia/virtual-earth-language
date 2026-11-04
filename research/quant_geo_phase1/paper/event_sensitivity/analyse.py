#!/usr/bin/env python3
"""Post-hoc deletion sensitivity of observed consecutive high-demand runs."""
import csv
import hashlib
import io
import json
import math
from datetime import date
from pathlib import Path
import argparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def episodes(rows, threshold):
    """Missing dates and observed non-high dates both break an observed run."""
    ordered = sorted(rows, key=lambda r: r['date'])
    dates = [date.fromisoformat(r['date']) for r in ordered]
    if len(set(dates)) != len(dates):
        raise ValueError('Duplicate prediction date')
    runs = []
    previous = None
    for day, row in zip(dates, ordered):
        values = [float(row[k]) for k in ('actual', 'hgb__B2_distribution',
            'hgb__B3_site_identity', 'ridge__B2_distribution', 'ridge__B3_site_identity')]
        if not all(math.isfinite(v) for v in values):
            raise ValueError('Non-finite prediction')
        if values[0] >= threshold:
            if previous is None or (day-previous).days != 1:
                runs.append([])
            runs[-1].append(row)
            previous = day
        else:
            previous = None
    return runs


def summarize(runs, family):
    if len(runs) < 2:
        raise ValueError('At least two observed high-demand runs required')
    events = []
    for run in runs:
        differences = [abs(float(r['actual'])-float(r[family+'__B2_distribution'])) -
                       abs(float(r['actual'])-float(r[family+'__B3_site_identity'])) for r in run]
        events.append(dict(start=run[0]['date'], end=run[-1]['date'], days=len(run),
                           sum_gain_mw_days=math.fsum(differences), mean_gain_mw=math.fsum(differences)/len(run)))
    n = sum(e['days'] for e in events)
    total = math.fsum(e['sum_gain_mw_days'] for e in events)
    mean = total/n
    for event in events:
        event['remaining_mean_gain_mw'] = (total-event['sum_gain_mw_days'])/(n-event['days'])
    remaining = [e['remaining_mean_gain_mw'] for e in events]
    result = dict(high_days=n, observed_runs=len(events), mean_gain_mw=mean,
                  equal_run_mean_gain_mw=math.fsum(e['mean_gain_mw'] for e in events)/len(events),
                  deletion_min_gain_mw=min(remaining), deletion_max_gain_mw=max(remaining),
                  deletions_reversing_sign=sum(v*mean < 0 for v in remaining))
    return result, events


def render_csv(rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader(); writer.writerows(rows)
    return stream.getvalue()


def products():
    manifest = json.loads((HERE/'inputs.json').read_text())
    summary, detail = [], []
    for source in manifest['sources']:
        payload = (ROOT/source['path']).read_bytes()
        if hashlib.sha256(payload).hexdigest() != source['sha256']:
            raise ValueError('Input hash mismatch: '+source['path'])
        rows = list(csv.DictReader(io.StringIO(payload.decode())))
        for year in source['years']:
            runs = episodes([r for r in rows if date.fromisoformat(r['date']).year==year], source['threshold_mw'])
            for family in ('hgb', 'ridge'):
                result, events = summarize(runs, family)
                tags = dict(region=source['region'], year=year, family=family)
                summary.append(dict(**tags, **result))
                detail.extend(dict(**tags, **e) for e in events)
    table = ['| Region | Year | Model | High days / observed runs | Mean gain MW | Range after deleting one run MW | Sign reversals |',
             '|---|---:|---|---:|---:|---|---:|']
    for r in summary:
        table.append(f"| {r['region']} | {r['year']} | {r['family']} | {r['high_days']} / {r['observed_runs']} | {r['mean_gain_mw']:+.2f} | [{r['deletion_min_gain_mw']:+.2f}, {r['deletion_max_gain_mw']:+.2f}] | {r['deletions_reversing_sign']} / {r['observed_runs']} |")
    return {'summary.csv':render_csv(summary), 'events.csv':render_csv(detail), 'table.md':'\n'.join(table)+'\n'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    for name, value in products().items():
        if args.check:
            if (HERE/name).read_text() != value:
                raise ValueError('Stale diagnostic: '+name)
        else:
            (HERE/name).write_text(value)
    print('Checked 8 post-hoc comparisons; zero model fits.')


if __name__=='__main__':
    main()
