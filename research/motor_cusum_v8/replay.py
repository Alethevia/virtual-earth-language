"""Clean fixed-seed replay. A successful replay must retain the failed screen."""
import argparse,json,hashlib,math,sys,platform
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import numpy,scipy,numba
import cusum_study as s

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=Path('results/reproduced'));p.add_argument('--workers',type=int,default=2);a=p.parse_args()
 if a.out.exists():raise FileExistsError('Use a new output directory')
 if not 1<=a.workers<=4:raise ValueError('workers must be 1 through 4')
 ref=json.loads((s.HERE/'REFERENCE.json').read_text());lock=json.loads((s.HERE/'CALIBRATION_LOCK.json').read_text())
 assert s.sources()==ref['source_sha256']
 a.out.mkdir(parents=True)
 with ProcessPoolExecutor(a.workers) as ex:
  for f in [ex.submit(s.calibrate,a.out,profile) for profile in s.PROFILES]:f.result()
 s.freeze(a.out)
 cal=json.loads((a.out/'calibration.json').read_text())
 for m in s.STREAMS:
  assert numpy.allclose(cal['rate'][m],lock['rate'][m],rtol=1e-8,atol=1e-9)
  assert math.isclose(cal['universal'][m],lock['universal'][m],rel_tol=1e-8,abs_tol=1e-9)
 with ProcessPoolExecutor(a.workers) as ex:
  tasks=[ex.submit(s.evaluate,a.out,profile,start,start+50) for profile in s.PROFILES+s.STRESS for start in range(61000,61200,50)]
  for f in tasks:f.result()
 s.summarize(a.out)
 actual=json.loads((a.out/'summary.json').read_text())
 rows=[{k:r[k] for k in ref['fields']} for r in actual['results']]
 digest=hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 assert digest==ref['integer_outcome_sha256'],(digest,ref['integer_outcome_sha256'])
 assert actual['screen_passed'] is False and sum(actual['criteria'].values())==16
 assert actual['records']==92400 and actual['cells']==462 and actual['n_cases']==10800
 s.save(a.out/'runtime.json',dict(python=sys.version,numpy=numpy.__version__,scipy=scipy.__version__,numba=numba.__version__,platform=platform.platform()))
 print('REPRODUCED: 462 integer outcome cells, all frozen thresholds, scientific screen remains FAILED 16/20.')

if __name__=='__main__':main()
