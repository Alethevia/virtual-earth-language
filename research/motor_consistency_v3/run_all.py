"""Full deterministic replay; refuses to overwrite an existing output directory."""
import argparse,json,math,platform,sys
from pathlib import Path
import numpy,scipy,numba
import study
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=Path('results/reproduced'));a=p.parse_args()
if a.out.exists():raise FileExistsError('Use a new output directory')
lock=json.loads(Path('CALIBRATION_LOCK.json').read_text())
reference=json.loads(Path('REFERENCE.json').read_text())
assert study.source_hashes()==lock['source_sha256']==reference['source_sha256']
study.calibrate(a.out)
cal=json.loads((a.out/'calibration.json').read_text())
for mode,values in lock['thresholds'].items():
 for method,value in values.items():
  assert math.isclose(cal['thresholds'][mode][method],value,rel_tol=1e-8,abs_tol=1e-10),(mode,method)
for condition in study.CONDITIONS:study.evaluate(a.out,condition)
study.summarize(a.out)
actual=json.loads((a.out/'summary.json').read_text())
for condition,modes in reference['counts'].items():
 for mode,counts in modes.items():
  for method,count in zip(reference['method_order'],counts):
   row=next(r for r in actual['results'] if (r['condition'],r['mode'],r['method'])==(condition,mode,method))
   assert row['n']==100 and row['count']==count,(condition,mode,method,row['count'],count)
assert actual['targeted_screen_passed'] is False and actual['extended_screen_passed'] is False
study.save_new(a.out/'runtime.json',dict(python=sys.version,numpy=numpy.__version__,scipy=scipy.__version__,numba=numba.__version__,platform=platform.platform()))
print('REPRODUCED: all 168 count cells, 12 thresholds, and both FAILED scientific screens.')
