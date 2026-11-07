"""Declared paired contrasts plus labelled exploratory pulse/delay comparisons."""
from pathlib import Path
import json,csv,argparse
import numpy as np

def paired(root):
    rng=np.random.default_rng(202611061113);rows=[]
    def compare(roundnum,cfgA,caseA,methodA,cfgB,caseB,methodB,metric,label):
        path=root/f'r{roundnum}'
        def load(cfg):return json.loads((path/(cfg+'.json')).read_text())['rows']
        def arr(cfg,case,m):return np.array([x[metric] for x in sorted([r for r in load(cfg) if r['case']==case and r['method']==m],key=lambda r:r['seed'])],float)
        a=arr(cfgA,caseA,methodA);b=arr(cfgB,caseB,methodB);assert a.shape==b.shape
        d=a-b;idx=rng.integers(0,len(d),size=(10000,len(d)));boot=d[idx].mean(axis=1)
        rows.append(dict(round=roundnum,contrast=label,metric=metric,n_pairs=len(d),difference=float(d.mean()),
                         ci95=np.quantile(boot,[.025,.975]).tolist(),scope='paired exploratory; no multiplicity adjustment'))
    m='known_target_mean5'
    compare(11,'f100_s1_r0.9','primary05',m,'f20_s1_r0.9','primary05',m,'within5','100Hz minus20Hz, original noise')
    compare(11,'f20_s0.7_r0.9','primary05',m,'f20_s1_r0.9','primary05',m,'within5','20Hz noise0.7 minus original')
    compare(11,'f20_s0.5_r0.9','primary05',m,'f20_s1_r0.9','primary05',m,'within5','20Hz noise0.5 minus original')
    for cfg in ('f100_s1_r0','f2_s1_r0.9','f20_s1_r0.9','f100_s1_r0.9','f20_s0.5_r0.9'):
        for other in ('mean5','raw_scan'):
            for case,metric in (('healthy','any_alarm'),('primary05','within5')):
                compare(12,cfg,case,'innovation_scan',cfg,case,other,metric,f'{cfg}: innovation minus {other}; {case}')
    for other in ('raw_scan','innovation_scan'):
        compare(12,'f20_s0.5_r0.9','primary05','mean5','f20_s0.5_r0.9','primary05',other,'within5','selection metric: mean minus '+other)
    compare(12,'f20_s0.5_r0.9','pulse','innovation_scan','f20_s0.5_r0.9','pulse','mean5','first_correct','EXPLORATORY pulse before recovery: innovation minus mean')
    return rows

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();rows=paired(a.root)
    with (a.root/'PAIRED.json').open('x') as f:json.dump(rows,f,indent=2)
    with (a.root/'paired.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps([x for x in rows if x['round']==11 or x['contrast'].startswith(('selection','EXPLORATORY'))],indent=2))
