"""V6: whole-episode count-stratified calibration. SIMULATION ONLY.
Count is distinct common acquisition timestamps, NOT an estimated statistical
independent-sample size. Parent detector and controller are unchanged.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, math, sys, time
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'motor_telemetry_v5'))
import telemetry as v5
PARENT='eb48c71c73fc38cdc7121b977bce817e77b6aaae'
EXPECTED_V5='e26f86c34c18cc57436efc2980134cf8a59c869375068b52acc7181c9ca6b956'
CAL_RANGES=(range(39000,39199),range(39200,39399),range(39400,39599))
TEST_SEEDS=range(41000,41200)
CAL_PROFILES=('healthy','healthy_shift','healthy_quantized','healthy_witness_delay',
              'healthy_primary_noise','healthy_high_noise','healthy_nonlinear')
EXTRA=('healthy_mid_reporting','bias_mid_reporting','healthy_rate_switch','bias_rate_switch',
       'healthy_many_rate_changes','bias_many_rate_changes','healthy_correlated_noise',
       'bias_correlated_noise','healthy_very_sparse','bias_very_sparse')
CONDITIONS=v5.CONDITIONS+EXTRA
METHODS=('v5_frozen_quality','pooled_quality','count_quality','max_group_quality','count_time_only','always_abstain')
HEALTHY_SCREEN=('healthy','healthy_shift','healthy_late_shift','healthy_nonlinear','healthy_quantized',
 'healthy_slow_reporting','healthy_witness_delay','healthy_primary_noise','healthy_high_noise','healthy_mid_reporting')
FAULT_SCREEN=('bias','bias_shift','bias_late_shift','drift','stuck','stuck_noisy_readout','bias_nonlinear',
 'bias_quantized','bias_slow_reporting','stuck_slow_reporting','bias_witness_delay','bias_primary_noise',
 'bias_mid_reporting','aux1_bias','aux2_bias')
FROZEN_QUALITY=1.694663815648237
ALPHA=.05


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def sources():
    x=v5.source_hashes()
    if x['telemetry.py']!=EXPECTED_V5:raise RuntimeError('V5 changed')
    return {**x,'calibration_study.py':sha(__file__)}
def save_new(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n')
def group_ids(counts):
    n=np.asarray(counts)
    if not np.issubdtype(n.dtype,np.integer) or (n<0).any():raise ValueError('Counts must be nonnegative integers')
    return np.where(n<3,-1,np.where(n<=5,0,np.where(n<=25,1,2)))
def rank_threshold(values,alpha=ALPHA):
    x=np.asarray(values,float)
    if x.ndim!=1 or len(x)==0 or not np.isfinite(x).all() or not 0<alpha<1:raise ValueError('Invalid calibration')
    k=math.ceil((len(x)+1)*(1-alpha))
    return math.inf if k>len(x) else float(np.sort(x)[k-1])


def resample_primary(p,kind):
    """Causal sample/hold, after the controller tap. Never creates extra observations."""
    n=len(p.values);ticks=np.arange(n)
    if isinstance(kind,int):sample=(ticks//kind)*kind
    else:
        sample=np.zeros(n,dtype=int);last=0
        for t in range(n):
            period=(50 if t<800 else 1) if kind=='switch' else (50 if (t//200)%2==0 else 1)
            if t%period==0:last=t
            sample[t]=last
    values=p.values.copy();stamps=p.stamps.copy()
    values[:,0]=p.values[sample,0];stamps[:,0]=p.stamps[sample,0]
    return v5.Packets(values,stamps,p.sigma.copy(),p.quantum.copy(),p.offset_bound.copy())


def generate(seed,condition):
    if condition not in CONDITIONS:raise ValueError(condition)
    if condition in v5.CONDITIONS:return v5.generate(seed,condition)
    base='bias' if condition.startswith('bias_') else 'healthy'
    p,meta,cost=v5.generate(seed,base)
    if condition.endswith('mid_reporting'):p=resample_primary(p,20)
    elif condition.endswith('very_sparse'):p=resample_primary(p,100)
    elif condition.endswith('many_rate_changes'):p=resample_primary(p,'many')
    elif condition.endswith('rate_switch'):p=resample_primary(p,'switch')
    elif condition.endswith('correlated_noise'):
        rng=np.random.default_rng(seed+7000000);rho=.9
        ar=np.empty(len(p.values));ar[0]=rng.normal()
        for t in range(1,len(ar)):ar[t]=rho*ar[t-1]+math.sqrt(1-rho*rho)*rng.normal()
        y=p.values.copy();y[:,0]+=math.sqrt(.75**2-.25**2)*ar
        sigma=p.sigma.copy();sigma[0]=.75
        p=v5.Packets(y,p.stamps.copy(),sigma,p.quantum.copy(),p.offset_bound.copy())
    return p,dict(meta,condition=condition,profile='v6_stress'),cost


def calibration_episode(seed,group):
    rng=np.random.default_rng(seed+8000000)
    profile=CAL_PROFILES[int(rng.integers(len(CAL_PROFILES)))]
    periods=((50,),(10,20),(1,2,5))
    period=int(periods[group][int(rng.integers(len(periods[group])))])
    p,_,_=v5.generate(seed,profile)
    return resample_primary(p,period),profile,period


def calibrate(out):
    out=Path(out);lock=sources();rows=[];examples=[];tic=time.perf_counter()
    if (out/'calibration.json').exists():raise FileExistsError('Existing calibration')
    for group,seeds in enumerate(CAL_RANGES):
        for seed in seeds:
            p,profile,period=calibration_episode(seed,group)
            s,a,count,age=v5.features(p)
            if not a[:,3].all() or not (group_ids(count)==group).all():raise AssertionError('Calibration does not stay within declared count group')
            rows.append(dict(seed=seed,group=group,profile=profile,period=period,
                min_count=int(count.min()),max_count=int(count.max()),
                quality_max=float(s[:,3].max()),aligned_max=float(s[:,2].max())))
    q=[r['quality_max'] for r in rows]
    group_q=[rank_threshold([r['quality_max'] for r in rows if r['group']==g]) for g in range(3)]
    group_a=[rank_threshold([r['aligned_max'] for r in rows if r['group']==g]) for g in range(3)]
    doc=dict(source_hashes=lock,rows=rows,n=597,n_per_group=199,alpha=ALPHA,
        group_rank=190,pooled_rank=569,thresholds=dict(pooled_quality=rank_threshold(q),
        count_quality=group_q,max_group_quality=max(group_q),count_time_only=group_a),
        elapsed_seconds=time.perf_counter()-tic)
    save_new(out/'calibration.json',doc)
    print('CALIBRATED',doc['thresholds'],flush=True)


def decisions(f,thresholds):
    s,a,n,age=f;g=group_ids(n);valid=a[:,3]&(g>=0);idx=np.maximum(0,g)
    table={
      'v5_frozen_quality':(3,np.full(len(n),FROZEN_QUALITY)),
      'pooled_quality':(3,np.full(len(n),thresholds['pooled_quality'])),
      'count_quality':(3,np.array(thresholds['count_quality'])[idx]),
      'max_group_quality':(3,np.full(len(n),thresholds['max_group_quality'])),
      'count_time_only':(2,np.array(thresholds['count_time_only'])[idx])}
    out={}
    for name,(col,th) in table.items():
        cross=(s[:,col]>th[:,None])&valid[:,None]
        label=np.full(len(n),-1,int)
        label[cross[:,0]&cross[:,1]&~cross[:,2]]=0
        label[cross[:,0]&cross[:,2]&~cross[:,1]]=1
        label[cross[:,1]&cross[:,2]&~cross[:,0]]=2
        out[name]=(label,cross.any(axis=1),valid.copy())
    out['always_abstain']=(np.full(len(n),-1,int),np.zeros(len(n),bool),valid.copy())
    return out


def record(times,labels,flags,available,meta):
    r=v5.record(times,labels,flags,available,meta)
    onset=meta['anomaly_onset'];target=meta['single_target']
    if target is not None:
        wrong=(labels>=0)&((times<onset)|(labels!=target))
    elif onset is None:
        wrong=labels>=0
    else:
        # Multi-fault cases have no declared uniquely correct one-channel answer.
        wrong=labels>=0
    r['wrong_any_episode']=bool(wrong.any())
    r['any_unique_episode']=bool((labels>=0).any())
    r['generic_false_episode']=bool(flags.any()) if onset is None else bool((flags&(times<onset)).any())
    r['first_correct_delay']=r['any_unique']-onset if r['unique_correct'] else None
    r['any_correct_after_onset']=bool(target is not None and ((labels==target)&(times>=onset)).any()) if onset is not None else False
    r['post_fault_coverage']=float(available[times>=onset].mean()) if onset is not None and (times>=onset).any() else None
    return r


def evaluate(out,condition):
    out=Path(out);cal=json.loads((out/'calibration.json').read_text());tic=time.perf_counter()
    if cal['source_hashes']!=sources():raise AssertionError('Sources changed after calibration')
    if (out/f'{condition}.json').exists():raise FileExistsError('Existing evaluation')
    rows=[];metas=[];scores=[];avails=[];counts=[];ages=[]
    for seed in TEST_SEEDS:
        p,meta,_=generate(seed,condition);f=v5.features(p)
        times=np.arange(200,len(p.values),20)*.01
        scores.append(f[0]);avails.append(f[1]);counts.append(f[2]);ages.append(f[3]);metas.append(meta)
        for name,(label,flag,valid) in decisions(f,cal['thresholds']).items():
            rows.append(dict(condition=condition,seed=seed,method=name,**record(times,label,flag,valid,meta)))
        if seed==TEST_SEEDS.start:
            np.savez_compressed(out/f'{condition}_example.npz',values=p.values,stamps=p.stamps,
                sigma=p.sigma,quantum=p.quantum,offset_bound=p.offset_bound)
    np.savez_compressed(out/f'{condition}_features.npz',scores=np.array(scores),available=np.array(avails),
        counts=np.array(counts),ages=np.array(ages),times=times)
    save_new(out/f'{condition}.json',dict(source_hashes=sources(),calibration_sha256=v5.sha(out/'calibration.json'),
        metadata=metas,rows=rows,elapsed_seconds=time.perf_counter()-tic))
    print('EVALUATED',condition,round(time.perf_counter()-tic,3),flush=True)


def summarize(out):
    out=Path(out);cal=json.loads((out/'calibration.json').read_text());rows=[]
    for c in CONDITIONS:
        d=json.loads((out/f'{c}.json').read_text())
        assert d['source_hashes']==sources() and d['calibration_sha256']==v5.sha(out/'calibration.json')
        rows.extend(d['rows'])
    rates=[];pairs=[];rng=np.random.default_rng(44996)
    metrics=('primary_event','unique_correct','wrong_any_episode','generic_false_episode','anomaly_valid','any_correct_after_onset')
    for c in CONDITIONS:
        groups={}
        for method in METHODS:
            rr=sorted([r for r in rows if r['condition']==c and r['method']==method],key=lambda x:x['seed'])
            assert [r['seed'] for r in rr]==list(TEST_SEEDS)
            n=len(rr);rate=dict(condition=c,method=method,n=n)
            for m in metrics:
                count=sum(r[m] for r in rr);rate[m+'_count']=count;rate[m+'_rate']=count/n
                rate[m+'_wilson95']=v5.v4.v3.mb.wilson(count,n)
            rate['any_alarm_count']=sum(r['any_alarm'] is not None for r in rr)
            rate['any_unique_count']=sum(r['any_unique_episode'] for r in rr)
            rate['coverage']=float(np.mean([r['coverage'] for r in rr]))
            post=[r['post_fault_coverage'] for r in rr if r['post_fault_coverage'] is not None]
            rate['post_fault_coverage']=float(np.mean(post)) if post else None
            delays=[r['first_correct_delay'] for r in rr if r['first_correct_delay'] is not None]
            rate['conditional_median_first_correct_delay']=float(np.median(delays)) if delays else None
            rate['unresolved_fraction']=float(np.mean([r['unresolved_fraction'] for r in rr]))
            rates.append(rate);groups[method]=rr
        # Same per-condition resample indices for every contrast and metric.
        ix=rng.integers(0,len(TEST_SEEDS),size=(10000,len(TEST_SEEDS)))
        for cmp in ('v5_frozen_quality','pooled_quality','max_group_quality','count_time_only'):
            for metric in ('generic_false_episode','wrong_any_episode','unique_correct'):
                delta=np.array([r[metric] for r in groups['count_quality']],int)-np.array([r[metric] for r in groups[cmp]],int)
                ci=np.quantile(delta[ix].mean(axis=1),[.025,.975]).tolist()
                pairs.append(dict(condition=c,contrast='count_quality minus '+cmp,metric=metric,
                    difference=float(delta.mean()),percentile95=ci,scope='paired by seed, exploratory, unadjusted'))
    lookup={(r['condition'],r['method']):r for r in rates};criteria={}
    for c in HEALTHY_SCREEN:
        r=lookup[c,'count_quality']
        criteria[c+'_generic_false']=r['generic_false_episode_rate']<=.10
        criteria[c+'_wrong_any']=r['wrong_any_episode_rate']<=.05
        criteria[c+'_coverage']=r['coverage']>=.90
    for c in FAULT_SCREEN:
        r=lookup[c,'count_quality']
        criteria[c+'_first_correct']=r['unique_correct_rate']>=.90
        criteria[c+'_coverage']=r['post_fault_coverage']>=.90
    doc=dict(source_hashes=sources(),calibration_sha256=v5.sha(out/'calibration.json'),criteria=criteria,
        targeted_screen_passed=all(criteria.values()),n_calibration=597,n_evaluation=len(CONDITIONS)*len(TEST_SEEDS),
        independent_test_seed_groups=len(TEST_SEEDS),results=rates,paired=pairs,
        scope='Whole-episode maximum calibration; bins use distinct timestamps, not proven effective independence; no general asynchronous/multi-fault guarantee.')
    save_new(out/'summary.json',doc)
    for name,data in (('rates.csv',rates),('paired.csv',pairs),('episode_metrics.csv',rows)):
        with (out/name).open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    print('SCREEN',doc['targeted_screen_passed'],sum(criteria.values()),len(criteria),flush=True)
    for c in CONDITIONS:
        print(c,{m:{k:lookup[c,m][k] for k in ('generic_false_episode_count','wrong_any_episode_count','unique_correct_count','coverage')} for m in ('v5_frozen_quality','pooled_quality','count_quality','count_time_only')},flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=('calibrate','evaluate','summarize'))
    p.add_argument('--out',type=Path,default=Path('results'));p.add_argument('--condition',choices=CONDITIONS);a=p.parse_args()
    if a.phase=='calibrate':calibrate(a.out)
    elif a.phase=='evaluate':evaluate(a.out,a.condition)
    else:summarize(a.out)
