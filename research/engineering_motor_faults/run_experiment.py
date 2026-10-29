"""Run the fixed protocol and save all results; no threshold tuning on test data."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import platform
import sys
import numpy as np
import scipy
from motorbench import (DT, WARMUP, FAULT_TIME, METHODS, CONDITIONS,
                        episode, calibration_threshold, first_alarm, wilson)


def run(out):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError("Use a new empty output directory; old results are not overwritten")
    out.mkdir(parents=True, exist_ok=True)
    maxima = np.array([s[round(WARMUP/DT):].max(axis=0)
                       for _, s in (episode(seed) for seed in range(1000, 1039))])
    thresholds = [calibration_threshold(maxima[:, j]) for j in range(3)]
    np.savetxt(out/'calibration_maxima.csv', maxima, delimiter=',',
               header=','.join(METHODS), comments='', fmt='%.12g')
    rows = []
    summary = {}
    for condition in CONDITIONS:
        summary[condition] = {}
        for seed in range(2000, 2060):
            trace, s = episode(seed, condition)
            for j, method in enumerate(METHODS):
                idx = first_alarm(s[:, j], thresholds[j])
                fault = not condition.startswith('healthy')
                alarm_time = None if idx is None else idx*DT
                pre = bool(fault and idx is not None and alarm_time < FAULT_TIME)
                valid = bool(fault and idx is not None and alarm_time >= FAULT_TIME)
                rows.append(dict(condition=condition, seed=seed, method=method,
                    threshold=thresholds[j], max_score=float(s[round(WARMUP/DT):, j].max()),
                    first_alarm_s=alarm_time, pre_fault_alarm=pre, valid_detection=valid,
                    delay_s=alarm_time-FAULT_TIME if valid else None,
                    saturation_fraction=float(np.mean(np.abs(trace[:, 5]) >= 12)),
                    tracking_rmse=float(np.sqrt(np.mean((trace[:, 3]-trace[:, 1])**2)))))
            if seed == 2000:
                np.savetxt(out/f'trace_{condition}.csv', np.c_[trace, s], delimiter=',',
                    header='time,reference,load,true_speed,true_current,voltage,speed_sensor,current_sensor,'+','.join(METHODS),
                    comments='', fmt='%.10g')
        for method in METHODS:
            group = [r for r in rows if r['condition'] == condition and r['method'] == method]
            fault = not condition.startswith('healthy')
            count = sum(r['valid_detection'] if fault else r['first_alarm_s'] is not None for r in group)
            delays = [r['delay_s'] for r in group if r['valid_detection']]
            summary[condition][method] = dict(n=len(group), count=count,
                metric='valid_detection_fraction' if fault else 'false_alarm_fraction',
                rate=count/len(group), wilson95=wilson(count, len(group)),
                pre_fault_alarms=sum(r['pre_fault_alarm'] for r in group),
                median_delay_s=float(np.median(delays)) if delays else None)
        print(condition, {m: summary[condition][m]['count'] for m in METHODS}, flush=True)
    with (out/'episode_metrics.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    document = dict(protocol='PROTOCOL.md v1', calibration_seeds=[1000, 1038],
        test_seeds=[2000, 2059], total_trajectories=399,
        thresholds=dict(zip(METHODS, thresholds)), results=summary)
    (out/'summary.json').write_text(json.dumps(document, indent=2)+'\n')
    lines = ['# Simulation results — protocol v1', '',
        'Synthetic data only. Each cell is count/60; faults require no earlier alarm.', '',
        '| Condition | Tracking | No-load observer | Load-augmented observer |',
        '|---|---:|---:|---:|']
    for c in CONDITIONS:
        lines.append('| '+c+' | '+' | '.join(str(summary[c][m]['count'])+'/60' for m in METHODS)+' |')
    lines += ['', 'Healthy rows report false alarms (lower is better); fault rows report valid detections (higher is better).',
              'Confidence intervals and conditional delays are in summary.json. Healthy_shift is outside the calibration distribution.',
              'No hardware validation, fault-tolerant control, novelty, or publication claim is made.']
    (out/'RESULTS.md').write_text('\n'.join(lines)+'\n')
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file()}
    source_dir = Path(__file__).resolve().parent
    source_hashes = {name: hashlib.sha256((source_dir/name).read_bytes()).hexdigest()
                     for name in ('motorbench.py', 'controller.c', 'run_experiment.py', 'PROTOCOL.md')
                     if (source_dir/name).exists()}
    manifest = dict(python=sys.version, numpy=np.__version__, scipy=scipy.__version__,
        platform=platform.platform(), source_sha256=source_hashes, artifacts_sha256=hashes)
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return document


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', default='results/run_v1')
    args = parser.parse_args()
    run(args.out)
