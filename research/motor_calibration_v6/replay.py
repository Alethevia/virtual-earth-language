"""Clean full replay. Parallelism changes scheduling, not experiment code/seeds."""
import argparse,hashlib,json,math,platform,sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy,scipy,numba
import calibration_study as study

def run_condition(item):
    out,condition=item
    study.evaluate(Path(out),condition)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=Path('results/reproduced'));p.add_argument('--workers',type=int,default=2);a=p.parse_args()
    if a.out.exists():raise FileExistsError('Use a new output directory')
    if not 1<=a.workers<=4:raise ValueError('workers must be 1..4')
    lock=json.loads(Path('CALIBRATION_LOCK.json').read_text());ref=json.loads(Path('REFERENCE.json').read_text())
    assert study.sources()==lock['source_sha256']==ref['source_sha256']
    study.calibrate(a.out)
    cal=json.loads((a.out/'calibration.json').read_text())
    for name,want in lock['thresholds'].items():
        numpy.testing.assert_allclose(cal['thresholds'][name],want,rtol=1e-9,atol=1e-10)
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        list(pool.map(run_condition,[(str(a.out),c) for c in study.CONDITIONS]))
    study.summarize(a.out)
    actual=json.loads((a.out/'summary.json').read_text())
    compact=[{k:r[k] for k in ref['count_signature_fields']} for r in actual['results']]
    digest=hashlib.sha256(json.dumps(compact,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    assert digest==ref['count_signature_sha256'],(digest,ref['count_signature_sha256'])
    assert actual['targeted_screen_passed']==ref['targeted_screen_passed']
    assert len(actual['criteria'])==ref['checks_passed'] and all(actual['criteria'].values())
    study.save_new(a.out/'runtime.json',dict(python=sys.version,numpy=numpy.__version__,scipy=scipy.__version__,numba=numba.__version__,platform=platform.platform()))
    print('REPRODUCED: all 288 discrete result cells, 8 thresholds and 60 checks. Correlation/metadata/common-mode failures preserved.')
