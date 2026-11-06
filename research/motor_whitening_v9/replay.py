"""Clean full same-seed replay. Reject overwrite; preserve failed science screen."""
import argparse, concurrent.futures, hashlib, json, os, subprocess, sys
from pathlib import Path
import numpy as np
import whitening as w

def invoke(args):
    subprocess.run([sys.executable,'whitening.py',*args],check=True)

def digest(results):
    keys=['profile','mode','amplitude','horizon','method']+[m+'_count' for m in w.METRICS]
    data=[{k:r[k] for k in keys} for r in results]
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def run(out,workers):
    if out.exists():raise FileExistsError('Use a new output directory')
    ref=json.loads(Path('REFERENCE.json').read_text());assert w.sources()==ref['source_hashes']
    invoke(['train','--out',str(out)])
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(invoke,[['calibrate','--out',str(out),'--profile',p] for p in w.PROFILES]))
    invoke(['freeze','--out',str(out)])
    cal=json.loads((out/'calibration.json').read_text())
    for p in w.PROFILES:np.testing.assert_allclose(cal['thresholds'][p],ref['thresholds'][p],rtol=1e-8,atol=1e-10)
    jobs=[['evaluate','--out',str(out),'--profile',p,'--start',str(s),'--stop',str(s+100)] for p in w.PROFILES+w.STRESS for s in (70000,70100)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:list(ex.map(invoke,jobs))
    invoke(['summarize','--out',str(out)])
    d=json.loads((out/'summary.json').read_text())
    assert digest(d['results'])==ref['integer_results_sha256']
    assert d['screen_passed'] is False and sum(d['criteria'].values())==17
    assert (d['n_cases'],d['records'],d['cells'])==(9200,81200,406)
    print('REPRODUCED: 406 cells, all outcome counts, 20 thresholds; scientific screen remains FAILED17/20.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--workers',type=int,default=2);a=p.parse_args()
    if not 1<=a.workers<=2:raise ValueError('Bounded replay supports 1-2 workers')
    os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1';run(a.out,a.workers)
