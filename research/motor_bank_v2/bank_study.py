"""Locked current-only model-bank study. Simulation only. See PROTOCOL.md.

Run: python bank_study.py tests; python bank_study.py calibrate --out results
     python bank_study.py evaluate --out results --condition healthy
     python bank_study.py summarize --out results
"""
import argparse
import csv
import hashlib
import json
import math
import platform
import sys
import time
import unittest
from functools import lru_cache
from pathlib import Path
import numpy as np
import scipy
from scipy.linalg import solve_discrete_are
from numba import njit
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engineering_motor_faults'))
import motorbench as mb

PROTOCOL_COMMIT = '907e4a13065f51a63d66f97b09c02266576a9298'
ORIGINAL_BLOB = '681bceb05fd29c17e131e5872291be556c9c2ca1'
CORE = ('healthy','healthy_shift','bias','bias_shift','drift','stuck')
STRESS = ('startup_bias','healthy_late_shift','bias_late_shift',
          'healthy_outside_bank','healthy_nonlinear','bias_nonlinear')
STREAMS = ('no_load','load_augmented','bank_cumulative','bank_recent','bank_residual_min')
RULES = ('no_load_original','load_original','no_load_matched','load_matched',
         'bank_cumulative','bank_recent','bank_residual_min')
COLUMNS = (0,1,0,1,2,3,4)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_hashes():
    b=Path(mb.__file__).read_bytes()
    assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==ORIGINAL_BLOB
    return {'motorbench.py':sha(mb.__file__),'bank_study.py':sha(__file__)}


def save_new(path, doc):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:
        json.dump(doc,f,indent=2,allow_nan=False)
        f.write('\n')


@lru_cache(maxsize=1)
def design():
    configs=np.array([(r,l) for r in np.round(np.arange(1.8,3.001,.05),6)
                      for l in (.018,.019,.020,.021,.022)])
    A=np.zeros((127,3,3));B=np.zeros((127,3));G=np.zeros((127,3));S=np.ones(127)
    for j,aug in enumerate((False,True)):
        a,b,g=mb.observer_design(aug)
        n=len(g);A[j,:n,:n]=a;B[j,:n]=b;G[j,:n]=g
    for j,(r,l) in enumerate(configs,2):
        p=mb.Motor(R=float(r),L=float(l))
        a,_=p.continuous();ac=np.zeros((3,3));ac[:2,:2]=a;ac[1,2]=-1/p.J
        ad,bd=mb.discretize(ac,np.array([[1/p.L],[0.],[0.]]))
        c=np.array([[1.,0.,0.]])
        P=solve_discrete_are(ad.T,c.T,np.diag([.0001,.05,.000001]),np.array([[.015**2]]))
        S[j]=P[0,0]+.015**2;A[j]=ad;B[j]=bd[:,0];G[j]=P[:,0]/S[j]
    for arr in (configs,A,B,G,S):
        arr.setflags(write=False)
    return configs,A,B,G,S


@njit(cache=True)
def filter_kernel(measured,A,B,G,S):
    # measured columns: applied voltage, measured current, measured speed ONLY.
    n=len(measured);m=len(S);x=np.zeros((m,3));cost=np.zeros(m);recent=np.zeros(m)
    sm=np.zeros(5);out=np.empty((n,5));selected=np.empty((n,2),np.int64)
    a=math.exp(-.1);discount=math.exp(-.01/2)
    for t in range(n):
        u=measured[t-1,0] if t else 0.
        yi=measured[t,1];yw=measured[t,2]
        for j in range(m):
            p0=A[j,0,0]*x[j,0]+A[j,0,1]*x[j,1]+A[j,0,2]*x[j,2]+B[j,0]*u
            p1=A[j,1,0]*x[j,0]+A[j,1,1]*x[j,1]+A[j,1,2]*x[j,2]+B[j,1]*u
            p2=A[j,2,0]*x[j,0]+A[j,2,1]*x[j,1]+A[j,2,2]*x[j,2]+B[j,2]*u
            innovation=yi-p0
            x[j,0]=p0+G[j,0]*innovation
            x[j,1]=p1+G[j,1]*innovation
            x[j,2]=p2+G[j,2]*innovation
            if j>=2:
                loss=innovation*innovation/S[j]+math.log(S[j])
                cost[j]+=loss;recent[j]=discount*recent[j]+loss
        ic=2;ir=2;minimum=abs(yw-x[2,1])
        for j in range(3,m):
            if cost[j]<cost[ic]:ic=j
            if recent[j]<recent[ir]:ir=j
            minimum=min(minimum,abs(yw-x[j,1]))
        residual=(abs(yw-x[0,1]),abs(yw-x[1,1]),abs(yw-x[ic,1]),abs(yw-x[ir,1]),minimum)
        for k in range(5):
            sm[k]=a*sm[k]+(1-a)*residual[k];out[t,k]=sm[k]
        selected[t,0]=ic-2;selected[t,1]=ir-2
    return out,selected


def diagnose(measured):
    y=np.asarray(measured,float)
    if y.ndim!=2 or y.shape[1]!=3 or len(y)<2 or not np.isfinite(y).all():
        raise ValueError('Expected finite (N,3) voltage/current/speed, not simulator states')
    return filter_kernel(np.ascontiguousarray(y),*design()[1:])


def stress_episode(seed,condition):
    if condition not in STRESS:raise ValueError('Unknown stress condition')
    rng=np.random.default_rng(seed)
    p=mb.Motor(J=.002*rng.uniform(.9,1.1),b=.002*rng.uniform(.9,1.1),
               K=.05*rng.uniform(.97,1.03),R=2*rng.uniform(.95,1.05),L=.02*rng.uniform(.95,1.05))
    nonlinear=condition.endswith('nonlinear')
    if condition=='healthy_outside_bank':
        p=mb.Motor(J=p.J,b=p.b*1.5,K=p.K,R=p.R*1.65,L=p.L)
    ad,bd=mb.discretize(*p.continuous())
    shifted=mb.Motor(J=p.J,b=p.b*1.3,K=p.K,R=p.R*1.35,L=p.L)
    sad,sbd=mb.discretize(*shifted.continuous())
    refs=rng.uniform(25,110,4);loads=np.r_[0,rng.uniform(.005,.035,3)];sign=rng.choice([-1,1])
    n=round(mb.DURATION/mb.DT);noise_factor=1.5 if nonlinear else 1.
    wn=rng.normal(0,.25,n)*noise_factor;inoise=rng.normal(0,.015,n)*noise_factor
    extra=np.random.default_rng(seed+1000000)
    change=float(extra.uniform(6,9));late_fault=float(extra.uniform(10,13))
    onset=None if condition.startswith('healthy') else (1. if condition=='startup_bias' else late_fault)
    x=np.zeros(2);pi=mb.PI();tr=np.empty((n,8))
    for k in range(n):
        t=k*mb.DT;ref=refs[np.searchsorted([5,10,14],t,side='right')]
        load=loads[np.searchsorted([3,9,14],t,side='right')]
        if nonlinear:load+=.012*math.tanh(x[1]/3)
        yw=x[1]+wn[k];yi=x[0]+inoise[k]
        if onset is not None and t>=onset:yw+=sign*6
        u=pi.step(ref-yw);tr[k]=t,ref,load,x[1],x[0],u,yw,yi
        active=condition.endswith('late_shift') and t>=change
        aa,bb=(sad,sbd) if active else (ad,bd)
        x=aa@x+bb@np.array([u,load])
    return tr,onset


def episode(seed,condition):
    if condition in CORE:
        return mb.generate_episode(seed,condition),None if condition.startswith('healthy') else 10.
    return stress_episode(seed,condition)


def calibrate(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    if (out/'calibration.json').exists():raise FileExistsError('Calibration already exists')
    lock=dict(protocol_commit=PROTOCOL_COMMIT,source_hashes=source_hashes(),
              python=sys.version,numpy=np.__version__,scipy=scipy.__version__,platform=platform.platform())
    save_new(out/'source_lock.json',lock)
    rng=np.random.default_rng(774411);rows=[];start=time.perf_counter()
    for seed in range(9400,9559):
        condition='healthy_shift' if rng.random()<.5 else 'healthy'
        tr,_=episode(seed,condition);s,_=diagnose(tr[:,[5,7,6]])
        rows.append(dict(seed=seed,condition=condition,maxima=s[200:].max(axis=0).tolist()))
    maxima=np.array([r['maxima'] for r in rows]);threshold=[mb.calibration_threshold(maxima[:,j]) for j in range(5)]
    doc=dict(n=159,rank=152,seed_range=[9400,9558],thresholds=dict(zip(STREAMS,threshold)),rows=rows,
             source_hashes=lock['source_hashes'],elapsed_seconds=time.perf_counter()-start)
    save_new(out/'calibration.json',doc)
    print('CALIBRATED',doc['thresholds'],'seconds',doc['elapsed_seconds'],flush=True)


def evaluate(out,condition,start=None,stop=None):
    out=Path(out);cal=json.loads((out/'calibration.json').read_text())
    assert cal['source_hashes']==source_hashes(),'Source changed after calibration'
    if condition not in CORE+STRESS:raise ValueError('Unknown evaluation condition')
    low,high=(11000,11200) if condition in CORE else (12000,12100)
    start=low if start is None else start;stop=high if stop is None else stop
    if not low<=start<stop<=high:raise ValueError('Outside locked seed range')
    dest=out/f'{condition}_{start}_{stop}.json'
    if dest.exists():raise FileExistsError('Do not overwrite prior evaluation')
    thresholds=[9.466770991995034,10.076904226760591]+[cal['thresholds'][k] for k in STREAMS]
    rows=[];tic=time.perf_counter()
    for seed in range(start,stop):
        tr,onset=episode(seed,condition);s,inds=diagnose(tr[:,[5,7,6]])
        for name,col,th in zip(RULES,COLUMNS,thresholds):
            hits=np.flatnonzero(s[200:,col]>th);alarm=None if not len(hits) else (int(hits[0])+200)*.01
            early=bool(onset is not None and alarm is not None and alarm<onset)
            detected=bool(onset is not None and alarm is not None and alarm>=onset)
            rows.append(dict(seed=seed,condition=condition,method=name,threshold=th,onset=onset,
                alarm_time=alarm,pre_fault_alarm=early,valid_detection=detected,
                event=bool(alarm is not None) if onset is None else detected,
                delay=None if not detected else alarm-onset,
                selected_R_final=float(design()[0][inds[-1,0],0]),
                selected_L_final=float(design()[0][inds[-1,0],1])))
    doc=dict(condition=condition,seed_range=[start,stop-1],n_episodes=stop-start,rows=rows,
             source_hashes=source_hashes(),calibration_sha256=sha(out/'calibration.json'),
             elapsed_seconds=time.perf_counter()-tic)
    save_new(dest,doc)
    print('EVALUATED',condition,start,stop,'seconds',doc['elapsed_seconds'],flush=True)


def summarize(out):
    out=Path(out);cal=json.loads((out/'calibration.json').read_text());rows=[];files=[]
    for cond in CORE+STRESS:
        paths=sorted(out.glob(cond+'_*.json'))
        # Exact condition field avoids healthy_* prefix collisions.
        docs=[(p,json.loads(p.read_text())) for p in paths]
        docs=[(p,d) for p,d in docs if d.get('condition')==cond]
        rr=[r for _,d in docs for r in d['rows']]
        expected=set(range(11000,11200) if cond in CORE else range(12000,12100))
        for method in RULES:
            ss=[r['seed'] for r in rr if r['method']==method]
            assert len(ss)==len(expected) and set(ss)==expected,(cond,method,'missing or duplicate')
        for p,d in docs:
            assert d['source_hashes']==cal['source_hashes']
            assert d['calibration_sha256']==sha(out/'calibration.json')
            files.append(p)
        rows.extend(rr)
    summary=[];paired=[];rng=np.random.default_rng(44991)
    for cond in CORE+STRESS:
        for method in RULES:
            r=sorted([x for x in rows if x['condition']==cond and x['method']==method],key=lambda x:x['seed'])
            n=len(r);count=sum(x['event'] for x in r);delays=[x['delay'] for x in r if x['delay'] is not None]
            summary.append(dict(condition=cond,method=method,n=n,count=count,rate=count/n,
                wilson95=mb.wilson(count,n),pre_fault_alarms=sum(x['pre_fault_alarm'] for x in r),
                conditional_median_delay=None if not delays else float(np.median(delays))))
        rr={m:np.array([x['event'] for x in sorted([r for r in rows if r['condition']==cond and r['method']==m],key=lambda r:r['seed'])],int) for m in RULES}
        for comparator in ('no_load_matched','load_matched'):
            diff=rr['bank_cumulative']-rr[comparator]
            boot=diff[rng.integers(0,len(diff),size=(10000,len(diff)))].mean(axis=1)
            paired.append(dict(condition=cond,contrast='bank_cumulative - '+comparator,
                difference=float(diff.mean()),percentile95=np.quantile(boot,[.025,.975]).tolist(),
                note='Lower is better for healthy false alarms; higher is better for detections. Exploratory, unadjusted.'))
    lookup={(r['condition'],r['method']):r['rate'] for r in summary}
    passed=all(lookup[c,'bank_cumulative']<=.10 for c in ('healthy','healthy_shift')) and all(lookup[c,'bank_cumulative']>=.60 for c in ('bias','bias_shift')) and lookup['stuck','bank_cumulative']>=.90
    doc=dict(protocol_commit=PROTOCOL_COMMIT,primary_screen_passed=passed,calibration_episodes=159,
        core_trajectories=1200,stress_trajectories=600,core_independent_seed_groups=200,
        stress_independent_seed_groups=100,methods=7,results=summary,paired=paired,
        source_hashes=cal['source_hashes'],calibration_sha256=sha(out/'calibration.json'),
        raw_file_sha256={p.name:sha(p) for p in files},hardware_validated=False,novel_algorithm_claim=False)
    save_new(out/'summary.json',doc)
    for filename,records in [('episode_metrics.csv',rows),('rates.csv',summary),('paired.csv',paired)]:
        with (out/filename).open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    print('PRIMARY_SCREEN',passed)
    for r in summary:
        if r['method'] in ('load_original','load_matched','bank_cumulative'):
            print(r['condition'],r['method'],f"{r['count']}/{r['n']}",r['wilson95'])


class IntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tr=mb.generate_episode(8190,'bias');cls.measured=cls.tr[:,[5,7,6]]
        cls.result=diagnose(cls.measured)
    def test_original_blob(self):source_hashes()
    def test_original_observer_parity(self):
        old=mb.scores(mb.residuals(self.tr))[:,1:]
        np.testing.assert_allclose(self.result[0][:,:2],old,rtol=1e-10,atol=1e-9)
    def test_bank_count(self):self.assertEqual(len(design()[0]),125)
    def test_causality(self):
        for stop in (201,999,1301):
            a,b=diagnose(self.measured[:stop])
            np.testing.assert_array_equal(a,self.result[0][:stop]);np.testing.assert_array_equal(b,self.result[1][:stop])
    def test_selection_does_not_read_speed(self):
        y=self.measured.copy();y[:,2]=np.random.default_rng(8233).normal(0,100,len(y))
        np.testing.assert_array_equal(diagnose(y)[1],self.result[1])
    def test_ground_truth_not_an_input(self):
        tr=self.tr.copy();tr[:,[2,3,4]]=-99999
        np.testing.assert_array_equal(diagnose(tr[:,[5,7,6]])[0],self.result[0])
    def test_reject_full_simulator_trace(self):
        with self.assertRaises(ValueError):diagnose(self.tr)
    def test_reject_nonfinite(self):
        y=self.measured.copy();y[0,0]=np.nan
        with self.assertRaises(ValueError):diagnose(y)
    def test_seeds_disjoint(self):
        sets=[set(range(8100,8120)),set(range(9400,9559)),set(range(11000,11200)),set(range(12000,12100))]
        for i,a in enumerate(sets):
            for b in sets[i+1:]:self.assertFalse(a&b)
    def test_stress_deterministic(self):
        for c in STRESS:
            t,o=stress_episode(8199,c);t2,o2=stress_episode(8199,c)
            np.testing.assert_array_equal(t,t2);self.assertEqual(o,o2)
            self.assertTrue(np.isfinite(t).all());self.assertLessEqual(abs(t[:,5]).max(),12)
    def test_calibration_rank(self):self.assertEqual(mb.calibration_threshold(np.arange(159.)),151.)
    def test_finite_scores(self):self.assertTrue(np.isfinite(self.result[0]).all())
    def test_startup_before_monitor(self):self.assertEqual(stress_episode(8199,'startup_bias')[1],1.)
    def test_original_bank_member_parity(self):
        _,A,B,G,_=design();idx=2+list(map(tuple,design()[0])).index((2.,.02))
        np.testing.assert_array_equal(A[idx],A[1]);np.testing.assert_array_equal(B[idx],B[1]);np.testing.assert_array_equal(G[idx],G[1])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase',choices=('tests','calibrate','evaluate','summarize'))
    p.add_argument('--out',type=Path,default=Path('results'))
    p.add_argument('--condition',choices=CORE+STRESS)
    p.add_argument('--start',type=int);p.add_argument('--stop',type=int)
    a=p.parse_args()
    if a.phase=='tests':
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(IntegrityTests))
        sys.exit(not result.wasSuccessful())
    elif a.phase=='calibrate':calibrate(a.out)
    elif a.phase=='evaluate':evaluate(a.out,a.condition,a.start,a.stop)
    else:summarize(a.out)
