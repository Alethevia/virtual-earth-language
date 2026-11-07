"""Three bounded, predeclared sensor-readout experiments; NOT machine control.

Known covariance/zero offsets are commissioning information, not inferred truth.
Round 11 has a known target. Rounds 12/13 diagnose an unknown single channel.
All noise/fault transformations occur downstream of an unchanged controller.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import os
import platform
import sys
import time
from dataclasses import dataclass, asdict
from functools import lru_cache
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import scipy
from scipy.signal import lfilter
from scipy.fft import rfft, irfft, next_fast_len
from scipy.stats import norm
from numba import njit

PROTOCOL_COMMIT='4a7727421f3148aa6de2e0355b2879a7b53f9892'
DURATION=600.; START=5.; WINDOWS=(.2,.5,1.,2.,5.)
METHODS=('mean5','raw_scan','innovation_scan')
PAIRS=((0,1),(0,2),(1,2))
CAL_N=199
@dataclass(frozen=True)
class Config:
    fs: int
    scale: float=1.
    rho: float=.9
    @property
    def name(self)->str:
        return f'f{self.fs}_s{self.scale:g}_r{self.rho:g}'
    def __post_init__(self):
        if self.fs not in (2,10,20,100) or self.scale<=0 or not 0<=self.rho<1:
            raise ValueError('Invalid fixed configuration')
R11_CONFIGS=tuple(Config(f,s) for f in (2,10,20,100) for s in (1.,.7,.5))
R12_CONFIGS=(Config(100,1.,0.),Config(2),Config(20),Config(100),Config(20,.5))
R13_CONFIG=Config(20,.5)
R12_CASES=(('healthy',-1,0.,'none'),('primary025',0,.25,'step'),
 ('primary05',0,.5,'step'),('primary1',0,1.,'step'),('primary6',0,6.,'step'),
 ('aux1',1,.5,'step'),('aux2',2,.5,'step'),('pulse',0,.5,'pulse'),
 ('alternating',0,.5,'alternating'))
FAMILIES=('gaussian','student_latent','student_white','two_scale','rho99','gain25')
R13_CASES=tuple((f+'__'+kind,f,target,amp,shape) for f in FAMILIES
                for kind,target,amp,shape in (('healthy',-1,0.,'none'),('primary05',0,.5,'step')))+tuple(
 (name,'gaussian',target,amp,shape) for name,target,amp,shape in
 (('primary1',0,1.,'step'),('aux1',1,.5,'step'),('aux2',2,.5,'step'),
  ('pulse',0,.5,'pulse'),('two_aux',-2,.5,'two_aux'),('all_common',-3,.5,'all_common')))

def sha(path:Path|str)->str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path:Path|str,obj:object)->None:
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:
        json.dump(obj,f,indent=2,allow_nan=False);f.write('\n')
def write_csv(path:Path,rows:list[dict])->None:
    with path.open('x',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def manifest()->dict:
    return dict(protocol_commit=PROTOCOL_COMMIT,source_sha256=sha(__file__),
                python=sys.version,numpy=np.__version__,scipy=scipy.__version__,
                platform=platform.platform())
def verify_lock(root:Path)->None:
    lock=json.loads((root/'SOURCE_LOCK.json').read_text())
    if sha(__file__)!=lock['study.py']:raise RuntimeError('Locked experimental source changed')
def rank95(x:np.ndarray)->float:
    x=np.asarray(x,float)
    if x.shape!=(CAL_N,) or not np.isfinite(x).all():raise ValueError('Expected199 finite maxima')
    return float(np.sort(x)[189])
def wilson(k:int,n:int)->list[float]:
    if not 0<=k<=n or n<=0:raise ValueError('Invalid binomial count')
    z=1.959963984540054;p=k/n;den=1+z*z/n
    center=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0.,center-half),min(1.,center+half)]

def original_sensors(seed:int,cfg:Config,duration:float=DURATION)->np.ndarray:
    """Matched-law V10 readout noise, at base100Hz then downsampled.
    Same seed yields paired base white/latent innovations at all rates/scales.
    Physical common speed need not be generated because every rule uses differences.
    """
    n=round(duration*100)
    white=np.random.default_rng(np.random.SeedSequence([seed,11])).normal(0,.25,(3,n))
    if cfg.rho:
        z=np.random.default_rng(np.random.SeedSequence([seed,12])).normal(size=n)
        e=math.sqrt(.5*(1-cfg.rho**2))*z;e[0]=math.sqrt(.5)*z[0]
        white[0]+=lfilter([1.],[1.,-cfg.rho],e)
    return np.ascontiguousarray((cfg.scale*white[:,::100//cfg.fs]).T)

@njit(cache=True)
def explicit_state(z:np.ndarray,a:float,variance:float)->np.ndarray:
    """Separate recurrence used only by Round13; z has unit marginal variance."""
    result=np.empty(len(z));state=math.sqrt(variance)*z[0];result[0]=state
    sd=math.sqrt(variance*(1-a*a))
    for k in range(1,len(z)):
        state=a*state+sd*z[k];result[k]=state
    return result

def independent_sensors(seed:int,cfg:Config,family:str,duration:float=DURATION)->np.ndarray:
    """Independent implementation/PRNG, not independent real-world evidence."""
    if family not in FAMILIES:raise ValueError(family)
    n=round(duration*cfg.fs)
    rw=np.random.Generator(np.random.PCG64DXSM(np.random.SeedSequence([seed,31])))
    rz=np.random.Generator(np.random.PCG64DXSM(np.random.SeedSequence([seed,32])))
    z=rz.normal(size=n)
    if family=='student_white':white=rw.standard_t(3,size=(n,3))*.25/math.sqrt(3)
    else:white=rw.normal(0,.25,size=(n,3))
    a=cfg.rho**(100/cfg.fs)
    if family=='student_latent':
        # Warm up 2000 steps so non-Gaussian AR initialization is approximately stationary.
        zz=rz.standard_t(5,size=n+2000)/math.sqrt(5/3)
        latent=explicit_state(zz,a,.5)[2000:]
    elif family=='two_scale':
        z2=np.random.Generator(np.random.PCG64DXSM(np.random.SeedSequence([seed,33]))).normal(size=n)
        latent=explicit_state(z,a,.25)+explicit_state(z2,.99**(100/cfg.fs),.25)
    else:
        latent=explicit_state(z,(.99 if family=='rho99' else cfg.rho)**(100/cfg.fs),.5)
    if family=='gain25':white[int(180*cfg.fs):,0]*=1.25
    white[:,0]+=latent
    return np.ascontiguousarray(cfg.scale*white)

def fault_metadata(seed:int)->tuple[float,int]:
    rng=np.random.default_rng(np.random.SeedSequence([seed,99]))
    return float(rng.uniform(300,330)),int(rng.choice([-1,1]))
def inject(y:np.ndarray,cfg:Config,seed:int,target:int,amp:float,shape:str)->tuple[np.ndarray,float|None,float|None]:
    if target==-1:return y,None,None
    onset,sign=fault_metadata(seed);times=np.arange(len(y))/cfg.fs
    delta=sign*amp*(times>=onset)
    recovery=None
    if shape=='pulse':
        recovery=onset+2.;delta*=times<recovery
    elif shape=='alternating':
        phase=np.floor(np.maximum(0.,times-onset)/.5).astype(int)
        delta*=np.where(phase%2==0,1.,-1.)
    result=y.copy()
    channels=(1,2) if target==-2 else ((0,1,2) if target==-3 else (target,))
    for c in channels:result[:,c]+=delta
    return result,onset,recovery

def rolling_sum(x:np.ndarray,n:int)->np.ndarray:
    z=np.concatenate((np.zeros((*x.shape[:-1],1)),np.cumsum(x,axis=-1)),axis=-1)
    return z[...,n:]-z[...,:-n]

def covariance_sum(n:int,a:float,q:float,r:float)->float:
    k=np.arange(1,n,dtype=float)
    return float(n*(q+r)+2*q*np.sum((n-k)*a**k))

@lru_cache(maxsize=128)
def steady(a:float,q:float,r:float)->tuple[float,float,float]:
    P=q
    for _ in range(10000):
        pred=a*a*P+q*(1-a*a);gain=pred/(pred+r);new=(1-gain)*pred
        if abs(new-P)<1e-15:P=new;break
        P=new
    pred=a*a*P+q*(1-a*a);S=pred+r;gain=pred/S
    b=a*(1-gain)
    c=(1-a)/(1-b)
    return b,c,S

@lru_cache(maxsize=256)
def templates(cfg:Config,length:int)->tuple:
    a=cfg.rho**(100/cfg.fs);r=2*.25**2*cfg.scale**2
    q0=.5*cfg.scale**2 if cfg.rho else 0.
    ns=tuple(sorted(set(max(1,round(w*cfg.fs)) for w in WINDOWS)))
    nfft=next_fast_len(length+max(ns)-1)
    weights=[];spectra=[];normalizers=[];params=[]
    for pair in range(3):
        q=q0 if pair<2 else 0.;b,c,S=steady(a,q,r)
        if q==0:b=0.;c=1.;S=r
        params.append((a if q else 0.,b,c,S))
        ws=[];sp=[];normal=[]
        for n in ns:
            g=c+(1-c)*b**np.arange(n)
            kernel=g[::-1]/math.sqrt(S*float(g@g))
            ws.append(kernel);sp.append(rfft(kernel,nfft));normal.append(math.sqrt(covariance_sum(n,a,q,r)))
        weights.append(ws);spectra.append(sp);normalizers.append(normal)
    return ns,nfft,weights,np.array(spectra),np.array(normalizers),params

def scores(y:np.ndarray,cfg:Config)->np.ndarray:
    """Causal scores: shape(method,pair,time). Input ONLY three received values.
    Steady-state innovation initialization transient is included in calibration;
    no exact quickest-detection optimality claim is made.
    """
    y=np.asarray(y,float)
    if y.ndim!=2 or y.shape[1]!=3 or not np.isfinite(y).all() or len(y)<round(5*cfg.fs)+1:
        raise ValueError('Finite N x3 readouts, N>5seconds, required')
    d=np.stack([y[:,a]-y[:,b] for a,b in PAIRS])
    N=len(y);ns,nfft,_,spectra,norms,params=templates(cfg,N)
    out=np.zeros((3,3,N))
    e=np.empty_like(d)
    for j,(a,b,c,S) in enumerate(params):e[j]=lfilter([1.,-a],[1.,-b],d[j])
    E=rfft(e,nfft,axis=-1)
    for k,n in enumerate(ns):
        sm=rolling_sum(d,n)/norms[:,k,None]
        out[1,:,n-1:]=np.maximum(out[1,:,n-1:],np.abs(sm))
        if n==round(5*cfg.fs):out[0,:,n-1:]=np.abs(sm)
        filtered=irfft(E*spectra[:,k],nfft,axis=-1)[:,:N]
        out[2,:,n-1:]=np.maximum(out[2,:,n-1:],np.abs(filtered[:,n-1:]))
    out[:,:,:round(START*cfg.fs)]=0.
    return out

def binary_score(y:np.ndarray,cfg:Config)->np.ndarray:
    d=y[:,0]-.5*(y[:,1]+y[:,2]);n=round(5*cfg.fs)
    r=1.5*.25**2*cfg.scale**2;q=.5*cfg.scale**2 if cfg.rho else 0.
    s=np.zeros(len(y));s[n-1:]=np.abs(rolling_sum(d,n))/math.sqrt(covariance_sum(n,cfg.rho**(100/cfg.fs),q,r))
    s[:round(START*cfg.fs)]=0.
    return s

def labels_from_cross(c:np.ndarray)->np.ndarray:
    # pair axis length3, trailing time. -1 denotes no unique claim.
    out=np.full(c.shape[1],-1,dtype=np.int8)
    out[c[0]&c[1]&~c[2]]=0;out[c[0]&c[2]&~c[1]]=1;out[c[1]&c[2]&~c[0]]=2
    return out

def record(s:np.ndarray,threshold:float,cfg:Config,target:int,onset:float|None,recovery:float|None)->dict:
    cross=s>threshold
    if s.ndim==1:flags=cross;labels=np.where(flags,0,-1)
    else:flags=cross.any(axis=0);labels=labels_from_cross(cross)
    tt=np.arange(len(flags))/cfg.fs
    alarm=np.flatnonzero(flags);unique=np.flatnonzero(labels>=0)
    ft=None if not len(alarm) else float(tt[alarm[0]])
    ut=None if not len(unique) else float(tt[unique[0]])
    ul=-1 if not len(unique) else int(labels[unique[0]])
    single=target>=0 and onset is not None
    active=(tt>=onset) if onset is not None else np.zeros(len(tt),bool)
    if recovery is not None:active&=tt<recovery
    correct=bool(single and ut is not None and ul==target and ut>=onset and (recovery is None or ut<recovery))
    wrong=(labels>=0)&(~active | (labels!=target)) if single else labels>=0
    delay=ut-onset if correct else None
    return dict(any_alarm=bool(len(alarm)),first_alarm=ft,first_unique_time=ut,first_unique_label=ul,
        wrong_any=bool(wrong.any()),first_correct=correct,within5=bool(correct and delay<=5.),
        within30=bool(correct and delay<=30.),delay=delay,
        early_alarm=bool(onset is not None and ft is not None and ft<onset),
        early_unique=bool(onset is not None and ut is not None and ut<onset),
        post_recovery_accusation=bool(recovery is not None and np.any((tt>=recovery)&(labels>=0))),
        any_unique=bool(len(unique)),coverage=1.)

METRICS=('any_alarm','wrong_any','first_correct','within5','within30','early_alarm','early_unique','post_recovery_accusation','any_unique')
def summarize_rows(rows:list[dict])->list[dict]:
    groups={}
    for r in rows:groups.setdefault((r['config'],r['case'],r['method']),[]).append(r)
    output=[]
    for (config,case,method),rr in sorted(groups.items()):
        rr=sorted(rr,key=lambda r:r['seed']);n=len(rr)
        if len(set(r['seed'] for r in rr))!=n:raise AssertionError('Duplicate base seeds')
        item=dict(config=config,case=case,method=method,n=n)
        for key in METRICS:
            count=sum(r[key] for r in rr);item[key]=count;item[key+'_rate']=count/n
            item[key+'_wilson95']=wilson(count,n)
        delays=[r['delay'] for r in rr if r['delay'] is not None]
        item['conditional_median_delay']=None if not delays else float(np.median(delays))
        item['restricted_delay30']=float(np.mean([min(r['delay'],30.) if r['delay'] is not None else 30. for r in rr]))
        output.append(item)
    return output

def _root_checks(root:Path,out:Path)->None:
    verify_lock(root)
    if out.exists():raise FileExistsError('New output directory required: '+str(out))
    out.mkdir(parents=True)

def calibrate11(root:Path)->None:
    out=root/'r11';_root_checks(root,out);cfgrows=[]
    for cfg in R11_CONFIGS:
        maxima=[]
        for seed in range(910000,910000+CAL_N):maxima.append(float(binary_score(original_sensors(seed,cfg),cfg).max()))
        cfgrows.append(dict(config=asdict(cfg),name=cfg.name,maxima=maxima,threshold=rank95(np.array(maxima))))
        print('R11 CAL',cfg.name,cfgrows[-1]['threshold'],flush=True)
    save(out/'calibration.json',dict(manifest=manifest(),groups=cfgrows))

def evaluate11_task(args:tuple)->str:
    rootstr,cfgdict=args;root=Path(rootstr);cfg=Config(**cfgdict);out=root/'r11'
    cal=json.loads((out/'calibration.json').read_text());assert cal['manifest']['source_sha256']==sha(__file__)
    threshold=next(g['threshold'] for g in cal['groups'] if g['name']==cfg.name)
    rows=[];examples={}
    for seed in range(920000,920300):
        y=original_sensors(seed,cfg)
        for case,amp in (('healthy',0.),('primary025',.25),('primary05',.5),('primary1',1.)):
            target=-1 if amp==0 else 0;yy,on,rec=inject(y,cfg,seed,target,amp,'step')
            sc=binary_score(yy,cfg)
            rows.append(dict(config=cfg.name,case=case,method='known_target_mean5',seed=seed,**record(sc,threshold,cfg,target,on,rec)))
            if seed==920000 and case in ('healthy','primary05'):
                examples[case+'_input']=yy;examples[case+'_scores']=sc
    save(out/(cfg.name+'.json'),dict(config=asdict(cfg),threshold=threshold,calibration_sha256=sha(out/'calibration.json'),rows=rows))
    np.savez_compressed(out/(cfg.name+'_examples.npz'),**examples)
    return cfg.name

def calibrate12(root:Path)->None:
    out=root/'r12';_root_checks(root,out);groups=[]
    for cfg in R12_CONFIGS:
        maxima=[]
        for seed in range(930000,930000+CAL_N):maxima.append(scores(original_sensors(seed,cfg),cfg).max(axis=(1,2)).tolist())
        mm=np.array(maxima);th=[rank95(mm[:,j]) for j in range(3)]
        groups.append(dict(config=asdict(cfg),name=cfg.name,maxima=maxima,thresholds=dict(zip(METHODS,th))))
        print('R12 CAL',cfg.name,th,flush=True)
    save(out/'calibration.json',dict(manifest=manifest(),groups=groups))

def evaluate12_task(args:tuple)->str:
    rootstr,cfgdict=args;root=Path(rootstr);cfg=Config(**cfgdict);out=root/'r12'
    cal=json.loads((out/'calibration.json').read_text());assert cal['manifest']['source_sha256']==sha(__file__)
    thresholds=next(g['thresholds'] for g in cal['groups'] if g['name']==cfg.name)
    rows=[];examples={}
    for seed in range(940000,940200):
        y=original_sensors(seed,cfg)
        for case,target,amp,shape in R12_CASES:
            yy,on,rec=inject(y,cfg,seed,target,amp,shape);ss=scores(yy,cfg)
            for j,m in enumerate(METHODS):
                rows.append(dict(config=cfg.name,case=case,method=m,seed=seed,**record(ss[j],thresholds[m],cfg,target,on,rec)))
            if seed==940000 and case in ('healthy','primary05','pulse'):
                examples[case+'_input']=yy;examples[case+'_scores']=ss
    save(out/(cfg.name+'.json'),dict(config=asdict(cfg),thresholds=thresholds,calibration_sha256=sha(out/'calibration.json'),rows=rows))
    np.savez_compressed(out/(cfg.name+'_examples.npz'),**examples)
    return cfg.name

def aggregate(root:Path,roundnum:int)->dict:
    out=root/f'r{roundnum}'
    configs=R11_CONFIGS if roundnum==11 else R12_CONFIGS
    rows=[]
    for cfg in configs:
        doc=json.loads((out/(cfg.name+'.json')).read_text())
        assert doc['calibration_sha256']==sha(out/'calibration.json')
        rows.extend(doc['rows'])
    rates=summarize_rows(rows)
    result=dict(manifest=manifest(),round=roundnum,n_records=len(rows),results=rates)
    if roundnum==12:
        criteria={}
        for cfg in configs:
            for m in METHODS:
                look={r['case']:r for r in rates if r['config']==cfg.name and r['method']==m}
                tests=dict(false_any=look['healthy']['any_alarm_rate']<=.1,wrong_any=look['healthy']['wrong_any_rate']<=.05,
                   small_timely=look['primary05']['within5_rate']>=.8,one_timely=look['primary1']['within5_rate']>=.9)
                criteria[cfg.name+'__'+m]=dict(checks=tests,pass_all=all(tests.values()))
        result['criteria']=criteria
    save(out/'summary.json',result);write_csv(out/'rates.csv',rates);write_csv(out/'records.csv',rows)
    return result

def select13(root:Path)->None:
    rates=json.loads((root/'r12/summary.json').read_text())['results'];cfg=R13_CONFIG
    eligible=[]
    for priority,m in enumerate(METHODS):
        look={r['case']:r for r in rates if r['config']==cfg.name and r['method']==m}
        if look['healthy']['any_alarm_rate']<=.1 and look['healthy']['wrong_any_rate']<=.05:
            eligible.append((-look['primary05']['within5'],priority,m))
    selected=min(eligible)[2] if eligible else 'mean5'
    cal=json.loads((root/'r12/calibration.json').read_text())
    thresholds=next(g['thresholds'] for g in cal['groups'] if g['name']==cfg.name)
    save(root/'SELECTION_LOCK.json',dict(source_sha256=sha(__file__),config=asdict(cfg),selected=selected,
          selection_failed=not bool(eligible),thresholds=thresholds,
          selection_rule='Max .5 within5 among healthy error eligible; ties prefer mean5,raw,innovation.',
          r12_summary_sha256=sha(root/'r12/summary.json'),calibration_sha256=sha(root/'r12/calibration.json')))
    print('FROZEN R13 SELECTION',selected,flush=True)

def evaluate13_task(args:tuple)->str:
    rootstr,casedef=args;root=Path(rootstr);out=root/'r13'
    lock=json.loads((root/'SELECTION_LOCK.json').read_text());assert lock['source_sha256']==sha(__file__)
    cfg=Config(**lock['config']);selected=lock['selected'];methods=tuple(dict.fromkeys(('mean5',selected)))
    case,family,target,amp,shape=casedef;rows=[];examples={}
    for seed in range(950000,950400):
        y=independent_sensors(seed,cfg,family);yy,on,rec=inject(y,cfg,seed,target,amp,shape);ss=scores(yy,cfg)
        for m in methods:
            rows.append(dict(config=cfg.name,case=case,method=m,seed=seed,**record(ss[METHODS.index(m)],lock['thresholds'][m],cfg,target,on,rec)))
        if seed==950000:examples=dict(input=yy,scores=ss)
    save(out/(case+'.json'),dict(case=case,case_definition=casedef,selection_sha256=sha(root/'SELECTION_LOCK.json'),rows=rows))
    np.savez_compressed(out/(case+'_example.npz'),**examples)
    return case

def aggregate13(root:Path)->dict:
    out=root/'r13';rows=[];lock=json.loads((root/'SELECTION_LOCK.json').read_text())
    for case,*_ in R13_CASES:
        d=json.loads((out/(case+'.json')).read_text());assert d['selection_sha256']==sha(root/'SELECTION_LOCK.json')
        rows.extend(d['rows'])
    rates=summarize_rows(rows);criteria={}
    for m in dict.fromkeys(('mean5',lock['selected'])):
        look={r['case']:r for r in rates if r['method']==m}
        tests={}
        for fam in FAMILIES:
            h=look[fam+'__healthy'];f=look[fam+'__primary05']
            tests[fam]=dict(false_any=h['any_alarm_rate']<=.1,wrong_any=h['wrong_any_rate']<=.05,timely=f['within5_rate']>=.8)
        nominal=all(tests['gaussian'].values()) and look['primary1']['within5_rate']>=.9 and all(look[c]['within5_rate']>=.8 for c in ('aux1','aux2'))
        criteria[m]=dict(families=tests,matched_confirmation_pass=nominal,broad_robustness_pass=nominal and all(all(v.values()) for v in tests.values()))
    result=dict(manifest=manifest(),round=13,selected=lock['selected'],n_records=len(rows),results=rates,criteria=criteria)
    save(out/'summary.json',result);write_csv(out/'rates.csv',rates);write_csv(out/'records.csv',rows)
    return result

def run_tasks(fn,args,workers:int):
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for name in pool.map(fn,args):print('COMPLETED',name,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase',choices=('cal11','eval11','cal12','eval12','select13','eval13'))
    p.add_argument('--root',type=Path,required=True);p.add_argument('--workers',type=int,default=2)
    a=p.parse_args();verify_lock(a.root)
    if a.phase=='cal11':calibrate11(a.root)
    elif a.phase=='eval11':run_tasks(evaluate11_task,[(str(a.root),asdict(c)) for c in R11_CONFIGS],a.workers);aggregate(a.root,11)
    elif a.phase=='cal12':calibrate12(a.root)
    elif a.phase=='eval12':run_tasks(evaluate12_task,[(str(a.root),asdict(c)) for c in R12_CONFIGS],a.workers);aggregate(a.root,12)
    elif a.phase=='select13':select13(a.root)
    elif a.phase=='eval13':
        if (a.root/'r13').exists():raise FileExistsError('Use fresh r13 directory')
        (a.root/'r13').mkdir();run_tasks(evaluate13_task,[(str(a.root),c) for c in R13_CASES],a.workers);aggregate13(a.root)
