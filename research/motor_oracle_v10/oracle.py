"""V10 oracle detectability audit. Known-model diagnostic READOUT simulation only.
An ideal simple-hypothesis bound is not a deployable monitor or an anytime claim.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, math, sys
from pathlib import Path
from functools import lru_cache
import numpy as np
from scipy.linalg import toeplitz, cho_factor, cho_solve
from scipy.signal import fftconvolve, lfilter
from scipy.stats import norm

PROFILES=('dense_iid','sparse_iid','dense_ar','sparse_ar','dense_ar99','sparse_ar99')
CAL_STARTS=tuple(81000+300*j for j in range(6))
TEST_START=85000
CAL_N=199
TEST_N=200
MC_N=20000
MC_SEED=2026110601
AMPLITUDES=(.125,.25,.5,1.,2.,6.)
DEADLINES=(.5,1.,2.,5.,10.,30.)
ALPHAS=(.05,.10)
DURATION=600.
WINDOW=5.
PROFILE_SEED=2026110602
VAR_WHITE_PRIMARY=.25**2
VAR_WHITE_CONTRAST=.25**2*1.5
VAR_AR=.75**2-.25**2
PARENT_HASHES={
 'motor_horizon_v7/horizon.py':'3e026b467693184d2b26a256e0f00a643ba5c9242eeb64678ae00bcaaa0ebdb1',
 'motor_cusum_v8/cusum_study.py':'82df678ef7ab82db02580c5b6c058d97f9c727f16f8830814a2bd2934402268a',
 'motor_whitening_v9/whitening.py':'fa91377767f25aa848b0a4193c19c3d1973dd1eeab7488060975104a58f3b4d2'}


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sources():
    result={'oracle.py':sha(__file__)}
    for rel,want in PARENT_HASHES.items():
        p=Path(__file__).resolve().parent.parent/rel
        if p.exists():
            actual=sha(p)
            if actual!=want:raise RuntimeError('Parent source changed: '+rel)
            result[rel]=actual
    return result

def save(path,obj):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n')

def write_csv(path,rows):
    with Path(path).open('x',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def config(profile):
    if profile not in PROFILES:raise ValueError(profile)
    step=50 if profile.startswith('sparse') else 1
    rho=.99 if profile.endswith('ar99') else (.9 if profile.endswith('ar') else 0.)
    q=VAR_AR if rho else 0.
    return step,step*.01,rho**step,q


def covariance(n,a,q,r,initial='stationary'):
    """Covariance of x_0..x_(n-1), x_t=a*x_(t-1)+v_t + independent w_t.
    perfect_state means latent state at LAST PRE-FAULT ACQUISITION is known;
    it is not knowledge of the future AR innovations.
    """
    idx=np.arange(n)
    C=q*a**np.abs(idx[:,None]-idx[None,:])+r*np.eye(n)
    if initial=='perfect_state':C-=q*np.outer(a**(idx+1),a**(idx+1))
    elif initial!='stationary':raise ValueError(initial)
    return C


def info_recurrence(n,a,q,r,initial='stationary'):
    """Exact scalar Kalman innovation factorization, not an estimated AR fit."""
    if n<1 or not 0<=a<1 or q<0 or r<=0:raise ValueError('Invalid model')
    P=q if initial=='stationary' else 0.
    if initial not in ('stationary','perfect_state'):raise ValueError(initial)
    template_state=0.;g=np.empty(n);gains=np.empty(n);variance=np.empty(n)
    for k in range(n):
        predP=a*a*P+q*(1-a*a)
        S=predP+r;K=predP/S
        predmean=a*template_state
        g[k]=(1.-predmean)/math.sqrt(S)
        template_state=predmean+K*(1.-predmean)
        P=(1-K)*predP;gains[k]=K;variance[k]=S
    return float(g@g),g,gains,variance


def oracle_grid(out):
    rows=[]
    tiers=(('contrast_post_only',VAR_WHITE_CONTRAST,'stationary'),
           ('contrast_latent_genie',VAR_WHITE_CONTRAST,'perfect_state'),
           ('truth_speed_latent_genie',VAR_WHITE_PRIMARY,'perfect_state'))
    for p in PROFILES:
        _,dt,a,q=config(p)
        for deadline in DEADLINES:
            # Continuous onset independent of grid: exactly floor(D/dt) for these multiples,
            # except probability-zero exact grid equality. Original .2s decisions cannot add data.
            n=int(round(deadline/dt))
            for tier,r,init in tiers:
                info,*_=info_recurrence(n,a,q,r,init)
                for alpha in ALPHAS:
                    for amplitude in AMPLITUDES:
                        snr=amplitude*math.sqrt(info)
                        rows.append(dict(profile=p,tier=tier,deadline_s=deadline,n_observations=n,
                          alpha=alpha,amplitude=amplitude,information_per_squared_amplitude=info,
                          power=float(norm.cdf(snr-norm.isf(alpha))),
                          minimum_amplitude_for_power_80=float((norm.isf(alpha)+norm.ppf(.8))/math.sqrt(info)),
                          scope='Known onset/sign/target and model. Genie tiers add latent-state truth; highest tier also true speed.'))
    write_csv(Path(out)/'oracle_power.csv',rows)
    save(Path(out)/'oracle_power.json',dict(source_hashes=sources(),rows=rows))
    core=[x for x in rows if x['deadline_s']==5 and x['amplitude']==.5 and x['alpha']==.1 and x['tier']=='truth_speed_latent_genie']
    print('IDEAL_FIVE_SECOND',[(x['profile'],x['power'],x['minimum_amplitude_for_power_80']) for x in core],flush=True)


def monte_carlo(out):
    """Explicit colored-noise observations, exact innovations, no scalar-N shortcut.
    All paths are conditional on a known zero previous latent value, equivalent
    to subtracting the oracle-known nonzero state's predicted mean.
    """
    records=[];examples={}
    for pi,p in enumerate(PROFILES):
        _,dt,a,q=config(p);n=int(round(5/dt))
        for ti,(tier,r) in enumerate((('contrast_latent_genie',VAR_WHITE_CONTRAST),('truth_speed_latent_genie',VAR_WHITE_PRIMARY))):
            info,g,K,S=info_recurrence(n,a,q,r,'perfect_state')
            rng=np.random.default_rng(np.random.SeedSequence([MC_SEED,pi,ti]))
            allz=[]
            for b in range(0,MC_N,500):
                size=min(500,MC_N-b);state=np.zeros(size);estimate=np.zeros(size);stat=np.zeros(size)
                raw=np.empty((min(size,2),n)) if b==0 else None
                for k in range(n):
                    state=a*state+rng.normal(0,math.sqrt(q*(1-a*a)),size)
                    y=state+rng.normal(0,math.sqrt(r),size)
                    prior=a*estimate;innovation=y-prior
                    estimate=prior+K[k]*innovation
                    stat+=g[k]*innovation/math.sqrt(S[k])
                    if raw is not None:raw[:,k]=y[:len(raw)]
                z=stat/math.sqrt(info);allz.extend(z.tolist())
                if raw is not None:examples[p+'__'+tier]=raw
            z=np.array(allz)
            examples[p+'__'+tier+'__null_Z']=z
            for alpha in ALPHAS:
                th=norm.isf(alpha);hit0=z>th;hit1=z+.5*math.sqrt(info)>th
                expected=float(norm.cdf(.5*math.sqrt(info)-th))
                records.append(dict(profile=p,tier=tier,n=MC_N,alpha=alpha,false_count=int(hit0.sum()),
                    false_rate=float(hit0.mean()),power_count=int(hit1.sum()),power_rate=float(hit1.mean()),
                    analytic_power=expected,z_mean=float(z.mean()),z_variance=float(z.var(ddof=1))))
    np.savez_compressed(Path(out)/'oracle_mc_inputs.npz',**examples)
    write_csv(Path(out)/'oracle_mc.csv',records)
    save(Path(out)/'oracle_mc.json',dict(source_hashes=sources(),rows=records,n_observation_windows=MC_N*12,
         scope='Conditional Gaussian observation simulations, not physical devices; alpha outcomes share paths.'))
    print('MONTE_CARLO',len(records),'cells',flush=True)


def generate_contrast(seed,profile,duration=DURATION):
    """Algebraic reduction of V7/V8 diagnostic readings after common speed and
    known per-path auxiliary offsets are removed. Sensors/noise unchanged;
    true offsets supplied to this ORACLE reference, unlike a deployable detector.
    """
    step,dt,a,q=config(profile);nfull=round(duration/.01)
    white=np.random.default_rng(seed+10000000).normal(0,.25,size=(nfull,3))
    d=white[:,0]-.5*(white[:,1]+white[:,2])
    if q:
        rho=.99 if profile.endswith('ar99') else .9
        stream=12000000 if rho==.99 else 10000002
        z=np.random.default_rng(seed+stream).normal(size=nfull)
        innovations=math.sqrt(q*(1-rho*rho))*z
        innovations[0]=math.sqrt(q)*z[0]
        d+=lfilter([1.],[1.,-rho],innovations)
    return d[::step]


@lru_cache(maxsize=6)
def weights(profile):
    step,dt,a,q=config(profile);n=int(round(WINDOW/dt))
    C=covariance(n,a,q,VAR_WHITE_CONTRAST,'stationary');one=np.ones(n)
    ci=cho_solve(cho_factor(C,lower=True),one)
    gls=ci/math.sqrt(one@ci)
    mean=one/math.sqrt(float(one@C@one))
    return np.stack((mean,gls))


def scan(x,profile):
    """Causal five-second windows. Only x and fixed known-model weights enter.
    Unknown sign and onset; target channel and correct noise model are supplied.
    Endpoints use ALL acquired samples (more favorable than old .2s grid).
    """
    x=np.asarray(x,float)
    if x.ndim!=1 or not np.isfinite(x).all():raise ValueError('Finite scalar contrasts required')
    w=weights(profile)
    if len(x)<w.shape[1]:raise ValueError('Insufficient length')
    return np.stack([fftconvolve(x,ww[::-1],mode='valid') for ww in w])


def calibrate(out):
    out=Path(out);groups={}
    for pi,p in enumerate(PROFILES):
        rows=[]
        for seed in range(CAL_STARTS[pi],CAL_STARTS[pi]+CAL_N):
            s=scan(generate_contrast(seed,p),p)
            rows.append(dict(seed=seed,maxima=np.max(np.abs(s),axis=1).tolist()))
        maxima=np.array([r['maxima'] for r in rows]);thresholds=np.sort(maxima,axis=0)[189]
        groups[p]=dict(rank=190,n=CAL_N,thresholds=thresholds.tolist(),rows=rows)
        print('CALIBRATED',p,thresholds,flush=True)
    save(out/'calibration.json',dict(source_hashes=sources(),groups=groups,alpha=.05,
        scope='Separate whole-600s-path maxima for two fixed rules; correct noise parameters supplied.'))


def outcomes(times,flags,onset):
    ids=np.flatnonzero(flags);first=None if not len(ids) else float(times[ids[0]])
    correct=bool(onset is not None and first is not None and first>=onset)
    delay=first-onset if correct else None
    return dict(first_alarm=first,any_alarm=bool(len(ids)),
         pre_fault_alarm=bool(onset is not None and first is not None and first<onset),
         first_alarm_valid=correct,within_5s=bool(correct and delay<=5.),within_30s=bool(correct and delay<=30.),
         delay=delay)


def evaluate(out,profile):
    out=Path(out);cal=json.loads((out/'calibration.json').read_text())
    assert sources()==cal['source_hashes']
    if (out/f'test_{profile}.json').exists():raise FileExistsError('Do not overwrite evaluation')
    _,dt,_,_=config(profile);length=round(DURATION/dt);nw=weights(profile).shape[1]
    times=np.arange(nw-1,length)*dt
    models=[('correct_model',profile)]
    if profile.endswith('ar99'):models.append(('misspecified_rho09',profile.replace('ar99','ar')))
    records=[];flags_all=[];index=[]
    for seed in range(TEST_START,TEST_START+TEST_N):
        x=generate_contrast(seed,profile)
        rng=np.random.default_rng(seed+13000000)
        sign=int(rng.choice([-1,1]));onset=float(rng.uniform(300,330))
        cases=[('healthy',0.,None)]+[('bias',a,onset) for a in (.5,1.,6.)]
        base_scores={model:scan(x,fp) for model,fp in models}
        step=(np.arange(length)*dt>=onset).astype(float)
        response={model:scan(step,fp) for model,fp in models}
        for mode,amp,start in cases:
            for model,fp in models:
                sc=base_scores[model]+sign*amp*response[model]
                th=np.array(cal['groups'][fp]['thresholds'])
                flags=np.abs(sc)>th[:,None]
                flags_all.append(np.packbits(flags,axis=1))
                index.append(dict(seed=seed,mode=mode,amplitude=amp,onset=start,model=model))
                for j,m in enumerate(('mean5','gls5')):
                    records.append(dict(profile=profile,seed=seed,mode=mode,amplitude=amp,onset=start,
                      model=model,method=m,**outcomes(times,flags[j],start)))
                if seed==TEST_START and amp in (0.,.5):
                    np.savez_compressed(out/f'example_{profile}_{model}_{mode}_{amp:g}.npz',
                        contrast=x+sign*amp*step,scores=sc,times=times,thresholds=th)
    np.savez_compressed(out/f'test_{profile}_flags.npz',flags=np.array(flags_all),times=times)
    save(out/f'test_{profile}.json',dict(source_hashes=sources(),calibration_hash=sha(out/'calibration.json'),
         index=index,records=records))
    print('EVALUATED',profile,len(records),'records',flush=True)


def wilson(k,n):
    z=norm.isf(.025);p=k/n;d=1+z*z/n
    c=(p+z*z/(2*n))/d;s=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0.,c-s),min(1.,c+s)]


def summarize(out):
    out=Path(out);records=[];rows=[]
    for p in PROFILES:
        d=json.loads((out/f'test_{p}.json').read_text())
        assert d['source_hashes']==sources() and d['calibration_hash']==sha(out/'calibration.json')
        records+=d['records']
    groups={}
    for r in records:
        key=tuple(r[k] for k in ('profile','mode','amplitude','model','method'))
        groups.setdefault(key,[]).append(r)
    for key,rr in sorted(groups.items()):
        assert sorted(r['seed'] for r in rr)==list(range(TEST_START,TEST_START+TEST_N))
        d=dict(zip(('profile','mode','amplitude','model','method'),key));d['n']=len(rr)
        for metric in ('any_alarm','pre_fault_alarm','first_alarm_valid','within_5s','within_30s'):
            k=sum(r[metric] for r in rr);d[metric+'_count']=k;d[metric+'_rate']=k/len(rr);d[metric+'_wilson95']=wilson(k,len(rr))
        delays=[r['delay'] for r in rr if r['delay'] is not None]
        d['conditional_median_delay']=float(np.median(delays)) if delays else None
        rows.append(d)
    write_csv(out/'scan_records.csv',records);write_csv(out/'scan_rates.csv',rows)
    save(out/'summary.json',dict(source_hashes=sources(),rows=rows,records=len(records),cells=len(rows),
        calibration_paths=CAL_N*6,test_scenarios=TEST_N*6*4,independent_test_seed_groups=TEST_N,
        limitation='Known-primary binary detection, true offsets and covariance supplied. Not unique channel diagnosis.'))
    for r in rows:
        if r['amplitude'] in (0.,.5) and r['method']=='gls5':
            print('REFERENCE',r['profile'],r['model'],r['amplitude'],'alarm',r['any_alarm_count'],'within5',r['within_5s_count'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=('theory','mc','calibrate','evaluate','summarize'))
    p.add_argument('--out',type=Path,default=Path('results'));p.add_argument('--profile',choices=PROFILES)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    if a.phase=='theory':oracle_grid(a.out)
    elif a.phase=='mc':monte_carlo(a.out)
    elif a.phase=='calibrate':calibrate(a.out)
    elif a.phase=='evaluate':evaluate(a.out,a.profile)
    else:summarize(a.out)
