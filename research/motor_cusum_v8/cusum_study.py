"""V8 signed evidence accumulation; downstream readout simulation, not safety control.
Fixed traditional CUSUM; fresh whole-path calibration, strong signed-mean baseline.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, math, sys, time
from pathlib import Path
import numpy as np
from numba import njit
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'motor_horizon_v7'))
import horizon as h
PROFILES=h.PROFILES
STRESS=('dense_ar99','sparse_ar99')
CAL_RANGES=tuple(range(57000+300*j,57199+300*j) for j in range(4))
TEST_SEEDS=range(61000,61200)
METHODS=('v7_rms_frozen','rms_universal','rms_rate','mean_rate','cusum_universal','cusum_rate','always_abstain')
STREAMS=('rms','mean','cusum')
SLACK=.25
FROZEN_RMS=2.4746751835866267
PARENT_SHA='3e026b467693184d2b26a256e0f00a643ba5c9242eeb64678ae00bcaaa0ebdb1'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def sources():
    d=h.sources()
    if d['horizon.py']!=PARENT_SHA:raise RuntimeError('Parent source differs')
    return {**d,'cusum_study.py':sha(__file__)}
def save(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n')


@njit(cache=True)
def score_kernel(values,stamps,sigma,quantum,offsets):
    n=len(values);nt=(n-201)//20+1
    score=np.zeros((nt,3,3));valid=np.zeros(nt,np.bool_);counts=np.zeros(nt,np.int64)
    cache=np.zeros((n,3));seen=np.zeros((n,3),np.bool_)
    kt=np.empty(n,np.int64);dd=np.empty((n,3));qq=np.empty((n,3))
    sums=np.zeros(3);squares=np.zeros(3);up=np.zeros(3);down=np.zeros(3)
    pairs=((0,1),(0,2),(1,2));head=0;tail=0;last=-1;row=0
    bounds=np.empty(3);variances=np.empty(3)
    for j in range(3):
        a,b=pairs[j];bounds[j]=(quantum[a]+quantum[b])/2+offsets[a]+offsets[b]
        variances[j]=sigma[a]**2+sigma[b]**2
    for t in range(n):
        for c in range(3):
            k=stamps[t,c]
            if k>=0:cache[k,c]=values[t,c];seen[k,c]=True
        for k in range(last+1,t+1):
            if seen[k,0] and seen[k,1] and seen[k,2]:
                kt[tail]=k
                for j in range(3):
                    a,b=pairs[j];d=cache[k,a]-cache[k,b]
                    q=max(0.,abs(d)-bounds[j])**2/variances[j]
                    dd[tail,j]=d;qq[tail,j]=q;sums[j]+=d;squares[j]+=q
                    up[j]=max(0.,up[j]+d-SLACK-bounds[j])
                    down[j]=max(0.,down[j]-d-SLACK-bounds[j])
                tail+=1;last=k
        while head<tail and kt[head]<t-200:
            for j in range(3):sums[j]-=dd[head,j];squares[j]-=qq[head,j]
            head+=1
        if t<200 or (t-200)%20:continue
        count=tail-head;counts[row]=count
        if count>=3 and t-last<=60:
            valid[row]=True
            for j in range(3):
                score[row,0,j]=math.sqrt(max(0.,squares[j]/count))
                score[row,1,j]=max(0.,abs(sums[j]/count)-bounds[j])
                score[row,2,j]=max(up[j],down[j])
        row+=1
    return score,valid,counts


def features(p):
    h.v5.validate(p)
    return score_kernel(np.asarray(p.values,float),p.stamps,np.asarray(p.sigma,float),np.asarray(p.quantum,float),np.asarray(p.offset_bound,float))


def acquire(seed,profile,duration=600.):
    if profile in PROFILES:return h.acquired(seed,profile,duration)
    if profile not in STRESS:raise ValueError(profile)
    # Same truthful marginal SD, stronger unseen temporal dependence.
    y,sd=h.acquired(seed,profile.replace('ar99','iid'),duration)
    z=np.random.default_rng(seed+12000000).normal(size=len(y))
    y[:,0]+=math.sqrt(.75**2-.25**2)*h.ar_series(z,.99);sd[0]=.75
    return y,sd


def scenarios(seed,profile):
    rng=np.random.default_rng(seed+12000001)
    sign=int(rng.choice([-1,1]));onset=float(rng.uniform(300,330))
    cases=[dict(mode='healthy',amplitude=0.,onset=None,target=None,sign=sign)]
    amps=h.AMPLITUDES if profile in PROFILES else (.5,6.)
    for a in amps:cases.append(dict(mode='primary_bias',amplitude=a,onset=onset,target=0,sign=sign))
    if profile in PROFILES:
        for mode,target in (('aux1_bias',1),('aux2_bias',2),('two_aux_common',None),('all_common',None)):
            cases.append(dict(mode=mode,amplitude=6.,onset=onset,target=target,sign=sign))
    if profile in ('dense_iid','sparse_iid'):
        for mode in ('alternating_bias','two_second_pulse'):
            cases.append(dict(mode=mode,amplitude=.5,onset=onset,target=0,sign=sign))
    return cases


def make_packets(y,sd,profile,case):
    # Faults affect diagnostic observations ONLY, never plant/controller.
    p=h.packets(y,sd,profile)
    val=p.values.copy();mode=case['mode'];onset=case['onset']
    if onset is not None:
        channels=(0,1,2) if mode=='all_common' else ((1,2) if mode=='two_aux_common' else (case['target'],))
        for c in channels:
            tm=p.stamps[:,c]*.01;active=tm>=onset
            shift=case['sign']*case['amplitude']*active.astype(float)
            if mode=='alternating_bias':shift*=np.where((np.floor(np.maximum(0.,tm-onset)/.5).astype(int)%2)==0,1.,-1.)
            if mode=='two_second_pulse':shift*=tm<onset+2.
            val[:,c]+=shift
    return h.v5.Packets(val,p.stamps,p.sigma,p.quantum,p.offset_bound)


def decide(f,cal):
    s,valid,count=f;group=np.where(count>=26,0,1) # 0=dense; 1=sparse. No true profile input.
    nt=len(s);labels=np.full((len(METHODS),nt),-1,np.int8);flags=np.zeros_like(labels,dtype=bool)
    spec=[(0,FROZEN_RMS),(0,cal['universal']['rms']),(0,np.array(cal['rate']['rms'])[group]),
          (1,np.array(cal['rate']['mean'])[group]),(2,cal['universal']['cusum']),(2,np.array(cal['rate']['cusum'])[group])]
    for j,(stream,th) in enumerate(spec):
        th=np.full(nt,th) if np.isscalar(th) else th
        cross=(s[:,stream,:]>th[:,None])&valid[:,None]
        labels[j,cross[:,0]&cross[:,1]&~cross[:,2]]=0
        labels[j,cross[:,0]&cross[:,2]&~cross[:,1]]=1
        labels[j,cross[:,1]&cross[:,2]&~cross[:,0]]=2
        flags[j]=cross.any(axis=1)
    return labels,flags,valid


def record(times,labels,flags,valid,case,end):
    keep=times<end;tt=times[keep];ll=labels[keep];ff=flags[keep];vv=valid[keep]
    onset=case['onset'];target=case['target'];fault=onset is not None
    ix=np.flatnonzero(ll>=0);first=None if not len(ix) else float(tt[ix[0]]);channel=None if not len(ix) else int(ll[ix[0]])
    af=np.flatnonzero(ff);first_alarm=None if not len(af) else float(tt[af[0]])
    fault_end=onset+2. if case['mode']=='two_second_pulse' else math.inf
    correct=bool(fault and target is not None and first is not None and onset<=first<fault_end and channel==target)
    wrong=(ll>=0) if not fault or target is None else ((ll>=0)&((tt<onset)|(tt>=fault_end)|(ll!=target)))
    early=ff if not fault else ff&(tt<onset)
    delay=first-onset if correct else None
    return dict(generic_alarm=bool(ff.any()),generic_false=bool(early.any()),wrong_any=bool(wrong.any()),
        first_unique=first,first_label=channel,first_generic=first_alarm,first_correct=correct,
        delay=delay,within_5s=bool(correct and delay<=5),within_30s=bool(correct and delay<=30),
        eventual_correct=bool(fault and target is not None and ((ll==target)&(tt>=onset)&(tt<fault_end)).any()),
        first_generic_valid=bool(fault and first_alarm is not None and first_alarm>=onset),
        pre_fault_unique=bool(fault and ((ll>=0)&(tt<onset)).any()),coverage=float(vv.mean()),
        restricted_delay_30s=min(30.,delay) if correct else 30.,
        unresolved_fraction=float(np.mean(ff&(ll<0))))


def calibrate(out,profile):
    out=Path(out);dest=out/f'cal_{profile}.json'
    if dest.exists():raise FileExistsError(dest)
    i=PROFILES.index(profile);rows=[];tic=time.perf_counter()
    for seed in CAL_RANGES[i]:
        y,sd=acquire(seed,profile);case=dict(mode='healthy',onset=None)
        s,v,count=features(make_packets(y,sd,profile,case))
        assert v.all() and ((count>=26).all() if profile.startswith('dense') else (count<26).all())
        rows.append(dict(seed=seed,profile=profile,maxima=s.max(axis=(0,2)).tolist()))
    save(dest,dict(source_hashes=sources(),rows=rows,elapsed=time.perf_counter()-tic))
    print('CALIBRATED',profile,len(rows),round(time.perf_counter()-tic,2),flush=True)


def freeze(out):
    out=Path(out);rows=[]
    for p in PROFILES:
        d=json.loads((out/f'cal_{p}.json').read_text());assert d['source_hashes']==sources();rows+=d['rows']
    by={p:{m:h.mb.calibration_threshold(np.array([r['maxima'] for r in rows if r['profile']==p])[:,j]) for j,m in enumerate(STREAMS)} for p in PROFILES}
    rate={m:[max(by[p][m] for p in PROFILES if p.startswith(g)) for g in ('dense','sparse')] for m in STREAMS}
    universal={m:max(rate[m]) for m in STREAMS}
    save(out/'calibration.json',dict(source_hashes=sources(),n=796,n_per_profile=199,rank=190,
         groups=by,rate=rate,universal=universal,rows=rows))
    print('FROZEN',rate,universal,flush=True)


def evaluate(out,profile,start,stop):
    out=Path(out);cal=json.loads((out/'calibration.json').read_text());assert cal['source_hashes']==sources()
    if not TEST_SEEDS.start<=start<stop<=TEST_SEEDS.stop:raise ValueError('Outside frozen test seed range')
    name=f'{profile}_{start}_{stop}'
    if (out/(name+'.json')).exists():raise FileExistsError(name)
    rows=[];cases=[];saved_l=[];saved_f=[];tic=time.perf_counter()
    for seed in range(start,stop):
        y,sd=acquire(seed,profile);times=np.arange(200,len(y),20)*.01
        for case in scenarios(seed,profile):
            p=make_packets(y,sd,profile,case);f=features(p);lab,flag,val=decide(f,cal)
            cc=dict(seed=seed,profile=profile,**case);cases.append(cc);saved_l.append(lab);saved_f.append(flag)
            for horizon in ((18.,180.,600.) if case['mode']=='healthy' else (600.,)):
                for j,m in enumerate(METHODS):
                    rows.append(dict(**cc,horizon=horizon,method=m,**record(times,lab[j],flag[j],val,case,horizon)))
            if seed==TEST_SEEDS.start and ((case['mode']=='healthy') or (case['mode']=='primary_bias' and case['amplitude'] in (.5,6.))):
                np.savez_compressed(out/f"example_{profile}_{case['mode']}_{case['amplitude']:g}.npz",
                    values=p.values,stamps=p.stamps,sigma=p.sigma,quantum=p.quantum,offset_bound=p.offset_bound,
                    scores=f[0],valid=f[1],counts=f[2],times=times,labels=lab,flags=flag)
    np.savez_compressed(out/(name+'_decisions.npz'),labels=np.array(saved_l),flags=np.array(saved_f))
    save(out/(name+'.json'),dict(source_hashes=sources(),calibration_sha256=sha(out/'calibration.json'),
        cases=cases,records=rows,elapsed=time.perf_counter()-tic))
    print('EVALUATED',name,len(cases),round(time.perf_counter()-tic,2),flush=True)


METRICS=('generic_alarm','generic_false','wrong_any','first_correct','within_5s','within_30s','eventual_correct','first_generic_valid','pre_fault_unique')
KEYS=('profile','mode','amplitude','horizon','method')

def summarize(out):
    out=Path(out);cal=json.loads((out/'calibration.json').read_text());records=[];ncase=0
    for p in PROFILES+STRESS:
        for fn in sorted(out.glob(p+'_*.json')):
            d=json.loads(fn.read_text());assert d['source_hashes']==sources();assert d['calibration_sha256']==sha(out/'calibration.json')
            records+=d['records'];ncase+=len(d['cases'])
    groups={}
    for r in records:groups.setdefault(tuple(r[k] for k in KEYS),[]).append(r)
    rates=[]
    for key,rr in sorted(groups.items()):
        rr.sort(key=lambda r:r['seed']);assert [r['seed'] for r in rr]==list(TEST_SEEDS)
        d=dict(zip(KEYS,key));d['n']=len(rr)
        for m in METRICS:
            n=sum(r[m] for r in rr);d[m+'_count']=n;d[m+'_rate']=n/len(rr);d[m+'_wilson95']=h.mb.wilson(n,len(rr))
        delays=[r['delay'] for r in rr if r['first_correct']]
        d['conditional_median_delay']=float(np.median(delays)) if delays else None
        d['mean_restricted_delay_30s']=float(np.mean([r['restricted_delay_30s'] for r in rr]))
        d['coverage']=float(np.mean([r['coverage'] for r in rr]));rates.append(d)
    rng=np.random.default_rng(45008);paired=[]
    for key in sorted(set(k[:-1] for k in groups)):
        ix=rng.integers(0,200,size=(5000,200));a=groups[key+('cusum_rate',)]
        for cmp in ('v7_rms_frozen','rms_rate','mean_rate','cusum_universal'):
            b=groups[key+(cmp,)]
            for metric in ('generic_false','wrong_any','within_5s','first_correct'):
                delta=np.array([r[metric] for r in a],int)-np.array([r[metric] for r in b],int)
                paired.append(dict(zip(KEYS[:-1],key))|dict(contrast='cusum_rate - '+cmp,metric=metric,
                    difference=float(delta.mean()),percentile95=np.quantile(delta[ix].mean(axis=1),[.025,.975]).tolist()))
    look={tuple(r[k] for k in KEYS):r for r in rates};criteria={}
    for p in PROFILES:
        a=look[p,'healthy',0.,600.,'cusum_rate'];b=look[p,'primary_bias',.5,600.,'cusum_rate'];c=look[p,'primary_bias',6.,600.,'cusum_rate']
        criteria[p+'_healthy_generic']=a['generic_false_rate']<=.10
        criteria[p+'_healthy_wrong_any']=a['wrong_any_rate']<=.05
        criteria[p+'_half_unit_within5']=b['within_5s_rate']>=.80
        criteria[p+'_six_unit_within5']=c['within_5s_rate']>=.90
        criteria[p+'_availability']=a['coverage']>=.95
    doc=dict(source_hashes=sources(),calibration_sha256=sha(out/'calibration.json'),n_cases=ncase,
        records=len(records),cells=len(rates),independent_test_seed_groups=200,criteria=criteria,
        screen_passed=all(criteria.values()),results=rates,paired=paired)
    save(out/'summary.json',doc)
    for name,data in (('episode_metrics.csv',records),('rates.csv',rates),('paired.csv',paired)):
        with (out/name).open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    print('SUMMARY',ncase,len(records),len(rates),sum(criteria.values()),len(criteria),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=('calibrate','freeze','evaluate','summarize'))
    p.add_argument('--out',type=Path,default=Path('results'));p.add_argument('--profile',choices=PROFILES+STRESS)
    p.add_argument('--start',type=int,default=61000);p.add_argument('--stop',type=int,default=61200);a=p.parse_args()
    if a.phase=='calibrate':calibrate(a.out,a.profile)
    elif a.phase=='freeze':freeze(a.out)
    elif a.phase=='evaluate':evaluate(a.out,a.profile,a.start,a.stop)
    else:summarize(a.out)
