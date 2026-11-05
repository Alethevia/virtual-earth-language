"""Full clean V7 replay; fixed references validate all cells, not just selected gains."""
import argparse,concurrent.futures,hashlib,json,math,os,platform,subprocess,sys
from pathlib import Path
import numpy,scipy,numba
import horizon as h

def run(args):
    subprocess.run([sys.executable,'horizon.py',*args],check=True,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})

def count_hash(summary):
    keys=('profile','mode','amplitude','horizon','method','n')
    metrics=('generic_alarm','generic_false','wrong_any','first_correct','within_5s','within_30s','eventual_correct','pre_fault_unique')
    table=[{k:r[k] for k in keys+tuple(m+'_count' for m in metrics)} for r in summary['results']]
    return hashlib.sha256(json.dumps(table,sort_keys=True,separators=(',',':')).encode()).hexdigest()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=Path('results/reproduced'));p.add_argument('--workers',type=int,default=2);a=p.parse_args()
    os.chdir(Path(__file__).resolve().parent)
    if a.out.exists():raise FileExistsError('New output directory required')
    if not 1<=a.workers<=4:raise ValueError('workers must be 1..4')
    lock=json.loads(Path('CALIBRATION_LOCK.json').read_text());ref=json.loads(Path('REFERENCE.json').read_text())
    assert h.sources()==lock['source_sha256']
    a.out.mkdir(parents=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        list(pool.map(run,[['calibrate','--out',str(a.out),'--profile',profile] for profile in h.PROFILES]))
    h.freeze(a.out);cal=json.loads((a.out/'calibration.json').read_text())
    for name in ('short','long'):
        assert math.isclose(cal['thresholds'][name],lock['thresholds'][name],rel_tol=1e-10,abs_tol=1e-10)
        for profile in h.PROFILES:
            assert math.isclose(cal['groups'][profile][name],lock['groups'][profile][name],rel_tol=1e-10,abs_tol=1e-10)
    jobs=[['evaluate','--out',str(a.out),'--profile',profile,'--start',str(start),'--stop',str(start+50)] for profile in h.PROFILES for start in range(50000,50200,50)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:list(pool.map(run,jobs))
    h.summarize(a.out);s=json.loads((a.out/'summary.json').read_text())
    assert count_hash(s)==ref['count_table_sha256'],'A reference outcome changed'
    assert s['screen_passed'] is False and sum(s['criteria'].values())==16
    h.save(a.out/'runtime.json',dict(python=sys.version,numpy=numpy.__version__,scipy=scipy.__version__,numba=numba.__version__,platform=platform.platform()))
    print('REPRODUCED all 300 cells, 10 threshold values, 60000 records. Scientific screen remains FAILED (16/20).')
