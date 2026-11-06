"""Reproduce V10 without replacing prior outputs."""
import argparse,hashlib,json,math,platform,sys
from pathlib import Path
import numpy,scipy
import oracle as o
import verify
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=Path('results/reproduced'));a=p.parse_args()
if a.out.exists():raise FileExistsError('Use a new output directory')
ref=json.loads(Path('REFERENCE.json').read_text());lock=json.loads(Path('CALIBRATION_LOCK.json').read_text())
assert o.sha('oracle.py')==ref['source_sha256']==lock['source_sha256']
a.out.mkdir(parents=True)
o.oracle_grid(a.out);o.monte_carlo(a.out);o.calibrate(a.out)
cal=json.loads((a.out/'calibration.json').read_text())
for profile,values in lock['thresholds'].items():
 for got,want in zip(cal['groups'][profile]['thresholds'],values):
  assert math.isclose(got,want,rel_tol=1e-10,abs_tol=1e-10)
for profile in o.PROFILES:o.evaluate(a.out,profile)
o.summarize(a.out)
summary=json.loads((a.out/'summary.json').read_text())
rows=[{k:r[k] for k in ref['count_keys']} for r in summary['rows']]
digest=hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()
assert digest==ref['count_digest'],(digest,ref['count_digest'])
assert summary['records']==ref['scan_records'] and summary['cells']==ref['scan_cells']
verify.run(a.out)
o.save(a.out/'runtime.json',dict(python=sys.version,numpy=numpy.__version__,scipy=scipy.__version__,platform=platform.platform()))
print('REPRODUCED: 1296 power cells,240000 Gaussian windows,64 scan cells. This is not a deployment pass.')
