#!/usr/bin/env python3
"""Generate the manuscript's descriptive tables from published result files."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCES = ['bridge_2024/qa/metrics.csv', 'bridge_2024/qa/full_calendar_intervals.json',
           'isone_v1/qa/metrics.csv', 'isone_v1/qa/block_intervals.json',
           'ghcnh_v1/qa/block_intervals.json', 'qa/empirical_20261029/metrics.csv']


def read_csv(name):
    with (ROOT/name).open(newline='') as stream:
        return list(csv.DictReader(stream))


def build_rows():
    bridge = read_csv(SOURCES[0]); iso = read_csv(SOURCES[2])
    bridge_ci = json.loads((ROOT/SOURCES[1]).read_text())
    iso_ci = json.loads((ROOT/SOURCES[3]).read_text())
    rows = []
    for region in ('NYISO', 'ISO-NE'):
        for year in (2024, 2025):
            for family in ('hgb', 'ridge'):
                if region == 'NYISO':
                    scope = f'GHCNh_{year}_native'
                    scores = [r for r in bridge if r['scope']==scope and r['family']==family]
                    intervals = [r for r in bridge_ci if r['scope']==scope and r['family']==family and r['block_days']==14]
                    role = 'post-hoc 2024 bridge' if year==2024 else '2025 experiment; supplementary full-calendar interval'
                else:
                    scores = [r for r in iso if int(r['year'])==year and r['family']==family]
                    intervals = [r for r in iso_ci if r['year']==year and r['family']==family and r['block_days']==14]
                    role = 'secondary year' if year==2024 else 'primary year'
                pairs = {r['representation']: r for r in scores}
                b2, b3 = pairs['B2_distribution'], pairs['B3_site_identity']
                assert len(intervals)==1
                ci = intervals[0]
                a, b = float(b2['high_load_MAE']), float(b3['high_load_MAE'])
                assert int(b2['n'])==int(b3['n']) and int(b2['high_load_n'])==int(b3['high_load_n'])
                assert abs(a-b-ci['paired_mean_improvement'])<1e-8
                rows.append(dict(region=region, year=year, family=family.upper(),
                    usable_days=int(b2['n']), high_load_days=int(b2['high_load_n']),
                    B2_all_MAE_MW=float(b2['MAE']), B3_all_MAE_MW=float(b3['MAE']),
                    B2_high_MAE_MW=a, B3_high_MAE_MW=b,
                    relative_high_improvement_percent=100*(1-b/a),
                    paired_improvement_MW=a-b, lower_95_MW=ci['lower_95'], upper_95_MW=ci['upper_95'],
                    meets_30_day_minimum=int(b2['high_load_n'])>=30, evidence_role=role))
    assert len(rows)==8
    return rows


def products(rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader(); writer.writerows(rows)
    table = ['| Region | Year | Model | High days | B2 MAE | B3 MAE | Relative gain | Paired gain [95% interval] |',
             '|---|---:|---|---:|---:|---:|---:|---|']
    for r in rows:
        table.append(f"| {r['region']} | {r['year']} | {r['family']} | {r['high_load_days']} | {r['B2_high_MAE_MW']:.2f} | {r['B3_high_MAE_MW']:.2f} | {r['relative_high_improvement_percent']:+.2f}% | {r['paired_improvement_MW']:+.2f} [{r['lower_95_MW']:+.2f}, {r['upper_95_MW']:+.2f}] |")
    hashes = {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES}
    return {'evidence.csv': stream.getvalue(), 'evidence_table.md': '\n'.join(table)+'\n',
            'evidence_provenance.json': json.dumps(dict(source_commit='5e9ffef948d8a7f43b65f3929d077cc594b23a4f', source_sha256=hashes,
                new_model_fits=0, note='Descriptive synthesis. NYISO full-calendar intervals are post hoc; original primary intervals remain unchanged.'), indent=2)+'\n'}


def plot(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':10, 'svg.hashsalt':'quant-geo-evidence-v1'})
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.7), sharex=True)
    colors = {'HGB':'#176B87', 'RIDGE':'#A24B18'}
    for ax, region in zip(axes, ('NYISO', 'ISO-NE')):
        selected = [r for r in rows if r['region']==region]
        for y, r in enumerate(selected):
            ax.errorbar(r['paired_improvement_MW'], y,
                xerr=[[r['paired_improvement_MW']-r['lower_95_MW']], [r['upper_95_MW']-r['paired_improvement_MW']]],
                fmt='o' if r['family']=='HGB' else 's', color=colors[r['family']], capsize=4, markersize=6)
        ax.set_yticks(range(4), [f"{r['year']} {r['family']} (n={r['high_load_days']})" for r in selected])
        ax.invert_yaxis(); ax.axvline(0, color='#555555', linewidth=1, linestyle='--')
        ax.set_xlim(-235, 235); ax.set_ylim(3.65, -.65)
        ax.set_xlabel('Paired high-load MAE improvement (MW)')
        ax.set_title(region+'\n'+('Post-hoc full-calendar intervals' if region=='NYISO' else 'Pre-specified full-calendar intervals'), fontsize=12)
        ax.spines[['top','right']].set_visible(False); ax.grid(axis='x', alpha=.15)
    fig.suptitle('Station identity: gains depend on year and model', fontsize=15, y=.98)
    fig.text(.5, .02, 'Positive favors station identity. 14-day circular-block 95% intervals. n counts observed high-load days.\nISO-NE misses the 30-day minimum in both years. Regional target definitions differ; no pooled effect is estimated.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=(0,.13,1,.92), w_pad=2.5)
    fig.savefig(HERE/'evidence.svg', metadata={'Date':None})
    fig.savefig(HERE/'figure_preview.png', dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--plot', action='store_true')
    args = parser.parse_args(); rows = build_rows()
    for name, text in products(rows).items():
        if args.check:
            if (HERE/name).read_text()!=text:
                raise ValueError('Evidence artifact differs from published results: '+name)
        else:
            (HERE/name).write_text(text)
    manuscript = HERE/'MANUSCRIPT.md'
    if manuscript.exists():
        text = manuscript.read_text(); begin='<!-- EVIDENCE_TABLE_BEGIN -->'; end='<!-- EVIDENCE_TABLE_END -->'
        table = products(rows)['evidence_table.md']
        updated = text.split(begin)[0]+begin+'\n\n'+table+'\n'+end+text.split(end)[1]
        if args.check:
            if text != updated:
                raise ValueError('Manuscript table differs from saved evidence')
        else:
            manuscript.write_text(updated)
    if args.plot:
        plot(rows)
    print('Verified 8 descriptive result rows; no model fitted.')


if __name__ == '__main__':
    main()
