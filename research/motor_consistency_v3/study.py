"""V3 causal electrical-consistency triage with active/passive paired simulation.
No hardware, safety, novelty, or unique-cause identification claim. See PROTOCOL.md.
"""
import argparse, csv, hashlib, json, math, platform, sys, time
from pathlib import Path
import numpy as np
import scipy
from numba import njit
from box_solver import box_fit
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'motor_bank_v2'))
import bank_study as v2
mb=v2.mb
CONDITIONS=v2.CORE+v2.STRESS+('healthy_voltage_bias','healthy_current_bias')
METHODS=('v2_bank','electrical_single','electrical_switch','bias_gate_no_switch','triage','always_abstain')
FIT_LIMIT=.04
CAL_SEEDS=range(19000,19159)
TEST_SEEDS=range(21000,21100)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def source_hashes():
    return {p.name:sha(p) for p in (Path(mb.__file__),Path(v2.__file__),HERE/'study.py',HERE/'box_solver.py')}

def save_new(path,doc):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(doc,f,indent=2,allow_nan=False);f.write('\n')


def simulate(seed,condition,probe):
    """Original V1/V2 plant; probe modifies reference, never bypasses +/-12V PI.
    Evaluation truth remains outside detector inputs. Extra channel corruption is
    applied only to logged signals; actual speed sensor remains healthy there.
    """
    if condition not in CONDITIONS:raise ValueError(condition)
    rng=np.random.default_rng(seed)
    p=mb.Motor(J=.002*rng.uniform(.9,1.1),b=.002*rng.uniform(.9,1.1),
               K=.05*rng.uniform(.97,1.03),R=2*rng.uniform(.95,1.05),L=.02*rng.uniform(.95,1.05))
    if condition in ('healthy_shift','bias_shift'):
        p=mb.Motor(J=p.J,b=p.b*1.3,K=p.K,R=p.R*1.35,L=p.L)
    if condition=='healthy_outside_bank':
        p=mb.Motor(J=p.J,b=p.b*1.5,K=p.K,R=p.R*1.65,L=p.L)
    ad,bd=mb.discretize(*p.continuous())
    sp=mb.Motor(J=p.J,b=p.b*1.3,K=p.K,R=p.R*1.35,L=p.L)
    sad,sbd=mb.discretize(*sp.continuous())
    refs=rng.uniform(25,110,4);loads=np.r_[0,rng.uniform(.005,.035,3)];sign=rng.choice([-1,1])
    nonlinear=condition.endswith('nonlinear');factor=1.5 if nonlinear else 1.
    wn=rng.normal(0,.25,1800)*factor;inoise=rng.normal(0,.015,1800)*factor
    ex=np.random.default_rng(seed+1000000)
    change=float(ex.uniform(6,9));late=float(ex.uniform(10,13))
    onset=None if condition.startswith('healthy') else (10. if condition in v2.CORE else (1. if condition=='startup_bias' else late))
    x=np.zeros(2);pi=mb.PI();tr=np.empty((1800,8));base=np.empty(1800);held=0.
    for k in range(1800):
        t=k*.01;ref=refs[np.searchsorted([5,10,14],t,side='right')];base[k]=ref
        if probe and k>=200:ref+=8.*(1 if ((k-200)//40)%2==0 else -1)
        load=loads[np.searchsorted([3,9,14],t,side='right')]
        if nonlinear:load+=.012*math.tanh(x[1]/3)
        yw=x[1]+wn[k];yi=x[0]+inoise[k]
        if onset is None or t<onset:held=yw
        elif condition=='stuck':yw=held
        elif condition=='drift':yw+=sign*10*(t-onset)/(18-onset)
        else:yw+=sign*6
        u=pi.step(ref-yw);tr[k]=t,ref,load,x[1],x[0],u,yw,yi
        aa,bb=(sad,sbd) if condition.endswith('late_shift') and t>=change else (ad,bd)
        x=aa@x+bb@np.array([u,load])
    # These two negative controls violate the declared trusted-current/voltage assumption.
    if condition=='healthy_voltage_bias':tr[tr[:,0]>=late,5]+=sign*.3
    if condition=='healthy_current_bias':tr[tr[:,0]>=late,7]+=sign*.15
    return tr,onset,base


@njit(cache=True)
def electrical_kernel(y):
    # Only applied-voltage reading, current reading, speed reading.
    n=(len(y)-1)//10;z=np.empty((n,4))
    for j in range(n):
        k=j*10;u=0.;ci=.5*(y[k,1]+y[k+10,1]);cw=.5*(y[k,2]+y[k+10,2])
        for q in range(10):u+=y[k+q,0]
        for q in range(1,10):ci+=y[k+q,1];cw+=y[k+q,2]
        z[j,0]=u/10;z[j,1]=ci/10;z[j,2]=(y[k+10,1]-y[k,1])/.1;z[j,3]=cw/10
    count=max(0,(n-20)//2+1);out=np.empty((count,5));ix=0
    lo=np.array([1.6,.016,.048]);hi=np.array([3.6,.024,.052])
    flo=np.array([1.6,.016,.048,-.8]);fhi=np.array([3.6,.024,.052,.8])
    slo=np.array([1.6,1.6,.016,.048]);shi=np.array([3.6,3.6,.024,.052])
    for stop in range(20,n+1,2):
        target=z[stop-20:stop,0].copy();X=z[stop-20:stop,1:].copy()
        h,_,_=box_fit(X,target,lo,hi)
        F=np.ones((20,4));F[:,:3]=X
        f,theta,_=box_fit(F,target,flo,fhi)
        switch=h
        # At most one R change. Omit one possible straddling integration block.
        # Reusing this flexible explanation may conceal real faults; test that explicitly.
        for split in range(1,19):
            A=np.empty((19,4));b=np.empty(19);row=0
            for k in range(20):
                if k==split:continue
                A[row,0]=X[k,0] if k<split else 0.
                A[row,1]=X[k,0] if k>split else 0.
                A[row,2]=X[k,1];A[row,3]=X[k,2];b[row]=target[k];row+=1
            val,_,_=box_fit(A,b,slo,shi);switch=min(switch,val)
        out[ix,0]=stop*.1;out[ix,1]=h;out[ix,2]=switch;out[ix,3]=f;out[ix,4]=theta[-1];ix+=1
    return out


def diagnose(measured):
    y=np.asarray(measured,float)
    if y.ndim!=2 or y.shape[1]!=3 or len(y)<201 or not np.isfinite(y).all():
        raise ValueError('Need finite N>=201 by 3 [voltage,current,speed] readings')
    raw=electrical_kernel(np.ascontiguousarray(y))
    bank,_=v2.diagnose(y)
    score=np.zeros((len(raw),len(METHODS)))
    score[:,0]=bank[np.rint(raw[:,0]/.01).astype(int),2]
    score[:,1]=raw[:,1];score[:,2]=raw[:,2]
    feasible=raw[:,3]<=FIT_LIMIT
    score[:,3]=np.where(feasible,raw[:,1],0.)
    score[:,4]=np.where(feasible,raw[:,2],0.)
    return raw,score


def calibrate(out):
    out=Path(out)
    if (out/'calibration.json').exists():raise FileExistsError('Calibration already exists')
    hashes=source_hashes();rng=np.random.default_rng(774412);rows=[];tic=time.perf_counter()
    assignments=[('healthy_shift' if rng.random()<.5 else 'healthy') for _ in CAL_SEEDS]
    for mode in ('passive','active'):
        for seed,condition in zip(CAL_SEEDS,assignments):
            tr,_,_=simulate(seed,condition,mode=='active');raw,scores=diagnose(tr[:,[5,7,6]])
            rows.append(dict(mode=mode,seed=seed,condition=condition,maxima=scores.max(axis=0).tolist()))
    thresholds={}
    for mode in ('passive','active'):
        maxima=np.array([r['maxima'] for r in rows if r['mode']==mode])
        thresholds[mode]={m:mb.calibration_threshold(maxima[:,j]) for j,m in enumerate(METHODS)}
    doc=dict(source_hashes=hashes,n_seed_groups=159,n_trajectories=318,rank=152,
             thresholds=thresholds,rows=rows,elapsed_seconds=time.perf_counter()-tic)
    save_new(out/'calibration.json',doc)
    print('CALIBRATION',thresholds,doc['elapsed_seconds'],flush=True)


def evaluate(out,condition):
    out=Path(out);cal=json.loads((out/'calibration.json').read_text())
    assert source_hashes()==cal['source_hashes'],'Sources changed after calibration'
    if (out/f'{condition}.json').exists():raise FileExistsError('Do not overwrite evaluation')
    rows=[];scores_saved=[];features_saved=[];costs=[];states=[];tic=time.perf_counter()
    for mode in ('passive','active'):
        th=cal['thresholds'][mode]
        for seed in TEST_SEEDS:
            tr,onset,base=simulate(seed,condition,mode=='active');raw,scores=diagnose(tr[:,[5,7,6]])
            scores_saved.append(scores);features_saved.append(raw)
            cost=dict(mode=mode,seed=seed,condition=condition,
                      voltage_squared_integral=float(.01*np.sum(tr[:,5]**2)),
                      electrical_input_energy_j=float(.01*np.sum(tr[:,5]*tr[:,4])),
                      tracking_rmse_base=float(np.sqrt(np.mean((tr[:,3]-base)**2))),
                      tracking_rmse_command=float(np.sqrt(np.mean((tr[:,3]-tr[:,1])**2))),
                      saturation_fraction=float(np.mean(np.abs(tr[:,5])>=12)))
            # Exclude corrupted-voltage negatives from claims about actual actuation cost.
            cost['voltage_cost_is_actual']=condition!='healthy_voltage_bias';costs.append(cost)
            health_compatible=raw[:,2]<=th['electrical_switch']
            change_compatible=(raw[:,1]>th['electrical_single'])&health_compatible
            unresolved=(~health_compatible)&(raw[:,3]>FIT_LIMIT)
            states.append(dict(mode=mode,seed=seed,condition=condition,
                change_compatible_fraction=float(change_compatible.mean()),
                unresolved_fraction=float(unresolved.mean()),
                healthy_not_rejected_fraction=float(health_compatible.mean()),
                bias_fit_compatible_fraction=float((raw[:,3]<=FIT_LIMIT).mean())))
            for j,method in enumerate(METHODS):
                hit=np.flatnonzero(scores[:,j]>th[method]);alarm=None if not len(hit) else float(raw[hit[0],0])
                early=bool(onset is not None and alarm is not None and alarm<onset)
                detected=bool(onset is not None and alarm is not None and alarm>=onset)
                event=bool(alarm is not None) if onset is None else detected
                rows.append(dict(mode=mode,seed=seed,condition=condition,method=method,
                    threshold=th[method],onset=onset,alarm_time=alarm,event=event,
                    pre_fault_alarm=early,valid_detection=detected,
                    delay=None if not detected else alarm-onset))
    np.savez_compressed(out/f'{condition}_scores.npz',scores=np.array(scores_saved),raw=np.array(features_saved))
    doc=dict(condition=condition,seed_range=[21000,21099],rows=rows,costs=costs,states=states,
             source_hashes=source_hashes(),calibration_sha256=sha(out/'calibration.json'),
             elapsed_seconds=time.perf_counter()-tic)
    save_new(out/f'{condition}.json',doc)
    print('EVALUATED',condition,'seconds',doc['elapsed_seconds'],flush=True)


def summarize(out):
    out=Path(out);cal=json.loads((out/'calibration.json').read_text());rows=[];costs=[];states=[]
    for c in CONDITIONS:
        d=json.loads((out/f'{c}.json').read_text())
        assert d['source_hashes']==cal['source_hashes'] and d['calibration_sha256']==sha(out/'calibration.json')
        rows.extend(d['rows']);costs.extend(d['costs']);states.extend(d['states'])
    rates=[];paired=[];rng=np.random.default_rng(44992)
    for c in CONDITIONS:
        for mode in ('passive','active'):
            for m in METHODS:
                rr=sorted([r for r in rows if (r['condition'],r['mode'],r['method'])==(c,mode,m)],key=lambda r:r['seed'])
                assert [r['seed'] for r in rr]==list(TEST_SEEDS)
                n=len(rr);count=sum(r['event'] for r in rr);delays=[r['delay'] for r in rr if r['delay'] is not None]
                rates.append(dict(condition=c,mode=mode,method=m,n=n,count=count,rate=count/n,
                    wilson95=mb.wilson(count,n),pre_fault_alarms=sum(r['pre_fault_alarm'] for r in rr),
                    conditional_median_delay=None if not delays else float(np.median(delays))))
        a=np.array([r['event'] for r in sorted([r for r in rows if r['condition']==c and r['mode']=='active' and r['method']=='triage'],key=lambda r:r['seed'])],int)
        b=np.array([r['event'] for r in sorted([r for r in rows if r['condition']==c and r['mode']=='passive' and r['method']=='triage'],key=lambda r:r['seed'])],int)
        delta=a-b;boot=delta[rng.integers(0,len(delta),size=(10000,len(delta)))].mean(axis=1)
        paired.append(dict(condition=c,contrast='active triage minus passive triage',difference=float(delta.mean()),
                           percentile95=np.quantile(boot,[.025,.975]).tolist(),unadjusted_exploratory=True))
    lookup={(r['condition'],r['mode'],r['method']):r['rate'] for r in rates}
    targeted=all(lookup[c,'active','triage']<=.1 for c in ('healthy','healthy_shift','healthy_late_shift')) and all(lookup[c,'active','triage']>=.6 for c in ('bias','bias_shift','bias_late_shift'))
    legacy=targeted and lookup['stuck','active','triage']>=.9 and lookup['drift','active','triage']>=.6
    doc=dict(source_hashes=cal['source_hashes'],calibration_sha256=sha(out/'calibration.json'),
             targeted_screen_passed=targeted,extended_screen_passed=legacy,n_evaluation_trajectories=2800,
             independent_evaluation_seed_groups=100,results=rates,paired=paired,
             note='Same seeds paired across conditions/modes; not independent devices. Simulator and study authors unchanged.')
    save_new(out/'summary.json',doc)
    for name,data in (('episode_metrics.csv',rows),('rates.csv',rates),('paired.csv',paired),('control_costs.csv',costs),('diagnostic_states.csv',states)):
        with (out/name).open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    print('SCREENS',targeted,legacy)
    for c in CONDITIONS:
        print(c,{m:{mode:next(r['count'] for r in rates if (r['condition'],r['mode'],r['method'])==(c,mode,m)) for mode in ('passive','active')} for m in ('v2_bank','triage')})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=('calibrate','evaluate','summarize'))
    p.add_argument('--out',type=Path,default=Path('results'));p.add_argument('--condition',choices=CONDITIONS);args=p.parse_args()
    if args.phase=='calibrate':calibrate(args.out)
    elif args.phase=='evaluate':evaluate(args.out,args.condition)
    else:summarize(args.out)
