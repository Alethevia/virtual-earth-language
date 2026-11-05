"""V5 bounded, causal timestamp/uncertainty experiment. SIMULATION ONLY.
Metadata is supplied instrument information, not inferred fault truth. No
hardware, safety certification, novelty, or common-mode identification claim.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import argparse, csv, hashlib, json, math, sys, time
import numpy as np
from numba import njit
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'motor_observability_v4'))
import experiment as v4
PARENT='5e5e5d54fbc8b0495848a71e2284abfae1b031d3'
CAL_SEEDS=range(33000,33199)
TEST_SEEDS=range(35000,35100)
CAL_CONDITIONS=('healthy','healthy_shift','healthy_quantized','healthy_slow_reporting',
                'healthy_witness_delay','healthy_primary_noise','healthy_high_noise','healthy_nonlinear')
CONDITIONS=('healthy','healthy_shift','bias','bias_shift','drift','stuck','stuck_noisy_readout',
 'healthy_late_shift','bias_late_shift','healthy_nonlinear','bias_nonlinear',
 'healthy_voltage_bias','healthy_current_bias','aux1_bias','aux2_bias','two_aux_common_bias','all_common_bias',
 'healthy_quantized','bias_quantized','healthy_slow_reporting','bias_slow_reporting','stuck_slow_reporting',
 'healthy_witness_delay','bias_witness_delay','healthy_primary_noise','bias_primary_noise','healthy_high_noise',
 'healthy_asynchronous','bias_asynchronous','healthy_timestamp_lie','bias_timestamp_lie',
 'healthy_noise_underreported','bias_noise_underreported','bias_quality_overreported',
 'healthy_dropout','bias_dropout','healthy_coarse_quantization','bias_coarse_quantization')
METHODS=('v4_frozen','raw_matched','window_only','time_aligned','time_quality','always_abstain')
STREAMS=('raw_short','raw_long','aligned','quality')
COLS=(0,0,1,2,3)
HISTORICAL_THRESHOLD=.49060564088478326
MAX_AGE=60
MIN_MATCHES=3

@dataclass(frozen=True)
class Packets:
    # Row t is the latest packet AVAILABLE at reception index t.
    # stamp=-1/value=NaN until the first arrival. Stamps use .01-second ticks.
    values: np.ndarray
    stamps: np.ndarray
    sigma: np.ndarray
    quantum: np.ndarray
    offset_bound: np.ndarray


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def source_hashes():return {**v4.source_hashes(),'telemetry.py':sha(__file__)}
def save_new(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n')


def generate(seed:int, condition:str):
    """Original closed-loop simulation unchanged, passive only.
    Packet transformations occur AFTER feedback tap. Only packets go to detector.
    Meta returned separately is evaluation truth, NEVER a detector input.
    """
    if condition not in CONDITIONS:raise ValueError(condition)
    profiles=('quantized','slow_reporting','witness_delay','primary_noise','asynchronous',
              'timestamp_lie','noise_underreported','quality_overreported','dropout','coarse_quantization')
    profile=next((p for p in profiles if condition.endswith('_'+p)),None)
    base=condition
    if profile is not None:
        base='stuck' if condition.startswith('stuck_') else ('bias' if condition.startswith('bias_') else 'healthy')
    y,meta,cost=v4.generate(seed,base,False)
    speeds=y[:,2:].copy();n=len(y)
    sigma=np.full(3,.25);quantum=np.zeros(3);offsets=np.array([0.,.03,.03])
    period=np.ones(3,dtype=int);delay=np.zeros(3,dtype=int);phase=np.zeros(3,dtype=int)
    if base in ('healthy_nonlinear','bias_nonlinear'):sigma[0]=.375
    if base=='healthy_high_noise':sigma[:]=.75
    if profile in ('primary_noise','noise_underreported'):
        speeds[:,0]+=np.random.default_rng(seed+5000000).normal(0,math.sqrt(.75**2-.25**2),n)
        sigma[0]=.75
    if profile in ('quantized','coarse_quantization'):quantum[0]=2. if profile=='quantized' else 16.
    if profile=='slow_reporting':period[0]=50
    if profile in ('witness_delay','timestamp_lie'):delay[1:]=10
    if profile=='asynchronous':period[:]=[5,7,11];phase[:]=[0,1,3]
    # Quantize each acquired raw value BEFORE transport/holding.
    for c in range(3):
        if quantum[c]>0:speeds[:,c]=quantum[c]*np.rint(speeds[:,c]/quantum[c])
    values=np.full((n,3),np.nan);stamps=np.full((n,3),-1,dtype=np.int64)
    for c in range(3):
        sample=phase[c]+((np.arange(n)-delay[c]-phase[c])//period[c])*period[c]
        valid=sample>=phase[c]
        if profile=='dropout' and c>0:sample=np.minimum(sample,300)
        values[valid,c]=speeds[sample[valid],c];stamps[valid,c]=sample[valid]
    # Wrong metadata are held-out negative controls, not corrected using truth.
    if profile=='timestamp_lie':
        for c in (1,2):
            valid=stamps[:,c]>=0;stamps[valid,c]=np.arange(n)[valid]
    if profile=='noise_underreported':sigma[0]=.25
    if profile=='quality_overreported':quantum[0]=20.
    meta=dict(meta,condition=condition,seed=seed,profile=profile,active=False)
    return Packets(values,stamps,sigma,quantum,offsets),meta,cost


def validate(p:Packets):
    y=np.asarray(p.values);s=np.asarray(p.stamps)
    if y.ndim!=2 or y.shape[1]!=3 or len(y)<201 or s.shape!=y.shape or not np.issubdtype(s.dtype,np.integer):
        raise ValueError('Need N>=201 by 3 values and integer acquisition stamps')
    for a in (p.sigma,p.quantum,p.offset_bound):
        if np.shape(a)!=(3,) or not np.isfinite(a).all():raise ValueError('Invalid declared quality')
    if (p.sigma<=0).any() or (p.quantum<0).any() or (p.offset_bound<0).any():raise ValueError('Invalid quality bounds')
    ok=s>=0
    if (s < -1).any() or (s>np.arange(len(s))[:,None]).any() or (np.diff(s,axis=0)<0).any():
        raise ValueError('Stamps must be causal and monotone')
    if not np.isfinite(y[ok]).all() or not np.isnan(y[~ok]).all():raise ValueError('Invalid packet validity')
    repeated=(s[1:]==s[:-1])&(s[1:]>=0)
    if (y[1:][repeated]!=y[:-1][repeated]).any():raise ValueError('Same packet stamp must retain its value')


@njit(cache=True)
def kernel(y,stamp,sigma,quantum,offsets):
    n=len(y);nt=(n-201)//20+1
    scores=np.zeros((nt,4,3));availability=np.zeros((nt,4),np.bool_)
    counts=np.zeros(nt,np.int64);ages=np.full(nt,-1.,np.float64)
    cached=np.zeros((n,3));seen=np.zeros((n,3),np.bool_)
    pairs=((0,1),(0,2),(1,2));row=0
    for t in range(n):
        for c in range(3):
            k=stamp[t,c]
            if k>=0:cached[k,c]=y[t,c];seen[k,c]=True
        if t<200 or (t-200)%20:continue
        for m in range(2):
            width=40 if m==0 else 200
            finite=True
            for k in range(t-width,t+1):
                for c in range(3):
                    if not np.isfinite(y[k,c]):finite=False
            if finite:
                availability[row,m]=True
                for j in range(3):
                    a,b=pairs[j];total=0.
                    for k in range(t-width,t+1):total+=(y[k,a]-y[k,b])**2
                    scores[row,m,j]=math.sqrt(total/(width+1))
        total=np.zeros(3);norm=np.zeros(3);count=0;latest=-1
        for k in range(t-200,t+1):
            if seen[k,0] and seen[k,1] and seen[k,2]:
                count+=1;latest=k
                for j in range(3):
                    a,b=pairs[j];d=abs(cached[k,a]-cached[k,b])
                    total[j]+=d*d
                    excess=max(0.,d-(quantum[a]+quantum[b])/2-offsets[a]-offsets[b])
                    norm[j]+=excess*excess/(sigma[a]**2+sigma[b]**2)
        counts[row]=count
        if latest>=0:ages[row]=(t-latest)*.01
        if count>=3 and t-latest<=60:
            availability[row,2]=True;availability[row,3]=True
            for j in range(3):
                scores[row,2,j]=math.sqrt(total[j]/count)
                scores[row,3,j]=math.sqrt(norm[j]/count)
        row+=1
    return scores,availability,counts,ages


def features(p:Packets):
    validate(p)
    return kernel(np.asarray(p.values,float),p.stamps,np.asarray(p.sigma,float),np.asarray(p.quantum,float),np.asarray(p.offset_bound,float))


def decisions(f,thresholds):
    scores,available,counts,age=f
    out={}
    for m,col in zip(METHODS[:-1],COLS):
        threshold=HISTORICAL_THRESHOLD if m=='v4_frozen' else thresholds[STREAMS[col]]
        cross=(scores[:,col]>threshold)&available[:,col,None]
        labels=np.full(len(scores),-1,dtype=int)
        labels[cross[:,0]&cross[:,1]&~cross[:,2]]=0
        labels[cross[:,0]&cross[:,2]&~cross[:,1]]=1
        labels[cross[:,1]&cross[:,2]&~cross[:,0]]=2
        out[m]=(labels,cross.any(axis=1),available[:,col])
    out['always_abstain']=(np.full(len(scores),-1,dtype=int),np.zeros(len(scores),bool),np.ones(len(scores),bool))
    return out


def record(times,labels,flags,available,meta):
    r=v4.episode_record(times,labels,flags,meta)
    r['coverage']=float(available.mean())
    r['insufficient_fraction']=float((~available).mean())
    return r


def calibrate(out):
    out=Path(out);tic=time.perf_counter();lock=source_hashes()
    if (out/'calibration.json').exists():raise FileExistsError('Calibration exists')
    rng=np.random.default_rng(774414);rows=[]
    for seed in CAL_SEEDS:
        condition=CAL_CONDITIONS[int(rng.integers(len(CAL_CONDITIONS)))]
        p,_,_=generate(seed,condition);s,a,_,_=features(p)
        if not a[:,2:].all():raise AssertionError('Calibration unexpectedly lacks matched data')
        rows.append(dict(seed=seed,condition=condition,maxima=s.max(axis=(0,2)).tolist()))
    maxima=np.array([r['maxima'] for r in rows])
    th={name:v4.v3.mb.calibration_threshold(maxima[:,j]) for j,name in enumerate(STREAMS)}
    doc=dict(source_hashes=lock,thresholds=th,rows=rows,n=199,rank=190,elapsed_seconds=time.perf_counter()-tic)
    save_new(out/'calibration.json',doc);print('CALIBRATED',th,flush=True)


def evaluate(out,condition):
    out=Path(out);cal=json.loads((out/'calibration.json').read_text());tic=time.perf_counter()
    assert cal['source_hashes']==source_hashes()
    if condition not in CONDITIONS or (out/f'{condition}.json').exists():raise ValueError('Invalid condition/existing output')
    rows=[];all_s=[];all_a=[];all_n=[];all_age=[];metas=[]
    for seed in TEST_SEEDS:
        p,meta,_=generate(seed,condition);f=features(p);s,a,num,age=f
        times=np.arange(200,len(p.values),20)*.01
        all_s.append(s);all_a.append(a);all_n.append(num);all_age.append(age);metas.append(meta)
        if seed==TEST_SEEDS.start:
            np.savez_compressed(out/f'{condition}_example.npz',values=p.values,stamps=p.stamps,sigma=p.sigma,quantum=p.quantum,offset_bound=p.offset_bound)
        for method,(labels,flags,avail) in decisions(f,cal['thresholds']).items():
            rows.append(dict(condition=condition,seed=seed,method=method,**record(times,labels,flags,avail,meta)))
    np.savez_compressed(out/f'{condition}_features.npz',scores=np.array(all_s),available=np.array(all_a),counts=np.array(all_n),ages=np.array(all_age),times=times)
    save_new(out/f'{condition}.json',dict(source_hashes=source_hashes(),calibration_sha256=sha(out/'calibration.json'),metadata=metas,rows=rows,elapsed_seconds=time.perf_counter()-tic))
    print('EVALUATED',condition,'seconds',round(time.perf_counter()-tic,3),flush=True)


def summarize(out):
    out=Path(out);rows=[];cal=json.loads((out/'calibration.json').read_text())
    for c in CONDITIONS:
        d=json.loads((out/f'{c}.json').read_text())
        assert d['source_hashes']==source_hashes() and d['calibration_sha256']==sha(out/'calibration.json')
        rows.extend(d['rows'])
    rates=[];paired=[];rng=np.random.default_rng(44994)
    for c in CONDITIONS:
        groups={}
        for m in METHODS:
            r=sorted([x for x in rows if x['condition']==c and x['method']==m],key=lambda x:x['seed'])
            assert [x['seed'] for x in r]==list(TEST_SEEDS)
            n=len(r);count=sum(x['primary_event'] for x in r);delay=[x['primary_delay'] for x in r if x['primary_delay'] is not None]
            rates.append(dict(condition=c,method=m,n=n,count=count,rate=count/n,wilson95=v4.v3.mb.wilson(count,n),
                early=sum(x['primary_early'] for x in r),unique_correct=sum(x['unique_correct'] for x in r),
                any_alarm_count=sum(x['any_alarm'] is not None for x in r),anomaly_valid=sum(x['anomaly_valid'] for x in r),
                coverage=float(np.mean([x['coverage'] for x in r])),unresolved_fraction=float(np.mean([x['unresolved_fraction'] for x in r])),
                conditional_median_delay=None if not delay else float(np.median(delay))))
            groups[m]=np.array([x['primary_event'] for x in r],int)
        for cmp in ('v4_frozen','raw_matched','time_aligned'):
            diff=groups['time_quality']-groups[cmp]
            boot=diff[rng.integers(0,100,size=(10000,100))].mean(axis=1)
            paired.append(dict(condition=c,contrast='time_quality minus '+cmp,difference=float(diff.mean()),ci95=np.quantile(boot,[.025,.975]).tolist(),scope='seed-paired, exploratory, unadjusted'))
    look={(r['condition'],r['method']):r for r in rates};tests={}
    for c in CAL_CONDITIONS:
        tests[c+'_false_primary']=look[c,'time_quality']['rate']<=.1
        tests[c+'_coverage']=look[c,'time_quality']['coverage']>=.9
    faults=('bias','bias_shift','bias_late_shift','drift','stuck','stuck_noisy_readout','bias_quantized','bias_slow_reporting','stuck_slow_reporting','bias_witness_delay','bias_primary_noise')
    for c in faults:tests[c+'_detection']=look[c,'time_quality']['rate']>=.9
    for c in ('aux1_bias','aux2_bias'):tests[c+'_correct_isolation']=look[c,'time_quality']['unique_correct']>=90
    doc=dict(source_hashes=source_hashes(),calibration_sha256=sha(out/'calibration.json'),criteria=tests,targeted_screen_passed=all(tests.values()),
        n_calibration=199,n_evaluation=len(CONDITIONS)*100,independent_evaluation_seed_groups=100,results=rates,paired=paired,
        scope='Simulation; unchanged three-speed measurement budget; supplied quality/timestamp metadata is extra prior information. Exact timestamp matching, no interpolation. Not general robustness.')
    save_new(out/'summary.json',doc)
    for name,data in (('episode_metrics.csv',rows),('rates.csv',rates),('paired.csv',paired)):
        with (out/name).open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    for c in CONDITIONS:print(c,{m:look[c,m]['count'] for m in METHODS[:-1]},'coverage',look[c,'time_quality']['coverage'])
    print('SCREEN',doc['targeted_screen_passed'],tests)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=('calibrate','evaluate','summarize'))
    p.add_argument('--out',type=Path,default=Path('results'));p.add_argument('--condition',choices=CONDITIONS);a=p.parse_args()
    if a.phase=='calibrate':calibrate(a.out)
    elif a.phase=='evaluate':evaluate(a.out,a.condition)
    else:summarize(a.out)
