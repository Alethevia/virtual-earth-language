"""V9 independently commissioned AR prewhitening and matched step scans.
SIMULATION ONLY. Diagnostic readout faults never enter feedback. Profile-specific
healthy commissioning is additional prior information, not automatic online
regime recognition. No novelty, anytime or safety certification claim.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, math, sys, time
from pathlib import Path
import numpy as np
from scipy.linalg import toeplitz
from scipy.signal import lfilter
from numba import njit
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'motor_cusum_v8'))
import cusum_study as old
PROFILES=old.PROFILES
STRESS=old.STRESS
METHODS=('rms_matched','mean_2s','signed_scan','whiten_naive','whiten_matched','v8_cusum_frozen','always_abstain')
PRIMARY='whiten_matched'
WINDOWS=(.2,.5,1.,2.,5.,10.,30.)
PAIRS=((0,1),(0,2),(1,2))
TRAIN_RANGES=tuple(range(65000+100*j,65032+100*j) for j in range(4))
CAL_RANGES=tuple(range(67000+300*j,67199+300*j) for j in range(4))
TEST_SEEDS=range(70000,70200)
PARENT_HASH='82df678ef7ab82db02580c5b6c058d97f9c727f16f8830814a2bd2934402268a'
CUSUM_H=(170.26237709964514,9.994218256126453)
METRICS=('generic_false','wrong_any','first_correct','within_5s','within_30s','eventual_correct','pre_fault_unique','generic_alarm')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sources():
    d=old.sources()
    if d['cusum_study.py']!=PARENT_HASH:raise RuntimeError('Changed parent')
    return {**d,'whitening.py':sha(__file__)}
def save(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n')

def common(p):
    """Accept this study's synchronous common acquisitions, consume each once.
    Delayed/asynchronous general fusion is explicitly outside this study.
    """
    old.h.v5.validate(p)
    mask=(p.stamps[:,0]==p.stamps[:,1])&(p.stamps[:,0]==p.stamps[:,2])&(p.stamps[:,0]>=0)
    ids=np.flatnonzero(mask)
    if len(ids):ids=ids[np.r_[True,np.diff(p.stamps[ids,0])>0]]
    stamp=p.stamps[ids,0]
    if len(stamp)<3:raise ValueError('Insufficient simultaneous distinct acquisitions')
    step=np.diff(stamp)
    if not np.all(step==step[0]):raise ValueError('This model requires regular matched sampling')
    val=p.values[ids];d=np.column_stack([val[:,a]-val[:,b] for a,b in PAIRS])
    bounds=np.array([(p.quantum[a]+p.quantum[b])/2+p.offset_bound[a]+p.offset_bound[b] for a,b in PAIRS])
    var=np.array([p.sigma[a]**2+p.sigma[b]**2 for a,b in PAIRS])
    return stamp,d,bounds,var


def fit_ar(paths,order):
    """Pooled within-path centered covariance; no test observations or labels."""
    gamma=np.zeros((3,order+1));n=0
    for d in paths:
        x=d-d.mean(axis=0)
        for k in range(order+1):gamma[:,k]+=(x[k:]*x[:len(x)-k]).sum(axis=0)
        n+=len(x)
    gamma/=n
    phi=[];innovation=[];radius=[]
    for j in range(3):
        G=toeplitz(gamma[j,:order]);G+=np.eye(order)*gamma[j,0]*1e-6
        a=np.linalg.solve(G,gamma[j,1:])
        r=float(np.max(np.abs(np.roots(np.r_[1.,-a]))))
        if r>=1:raise RuntimeError('Unstable fitted AR; no silent posthoc repair')
        vv=float(gamma[j,0]-a@gamma[j,1:])
        if vv<=0:raise RuntimeError('Nonpositive innovation variance')
        phi.append(a.tolist());innovation.append(math.sqrt(vv));radius.append(r)
    return dict(order=order,phi=phi,innovation_sd=innovation,marginal_sd=np.sqrt(gamma[:,0]).tolist(),
                autocovariance=gamma.tolist(),spectral_radius=radius,training_samples=n)


def train(out):
    out=Path(out);models={};tic=time.perf_counter()
    for i,profile in enumerate(PROFILES):
        ds=[]
        for seed in TRAIN_RANGES[i]:
            y,sd=old.acquire(seed,profile,60.)
            p=old.make_packets(y,sd,profile,dict(mode='healthy',onset=None))
            stamps,d,_,_=common(p);ds.append(d)
        dt=float(np.diff(stamps)[0])*.01;order=20 if dt<.1 else 1
        m=fit_ar(ds,order);m['dt']=dt;m['training_seeds']=[TRAIN_RANGES[i].start,TRAIN_RANGES[i].stop-1]
        # Training residual diagnostic only: does NOT select order or modify model.
        diag=[]
        for j in range(3):
            x=np.concatenate([d[order:,j]-d[:,j].mean() for d in ds])
            es=[lfilter(np.r_[1.,-np.array(m['phi'][j])],[1.],d[:,j]-d[:,j].mean())[order:] for d in ds]
            # Do not cross independent path boundaries in covariance calculations.
            lag=sum(float(e[1:]@e[:-1]) for e in es)/sum(float(e@e) for e in es)
            diag.append(dict(raw_lag1=float(m['autocovariance'][j][1]/m['autocovariance'][j][0]),innovation_lag1=lag))
        m['training_diagnostic']=diag;models[profile]=m
    save(out/'training.json',dict(source_hashes=sources(),models=models,n_paths=128,duration_each=60.,elapsed=time.perf_counter()-tic))
    print('TRAINED', {p:m['training_diagnostic'][0] for p,m in models.items()},flush=True)


@njit(cache=True)
def cumsum_score(d,bounds):
    out=np.zeros_like(d);up=np.zeros(3);dn=np.zeros(3)
    for i in range(len(d)):
        for j in range(3):
            up[j]=max(0.,up[j]+d[i,j]-.25-bounds[j]);dn[j]=max(0.,dn[j]-d[i,j]-.25-bounds[j])
            out[i,j]=max(up[j],dn[j])
    return out


def filter_scores(stamps,d,bounds,var,model,received_length):
    """Data-dependent input = common measurement differences, NEVER fault truth.
    Fixed model is supplied by independent healthy commissioning. No model choice
    using the test profile, true rho, onset, sign, or channel label occurs here.
    """
    dt=model['dt'];step=int(round(dt/.01))
    if np.any(np.diff(stamps)!=step):raise ValueError('Commissioned acquisition rate mismatch')
    times=np.arange(200,received_length,20)*.01
    k=np.searchsorted(stamps,np.rint(times/.01).astype(int),side='right')-1
    n=len(d);score=np.zeros((len(times),6,3));valid=(k>=2)&((times-stamps[np.maximum(k,0)]*.01)<=.6+1e-12)
    weights_by_pair=[]
    for j in range(3):
        x=d[:,j];B=bounds[j];marg=model['marginal_sd'][j];sd=model['innovation_sd'][j]
        phi=np.asarray(model['phi'][j]);p=len(phi);e=lfilter(np.r_[1.,-phi],[1.],x)
        g=np.r_[1.,1.-np.cumsum(phi)];ginf=float(g[-1]);head=g[:p]-ginf
        cs=np.r_[0.,np.cumsum(x)];ce=np.r_[0.,np.cumsum(e)]
        # Same endpoint-inclusive two-second RMS convention as V8.
        starts=np.searchsorted(stamps,np.rint(times/.01).astype(int)-200,side='left')
        count=k-starts+1
        q=np.maximum(0.,np.abs(x)-B)**2/var[j];cq=np.r_[0.,np.cumsum(q)]
        score[:,0,j]=np.sqrt(np.maximum(0.,(cq[k+1]-cq[starts])/np.maximum(1,count)))
        score[:,1,j]=np.maximum(0.,np.abs((cs[k+1]-cs[starts])/np.maximum(1,count))-B)/marg
        # Static nuisance offset is also transformed by the filter. A fault step
        # produces a transient g, not merely a constant after prewhitening.
        hc=np.correlate(e,head,mode='valid') if p else np.zeros(n)
        for w in sorted(set(max(p,int(math.ceil(sec/dt))) for sec in WINDOWS)):
            keep=k>=w-1+p # all raw regressors for this proposed onset exist
            end=k[keep]+1;start=end-w
            raw=np.maximum(0.,np.abs(cs[end]-cs[start])-w*B)/(marg*math.sqrt(w))
            naive=np.maximum(0.,np.abs(ce[end]-ce[start])-w*B*abs(ginf))/(sd*math.sqrt(w))
            numerator=ginf*(ce[end]-ce[start])+hc[start]
            energy=float(g[:p]@g[:p]+(w-p)*ginf*ginf)
            nuisance=B*abs(ginf*(float(g[:p].sum())+(w-p)*ginf))
            matched=np.maximum(0.,np.abs(numerator)-nuisance)/(sd*math.sqrt(max(1e-20,energy)))
            score[keep,2,j]=np.maximum(score[keep,2,j],raw)
            score[keep,3,j]=np.maximum(score[keep,3,j],naive)
            score[keep,4,j]=np.maximum(score[keep,4,j],matched)
        weights_by_pair.append((e,g))
    score[:,5]=cumsum_score(d,bounds)[k]
    valid&=count>=3
    score[~valid]=0.
    return times,score,valid


def features(p,model):
    stamp,d,b,v=common(p)
    return filter_scores(stamp,d,b,v,model,len(p.values))


def labels(scores,valid,thresholds,dt):
    nt=len(scores);lab=np.full((7,nt),-1,np.int8);flags=np.zeros((7,nt),bool)
    for m in range(6):
        th=thresholds[m] if m<5 else CUSUM_H[0 if dt<.1 else 1]
        cross=(scores[:,m]>th)&valid[:,None]
        lab[m,cross[:,0]&cross[:,1]&~cross[:,2]]=0
        lab[m,cross[:,0]&cross[:,2]&~cross[:,1]]=1
        lab[m,cross[:,1]&cross[:,2]&~cross[:,0]]=2
        flags[m]=cross.any(axis=1)
    return lab,flags


def calibrate(out,profile):
    out=Path(out);tr=json.loads((out/'training.json').read_text());assert tr['source_hashes']==sources()
    model=tr['models'][profile];rows=[];tic=time.perf_counter()
    for seed in CAL_RANGES[PROFILES.index(profile)]:
        y,sd=old.acquire(seed,profile);p=old.make_packets(y,sd,profile,dict(mode='healthy',onset=None))
        _,score,v=features(p,model);assert v.all()
        rows.append(dict(seed=seed,maxima=score[:,:5].max(axis=(0,2)).tolist()))
    save(out/f'cal_{profile}.json',dict(source_hashes=sources(),training_sha256=sha(out/'training.json'),profile=profile,rows=rows,elapsed=time.perf_counter()-tic))
    print('CALIBRATED',profile,len(rows),round(time.perf_counter()-tic,2),flush=True)


def freeze(out):
    out=Path(out);thresholds={};rows=[]
    for profile in PROFILES:
        a=json.loads((out/f'cal_{profile}.json').read_text());assert a['source_hashes']==sources()
        assert a['training_sha256']==sha(out/'training.json')
        arr=np.array([r['maxima'] for r in a['rows']]);assert len(arr)==199
        thresholds[profile]=[old.h.mb.calibration_threshold(arr[:,j]) for j in range(5)]
        rows.append(a)
    save(out/'calibration.json',dict(source_hashes=sources(),training_sha256=sha(out/'training.json'),thresholds=thresholds,n=796,rank=190))
    print('FROZEN',thresholds,flush=True)


def cases(seed,profile):
    rng=np.random.default_rng(seed+14000001);sign=int(rng.choice((-1,1)));onset=float(rng.uniform(300,330))
    ret=[dict(mode='healthy',amplitude=0.,onset=None,target=None,sign=sign)]
    for amp in ((.25,.5,1.,6.) if profile in PROFILES else (.5,6.)):
        ret.append(dict(mode='primary_bias',amplitude=amp,onset=onset,target=0,sign=sign))
    if profile in PROFILES:
        for mode,target,amp in [('aux1_bias',1,.5),('aux2_bias',2,.5),('two_aux_common',None,6.),('all_common',None,6.)]:
            ret.append(dict(mode=mode,amplitude=amp,onset=onset,target=target,sign=sign))
    if profile in ('dense_iid','sparse_iid'):
        for mode in ('alternating_bias','two_second_pulse'):
            ret.append(dict(mode=mode,amplitude=.5,onset=onset,target=0,sign=sign))
    return ret


def evaluate(out,profile,start,stop):
    out=Path(out);tr=json.loads((out/'training.json').read_text());cal=json.loads((out/'calibration.json').read_text())
    assert cal['source_hashes']==tr['source_hashes']==sources();assert cal['training_sha256']==sha(out/'training.json')
    if not TEST_SEEDS.start<=start<stop<=TEST_SEEDS.stop:raise ValueError('Outside locked seeds')
    config=profile.replace('ar99','ar');model=tr['models'][config];th=cal['thresholds'][config]
    # Frozen matched commissioning in core; frozen .9 commissioning under .99 stress.
    # Model/threshold identity is known BEFORE monitoring; not inferred from fault labels.
    name=f'{profile}_{start}_{stop}';dest=out/(name+'.json')
    if dest.exists():raise FileExistsError(dest)
    records=[];meta=[];all_l=[];all_f=[];tic=time.perf_counter()
    for seed in range(start,stop):
        y,sd=old.acquire(seed,profile)
        for case in cases(seed,profile):
            packets=old.make_packets(y,sd,profile,case)
            times,scores,valid=features(packets,model);lab,flag=labels(scores,valid,th,model['dt'])
            cc=dict(seed=seed,profile=profile,**case);meta.append(cc);all_l.append(lab);all_f.append(flag)
            for horizon in ((18.,180.,600.) if case['mode']=='healthy' else (600.,)):
                for j,method in enumerate(METHODS):
                    rec=old.record(times,lab[j],flag[j],valid,case,horizon)
                    records.append(dict(**cc,horizon=horizon,method=method,**rec))
            if seed==TEST_SEEDS.start and case['mode'] in ('healthy','primary_bias') and case['amplitude'] in (0.,.5,6.):
                fn=out/f'example_{profile}_{case["mode"]}_{case["amplitude"]:g}.npz'
                np.savez_compressed(fn,values=packets.values,stamps=packets.stamps,sigma=packets.sigma,quantum=packets.quantum,
                    offset_bound=packets.offset_bound,times=times,scores=scores,valid=valid,labels=lab,flags=flag)
    np.savez_compressed(out/(name+'_decisions.npz'),labels=np.array(all_l),flags=np.array(all_f))
    save(dest,dict(source_hashes=sources(),training_sha256=sha(out/'training.json'),calibration_sha256=sha(out/'calibration.json'),
                  cases=meta,records=records,elapsed=time.perf_counter()-tic))
    print('EVALUATED',name,len(meta),'seconds',round(time.perf_counter()-tic,2),flush=True)


def summarize(out):
    out=Path(out);records=[];ncase=0
    for profile in PROFILES+STRESS:
        for p in sorted(out.glob(profile+'_*.json')):
            d=json.loads(p.read_text());assert d['source_hashes']==sources()
            assert d['training_sha256']==sha(out/'training.json') and d['calibration_sha256']==sha(out/'calibration.json')
            records+=d['records'];ncase+=len(d['cases'])
    keys=('profile','mode','amplitude','horizon','method');groups={}
    for r in records:groups.setdefault(tuple(r[k] for k in keys),[]).append(r)
    rates=[]
    for key,rr in sorted(groups.items()):
        rr.sort(key=lambda x:x['seed']);assert [r['seed'] for r in rr]==list(TEST_SEEDS),(key,len(rr))
        row=dict(zip(keys,key));row['n']=len(rr)
        for metric in METRICS:
            count=sum(r[metric] for r in rr);row[metric+'_count']=count;row[metric+'_rate']=count/len(rr);row[metric+'_wilson95']=old.h.mb.wilson(count,len(rr))
        delays=[r['delay'] for r in rr if r['first_correct']]
        row['conditional_median_delay']=float(np.median(delays)) if delays else None
        row['mean_restricted_delay_30s']=float(np.mean([r['restricted_delay_30s'] for r in rr]));row['coverage']=float(np.mean([r['coverage'] for r in rr]))
        rates.append(row)
    rng=np.random.default_rng(45009);paired=[]
    for key in sorted(set(k[:-1] for k in groups)):
        ix=rng.integers(0,len(TEST_SEEDS),size=(3000,len(TEST_SEEDS)))
        aa=groups[key+(PRIMARY,)]
        for cmp in ('rms_matched','mean_2s','signed_scan','whiten_naive','v8_cusum_frozen'):
            bb=groups[key+(cmp,)]
            for metric in ('generic_false','wrong_any','within_5s','first_correct'):
                delta=np.array([a[metric] for a in aa],int)-np.array([b[metric] for b in bb],int)
                paired.append(dict(zip(keys[:-1],key))|dict(contrast=PRIMARY+' - '+cmp,metric=metric,difference=float(delta.mean()),
                    percentile95=np.quantile(delta[ix].mean(axis=1),[.025,.975]).tolist()))
    look={tuple(r[k] for k in keys):r for r in rates};checks={}
    for profile in PROFILES:
        healthy=look[(profile,'healthy',0.,600.,PRIMARY)]
        small=look[(profile,'primary_bias',.5,600.,PRIMARY)];large=look[(profile,'primary_bias',6.,600.,PRIMARY)]
        checks[profile+'_false_generic']=healthy['generic_false_rate']<=.1
        checks[profile+'_wrong_any']=healthy['wrong_any_rate']<=.05
        checks[profile+'_half_unit_5s']=small['within_5s_rate']>=.8
        checks[profile+'_six_unit_5s']=large['within_5s_rate']>=.9
        checks[profile+'_availability']=healthy['coverage']>=.95
    save(out/'summary.json',dict(source_hashes=sources(),training_sha256=sha(out/'training.json'),calibration_sha256=sha(out/'calibration.json'),
        n_training=128,n_calibration=796,n_cases=ncase,independent_test_seeds=200,records=len(records),cells=len(rates),criteria=checks,
        screen_passed=all(checks.values()),results=rates,paired=paired))
    for name,data in [('episode_metrics.csv',records),('rates.csv',rates),('paired.csv',paired)]:
        with (out/name).open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    print('SCREEN',sum(checks.values()),len(checks),all(checks.values()),flush=True)
    for profile in PROFILES+STRESS:
        for mode,amp in [('healthy',0.),('primary_bias',.5),('primary_bias',6.)]:
            print(profile,mode,amp,{m:((look[(profile,mode,amp,600.,m)]['generic_false_count'],look[(profile,mode,amp,600.,m)]['wrong_any_count']) if mode=='healthy' else (look[(profile,mode,amp,600.,m)]['within_5s_count'],look[(profile,mode,amp,600.,m)]['first_correct_count'])) for m in METHODS[:-1]},flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=('train','calibrate','freeze','evaluate','summarize'))
    p.add_argument('--out',type=Path,default=Path('results/local'));p.add_argument('--profile',choices=PROFILES+STRESS)
    p.add_argument('--start',type=int,default=70000);p.add_argument('--stop',type=int,default=70200);a=p.parse_args()
    if a.phase=='train':train(a.out)
    elif a.phase=='calibrate':calibrate(a.out,a.profile)
    elif a.phase=='freeze':freeze(a.out)
    elif a.phase=='evaluate':evaluate(a.out,a.profile,a.start,a.stop)
    else:summarize(a.out)
