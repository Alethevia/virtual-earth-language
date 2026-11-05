"""Full fixed-seed reproduction, refusing existing output directories."""
from pathlib import Path
import argparse,json,math,sys,platform
import numpy,scipy,numba
import telemetry as t
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=Path('results/reproduced'));a=p.parse_args()
if a.out.exists():raise FileExistsError('Use a new output directory')
lock=json.loads(Path('CALIBRATION_LOCK.json').read_text());ref=json.loads(Path('REFERENCE.json').read_text())
assert t.source_hashes()==lock['source_sha256']==ref['source_sha256']
t.calibrate(a.out)
cal=json.loads((a.out/'calibration.json').read_text())
for k,v in lock['thresholds'].items():assert math.isclose(cal['thresholds'][k],v,rel_tol=1e-8,abs_tol=1e-10),(k,v)
for c in t.CONDITIONS:t.evaluate(a.out,c)
t.summarize(a.out)
s=json.loads((a.out/'summary.json').read_text())
for c,counts in ref['counts'].items():
 for m,want in zip(ref['method_order'],counts):
  got=next(r for r in s['results'] if r['condition']==c and r['method']==m)
  assert got['n']==100 and got['count']==want,(c,m,got['count'],want)
assert s['targeted_screen_passed'] is True and len(s['criteria'])==29
# The 29 primary-attribution/availability checks are NOT a general false-alarm guarantee.
r=next(r for r in s['results'] if r['condition']=='healthy_slow_reporting' and r['method']=='time_quality')
assert r['any_alarm_count']==45 and r['count']==4
assert next(r for r in s['results'] if r['condition']=='healthy_asynchronous' and r['method']=='time_quality')['coverage']==0
assert next(r for r in s['results'] if r['condition']=='two_aux_common_bias' and r['method']=='time_quality')['count']==100
t.save_new(a.out/'runtime.json',dict(python=sys.version,numpy=numpy.__version__,scipy=scipy.__version__,numba=numba.__version__,platform=platform.platform()))
print('REPRODUCED: 228 rate cells, 4 thresholds, 29 targeted checks; generic-alarm, availability and common-mode failures preserved.')
