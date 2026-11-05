"""V7 small-bias/monitoring-horizon audit. Simulation, not deployment.
Original V5 pairwise quality score; extended monitoring and readout-only faults.
No controller sees these downstream faults. See PROTOCOL.md for inference scope.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, math, sys, time
from pathlib import Path
from functools import lru_cache
import numpy as np
from numba import njit
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'motor_calibration_v6'))
import calibration_study as v6
v5=v6.v5; mb=v5.v4.v3.mb
PROFILES=('dense_iid','sparse_iid','dense_ar','sparse_ar')
AMPLITUDES=(.125,.25,.5,1.,2.,6.)
METHODS=('v6_count','v6_universal','new_short_universal','new_long_universal','always_abstain')
CAL_RANGES=tuple(range(47000+300*j,47199+300*j) for j in range(4))
TEST_SEEDS=range(50000,50200)
DURATION=600.; DT=.01
V6_THRESHOLDS=(2.0307216952958402,1.6532623640481576,1.275003768049613)
EXPECTED_PARENT='4934e3d5e531579cc6881198880c691e2dd7eeb2365b7dc1b6da1830aa385e37'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def sources():
    parent=v6.sources()
    if parent['calibration_study.py']!=EXPECTED_PARENT:raise RuntimeError('Parent changed')
    return {**parent,'horizon.py':sha(__file__)}
def save(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n')


@njit(cache=True)
def plant_loop(A,B,refs,loads):
    n=len(refs);out=np.empty((n,3));current=0.;speed=0.;integral=0.
    for k in range(n):
        error=refs[k]-speed;raw=.2*error+integral;u=min(12.,max(-12.,raw))
        if raw==u or error*(raw-u)<=0:integral+=.6*.01*error
        out[k,0]=speed;out[k,1]=current;out[k,2]=u
        ni=A[0,0]*current+A[0,1]*speed+B[0,0]*u+B[0,1]*loads[k]
        nw=A[1,0]*current+A[1,1]*speed+B[1,0]*u+B[1,1]*loads[k]
        current=ni;speed=nw
    return out


@lru_cache(maxsize=1)
def nominal_dynamics():return mb.discretize(*mb.Motor().continuous())

def background(seed,n):
    """Healthy nominal PI motor; exact speed feedback. Telemetry is downstream.
    Random piecewise references/loads; no resets along a 600-second trajectory.
    This extends the benchmark, not a claim of old simulator parity.
    """
    r=np.random.default_rng(seed+9000000)
    # Separate streams make requested prefix length irrelevant to the other input.
    ref=r.uniform(25,110,(n+499)//500)
    load=np.random.default_rng(seed+9000001).uniform(.005,.035,(n+299)//300)
    return plant_loop(*nominal_dynamics(),np.repeat(ref,500)[:n],np.repeat(load,300)[:n])


@njit(cache=True)
def ar_series(z,rho):
    out=np.empty(len(z));out[0]=z[0];factor=math.sqrt(1-rho*rho)
    for k in range(1,len(z)):out[k]=rho*out[k-1]+factor*z[k]
    return out


def acquired(seed,profile,duration=DURATION):
    if profile not in PROFILES:raise ValueError('Unknown profile')
    if not np.isfinite(duration) or duration<2.01:raise ValueError('Duration too short')
    n=round(duration/DT)
    noise=np.random.default_rng(seed+10000000).normal(0,.25,size=(n,3))
    offsets=np.r_[0.,np.random.default_rng(seed+10000001).uniform(-.03,.03,2)]
    sigma=np.full(3,.25)
    if profile.endswith('_ar'):
        z=np.random.default_rng(seed+10000002).normal(size=n)
        noise[:,0]+=math.sqrt(.75**2-.25**2)*ar_series(z,.9);sigma[0]=.75
    y=background(seed,n)[:,0,None]+noise+offsets
    return y,sigma


def packets(y,sigma,profile,amplitude=0.,onset=0.,sign=1):
    if not np.isfinite(amplitude) or amplitude<0 or sign not in (-1,1):raise ValueError('Invalid bias')
    if not np.isfinite(onset) or onset<0:raise ValueError('Invalid onset')
    n=len(y);ticks=np.arange(n);stamps=np.tile(ticks[:,None],(1,3))
    if profile.startswith('sparse'):stamps[:,0]=(ticks//50)*50
    vals=np.column_stack([y[stamps[:,c],c] for c in range(3)])
    # Inject into the acquisition, not repeatedly into held packets. Controller unchanged.
    vals[:,0]+=sign*amplitude*(stamps[:,0]*DT>=onset)
    return v5.Packets(vals,stamps,np.asarray(sigma).copy(),np.zeros(3),np.array([0.,.03,.03]))


def raw_features(p):
    # Source-preserving reference; validation includes duplicate-packet consistency.
    return v5.features(p)


def decisions(f,thresholds):
    scores,available,counts,ages=f
    quality=scores[:,3];valid=available[:,3];g=v6.group_ids(counts)
    ths=(np.array(V6_THRESHOLDS)[np.maximum(g,0)],np.full(len(g),V6_THRESHOLDS[0]),
         np.full(len(g),thresholds['short']),np.full(len(g),thresholds['long']))
    labels=np.full((len(METHODS),len(g)),-1,dtype=np.int8);flags=np.zeros(labels.shape,bool)
    for j,th in enumerate(ths):
        cross=(quality>th[:,None])&valid[:,None]
        labels[j,cross[:,0]&cross[:,1]&~cross[:,2]]=0
        labels[j,cross[:,0]&cross[:,2]&~cross[:,1]]=1
        labels[j,cross[:,1]&cross[:,2]&~cross[:,0]]=2
        flags[j]=cross.any(axis=1)
    return labels,flags,valid


def record(times,label,flag,valid,onset,end):
    keep=times<end;tt=times[keep];ll=label[keep];ff=flag[keep];vv=valid[keep]
    where=np.flatnonzero(ll>=0);first=None if len(where)==0 else float(tt[where[0]])
    first_label=None if len(where)==0 else int(ll[where[0]])
    af=np.flatnonzero(ff);alarm=None if len(af)==0 else float(tt[af[0]])
    fault=onset is not None
    correct=bool(fault and first is not None and first>=onset and first_label==0)
    wrong=(ll>=0) if not fault else ((ll>=0)&((tt<onset)|(ll!=0)))
    early=ff if not fault else (ff&(tt<onset))
    delay=first-onset if correct else None
    post=(tt>=onset) if fault else np.zeros(len(tt),bool)
    # Non-overlapping 18-second epochs diagnostic only: detectors are NEVER reset.
    epochs=np.floor((tt-2)/18).astype(int)
    bad_epochs=sum(bool(ff[epochs==k].any()) for k in np.unique(epochs))
    return dict(generic_alarm=bool(ff.any()),generic_false=bool(early.any()),wrong_any=bool(wrong.any()),
        first_unique=first,first_label=first_label,first_generic=alarm,first_correct=correct,
        first_correct_delay=delay,within_5s=bool(correct and delay<=5),within_30s=bool(correct and delay<=30),
        eventual_correct=bool(fault and ((ll==0)&post).any()),coverage=float(vv.mean()),
        post_fault_coverage=float(vv[post].mean()) if fault and post.any() else None,
        pre_fault_unique=bool(fault and ((ll>=0)&(tt<onset)).any()),
        unresolved_fraction=float(np.mean(ff&(ll<0))),flagged_decisions=int(ff.sum()),
        alarm_bursts=int(np.sum(ff&~np.r_[False,ff[:-1]])),flagged_epoch_count=int(bad_epochs),
        epochs_observed=int(len(np.unique(epochs))),restricted_delay_30s=min(30.,delay) if correct else 30.)


def calibrate(out,profile):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    dest=out/f'cal_{profile}.json'
    if dest.exists():raise FileExistsError(dest)
    j=PROFILES.index(profile);rows=[];tic=time.perf_counter()
    for seed in CAL_RANGES[j]:
        y,sd=acquired(seed,profile);p=packets(y,sd,profile);s,a,n,age=raw_features(p)
        assert a[:,3].all()
        times=np.arange(200,len(y),20)*DT
        rows.append(dict(seed=seed,profile=profile,short=float(s[times<18,3].max()),long=float(s[:,3].max())))
    save(dest,dict(source_hashes=sources(),rows=rows,elapsed=time.perf_counter()-tic))
    print('CALIBRATED_PROFILE',profile,len(rows),round(time.perf_counter()-tic,2),flush=True)


def freeze(out):
    out=Path(out);rows=[]
    for p in PROFILES:
        d=json.loads((out/f'cal_{p}.json').read_text());assert d['source_hashes']==sources();rows+=d['rows']
    groups={p:{h:v6.rank_threshold([r[h] for r in rows if r['profile']==p]) for h in ('short','long')} for p in PROFILES}
    thresholds={h:max(g[h] for g in groups.values()) for h in ('short','long')}
    save(out/'calibration.json',dict(source_hashes=sources(),n=796,n_per_profile=199,rank=190,
        thresholds=thresholds,groups=groups,rows=rows,scope='Two finite horizons on same calibration paths; no anytime guarantee.'))
    print('FROZEN',thresholds,groups,flush=True)


def evaluate(out,profile,start,stop):
    out=Path(out);cal=json.loads((out/'calibration.json').read_text())
    assert sources()==cal['source_hashes']
    if not TEST_SEEDS.start<=start<stop<=TEST_SEEDS.stop:raise ValueError('Outside locked seeds')
    name=f'{profile}_{start}_{stop}'
    if (out/(name+'.json')).exists():raise FileExistsError(name)
    records=[];saved_labels=[];saved_flags=[];cases=[];tic=time.perf_counter()
    for seed in range(start,stop):
        y,sd=acquired(seed,profile)
        rnd=np.random.default_rng(seed+10000003);sign=int(rnd.choice([-1,1]));late=float(rnd.uniform(300,330))
        specs=[('healthy',0.,None,600.)]+[(mode,amp,10. if mode=='short_fault' else late,18. if mode=='short_fault' else 600.) for mode in ('short_fault','late_fault') for amp in AMPLITUDES]
        for mode,amp,onset,end in specs:
            sub=y[:round(end/DT)];p=packets(sub,sd,profile,amp,0. if onset is None else onset,sign)
            f=raw_features(p);labels,flags,valid=decisions(f,cal['thresholds']);times=np.arange(200,len(sub),20)*DT
            # Store all decisions compactly; full double-precision representative scores separately.
            padded=np.full((len(METHODS),2990),-2,np.int8);pflag=np.zeros((len(METHODS),2990),bool)
            padded[:,:len(times)]=labels;pflag[:,:len(times)]=flags
            saved_labels.append(padded);saved_flags.append(pflag)
            case=dict(seed=seed,profile=profile,mode=mode,amplitude=amp,sign=sign,onset=onset,end=end)
            cases.append(case)
            for h in ((18.,180.,600.) if mode=='healthy' else (end,)):
                for j,m in enumerate(METHODS):
                    records.append(dict(**case,horizon=h,method=m,**record(times,labels[j],flags[j],valid,onset,h)))
            if seed==TEST_SEEDS.start and ((mode=='healthy') or (amp in (.5,6.) and mode=='late_fault')):
                ex=out/f'example_{profile}_{mode}_{amp:g}.npz'
                np.savez_compressed(ex,values=p.values,stamps=p.stamps,sigma=p.sigma,offset_bound=p.offset_bound,
                    scores=f[0],available=f[1],counts=f[2],ages=f[3],labels=labels,flags=flags,times=times)
    np.savez_compressed(out/(name+'_decisions.npz'),labels=np.array(saved_labels),flags=np.array(saved_flags))
    save(out/(name+'.json'),dict(source_hashes=sources(),calibration_sha256=sha(out/'calibration.json'),
        cases=cases,records=records,elapsed=time.perf_counter()-tic))
    print('EVALUATED',name,'cases',len(cases),'seconds',round(time.perf_counter()-tic,2),flush=True)


def summarize(out):
    out=Path(out);cal=json.loads((out/'calibration.json').read_text());records=[]
    for p in PROFILES:
        for f in sorted(out.glob(p+'_*.json')):
            d=json.loads(f.read_text());assert d['source_hashes']==sources();assert d['calibration_sha256']==sha(out/'calibration.json');records+=d['records']
    groups={}
    for r in records:
        key=tuple(r[k] for k in ('profile','mode','amplitude','horizon','method'));groups.setdefault(key,[]).append(r)
    rates=[];metrics=('generic_alarm','generic_false','wrong_any','first_correct','within_5s','within_30s','eventual_correct','pre_fault_unique')
    for key,rr in sorted(groups.items()):
        rr.sort(key=lambda r:r['seed']);assert [r['seed'] for r in rr]==list(TEST_SEEDS),(key,len(rr))
        d=dict(zip(('profile','mode','amplitude','horizon','method'),key));d['n']=len(rr)
        for m in metrics:
            count=sum(r[m] for r in rr);d[m+'_count']=count;d[m+'_rate']=count/len(rr);d[m+'_wilson95']=mb.wilson(count,len(rr))
        delays=[r['first_correct_delay'] for r in rr if r['first_correct']]
        d.update(conditional_median_delay=float(np.median(delays)) if delays else None,
            mean_restricted_delay_30s=float(np.mean([r['restricted_delay_30s'] for r in rr])),
            coverage=float(np.mean([r['coverage'] for r in rr])),
            mean_alarm_bursts=float(np.mean([r['alarm_bursts'] for r in rr])),
            mean_flagged_epochs=float(np.mean([r['flagged_epoch_count'] for r in rr])))
        rates.append(d)
    rng=np.random.default_rng(44997);paired=[]
    basekeys=sorted(set(k[:-1] for k in groups))
    for key in basekeys:
        idx=rng.integers(0,len(TEST_SEEDS),size=(5000,len(TEST_SEEDS)))
        for comparator in ('v6_count','v6_universal','new_short_universal'):
            aa=groups[key+('new_long_universal',)];bb=groups[key+(comparator,)]
            for metric in ('generic_false','wrong_any','within_5s','first_correct'):
                delta=np.array([r[metric] for r in aa],int)-np.array([r[metric] for r in bb],int)
                paired.append(dict(zip(('profile','mode','amplitude','horizon'),key))|dict(contrast='new_long_universal - '+comparator,
                    metric=metric,difference=float(delta.mean()),percentile95=np.quantile(delta[idx].mean(axis=1),[.025,.975]).tolist()))
    look={tuple(r[k] for k in ('profile','mode','amplitude','horizon','method')):r for r in rates}
    criteria={}
    for p in PROFILES:
        h=look[p,'healthy',0.,600.,'new_long_universal'];f=look[p,'late_fault',6.,600.,'new_long_universal'];small=look[p,'late_fault',.5,600.,'new_long_universal']
        criteria[p+'_healthy_generic']=h['generic_false_rate']<=.10
        criteria[p+'_healthy_wrong_any']=h['wrong_any_rate']<=.05
        criteria[p+'_large_first_correct_5s']=f['within_5s_rate']>=.90
        criteria[p+'_half_unit_first_correct_5s']=small['within_5s_rate']>=.80
        criteria[p+'_availability']=h['coverage']>=.95
    doc=dict(source_hashes=sources(),calibration_sha256=sha(out/'calibration.json'),criteria=criteria,
        screen_passed=all(criteria.values()),records=len(records),cells=len(rates),paired_intervals=len(paired),
        independent_test_seeds=len(TEST_SEEDS),results=rates,paired=paired,
        scope='Downstream readout-only fault audit; 600s finite horizon; no closed-loop-fault or lifetime reliability claim.')
    save(out/'summary.json',doc)
    for fn,items in (('episode_metrics.csv',records),('rates.csv',rates),('paired.csv',paired)):
        with (out/fn).open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(items[0]));w.writeheader();w.writerows(items)
    print('SUMMARY',len(records),len(rates),'screen',sum(criteria.values()),len(criteria),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=('calibrate','freeze','evaluate','summarize'))
    p.add_argument('--out',type=Path,default=Path('results'));p.add_argument('--profile',choices=PROFILES)
    p.add_argument('--start',type=int,default=50000);p.add_argument('--stop',type=int,default=50200);a=p.parse_args()
    if a.phase=='calibrate':calibrate(a.out,a.profile)
    elif a.phase=='freeze':freeze(a.out)
    elif a.phase=='evaluate':evaluate(a.out,a.profile,a.start,a.stop)
    else:summarize(a.out)
