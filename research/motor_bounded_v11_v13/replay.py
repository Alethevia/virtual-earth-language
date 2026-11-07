"""Full clean-source replay of all three locked rounds. No output overwrite."""
from pathlib import Path
import argparse,hashlib,json,math,shutil,subprocess,sys
import study
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--workers',type=int,default=2);a=p.parse_args()
here=Path(__file__).resolve().parent;out=a.out.resolve()
if out.exists():raise FileExistsError('Use a new output directory')
out.mkdir(parents=True);shutil.copyfile(here/'SOURCE_LOCK.json',out/'SOURCE_LOCK.json')
ref=json.loads((here/'REFERENCE.json').read_text())
assert study.sha(here/'study.py')==ref['source_sha256']
for phase in ('cal11','eval11','cal12','eval12','select13','eval13'):
    subprocess.run([sys.executable,'-u',str(here/'study.py'),phase,'--root',str(out),'--workers',str(a.workers)],check=True,cwd=here)
keys=('config','case','method','n')+study.METRICS
for rnd in (11,12,13):
    actual=json.loads((out/f'r{rnd}/summary.json').read_text())
    rows=[{k:r[k] for k in keys} for r in actual['results']]
    digest=hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    expected=ref['rounds'][str(rnd)]
    assert digest==expected['integer_outcome_sha256'],(rnd,'Outcome digest mismatch')
    assert len(rows)==expected['cells'] and actual['n_records']==expected['records']
    if rnd<13:
        cal=json.loads((out/f'r{rnd}/calibration.json').read_text())
        for g in cal['groups']:
            th=g.get('threshold',g.get('thresholds'));ex=expected['thresholds'][g['name']]
            if isinstance(th,dict):
                assert all(math.isclose(th[k],ex[k],rel_tol=1e-8,abs_tol=1e-10) for k in th)
            else:assert math.isclose(th,ex,rel_tol=1e-8,abs_tol=1e-10)
    else:
        assert actual['selected']==ref['selected']
        q=actual['criteria'][actual['selected']]
        assert q['matched_confirmation_pass'] is True and q['broad_robustness_pass'] is False
subprocess.run([sys.executable,str(here/'verify.py'),str(out)],check=True,cwd=here)
subprocess.run([sys.executable,str(here/'paired_analysis.py'),str(out)],check=True,cwd=here)
print('REPRODUCED: 201 integer cells, 48,600 records, 27 thresholds. Matched-condition pass; broad robustness FAIL retained.')
