"""Replay all conditions; an engineering-screen pass is not broad robustness."""
import argparse,json,math,sys,platform
from pathlib import Path
import numpy,scipy,numba
import experiment as e
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=Path('results/reproduced'));a=p.parse_args()
if a.out.exists():raise FileExistsError('Use a NEW output directory')
reference=json.loads(Path('REFERENCE.json').read_text())
lock=json.loads(Path('CALIBRATION_LOCK.json').read_text())
assert e.source_hashes()==reference['source_sha256']==lock['source_sha256']
e.calibration(a.out)
cal=json.loads((a.out/'calibration.json').read_text())
for mode in ('passive','active'):
 for key,value in lock['thresholds'][mode].items():
  assert math.isclose(cal['thresholds'][mode][key],value,rel_tol=1e-8,abs_tol=1e-10)
for condition in e.CONDITIONS:e.evaluate(a.out,condition)
e.summarize(a.out)
actual=json.loads((a.out/'summary.json').read_text())
for c,modes in reference['counts'].items():
 for mode,counts in modes.items():
  for method,count in zip(reference['method_order'],counts):
   row=next(r for r in actual['results'] if (r['condition'],r['mode'],r['method'])==(c,mode,method))
   assert row['n']==100 and row['count']==count,(c,mode,method,row['count'],count)
for mode in ('passive','active'):
 assert actual['criteria'][mode]['single_fault_screen_passed'] is reference['single_fault_screens'][mode]
e.save_new(a.out/'runtime.json',dict(python=sys.version,platform=platform.platform(),numpy=numpy.__version__,scipy=scipy.__version__,numba=numba.__version__))
print('REPRODUCED: 322 reference cells and 6 thresholds. Targeted screens pass; common-mode/timing/noise failures preserved.')
