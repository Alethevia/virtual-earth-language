"""V4: information-budget intervention and failure-attribution audit.
Simulation only. Added witnesses are measurements, NOT oracle inputs to detectors.
No novelty, safety, hardware validation, or equal-information superiority claim.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, math, platform, sys, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'motor_consistency_v3'))
import study as v3

EXTRA = ('stuck_noisy_readout','aux1_bias','aux2_bias','two_aux_common_bias',
         'all_common_bias','healthy_quantized','healthy_slow_reporting',
         'healthy_witness_delay','healthy_high_noise')
CONDITIONS = v3.CONDITIONS + EXTRA
METHODS = ('v3_forced_primary','flatline','dual_forced_primary','triple_consensus',
           'dual_unlocalized','v3_unlocalized','always_abstain')
CAL_SEEDS = range(26000,26199)
TEST_SEEDS = range(28000,28100)
PARENT_SHA = '57768d20b2bcd161fac90fcddc3b191c257a6d14'
EXPECTED_PARENT = {
 'motorbench.py':'caea2a328becfff82cf915511b157c76b7dd01ca43a2c884e1f2804c566a4834',
 'bank_study.py':'e6aa4ccba89aa53c20f9586331344093301947c6c8e59edcde20ca3ab7bf6f1d',
 'study.py':'419240774aabbd96d84a60ad72d91567ab55c1ffa4dc33fed6128ff6b246b0ca',
 'box_solver.py':'e0f4cf9863787a905e02a0c79f84d090f50d020f0d6cb116811416b84bf62b7d'}


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_hashes() -> dict:
    parent = v3.source_hashes()
    if parent != EXPECTED_PARENT:
        raise RuntimeError('Parent implementation changed')
    return {**parent, 'experiment.py':sha(Path(__file__))}


def save_new(path: Path, obj: dict) -> None:
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:
        json.dump(obj,f,indent=2,allow_nan=False); f.write('\n')


def generate(seed: int, condition: str, active: bool):
    """Simulator uses true speed ONLY to generate independent witness observations.
    Added channels never affect the PI controller. New telemetry stresses act
    AFTER the original controller sensor tap, explicitly unlike physical feedback faults.
    """
    if condition not in CONDITIONS:
        raise ValueError(condition)
    base = condition if condition in v3.CONDITIONS else ('stuck' if condition=='stuck_noisy_readout' else 'healthy')
    tr, onset, reference = v3.simulate(seed,base,active)
    rng=np.random.default_rng(seed+3000000)
    offsets=rng.uniform(-.03,.03,2)
    signs=int(rng.choice([-1,1])); late=float(rng.uniform(10,13))
    noise=rng.normal(size=(len(tr),2))
    witness_sd=.75 if condition=='healthy_high_noise' else .25
    witnesses=tr[:,3,None]+offsets+witness_sd*noise
    measured=np.c_[tr[:,5],tr[:,7],tr[:,6],witnesses]
    primary_onset=onset
    target=0 if onset is not None else None
    anomaly_onset=onset
    if condition in ('healthy_voltage_bias','healthy_current_bias'):
        extra=np.random.default_rng(seed+1000000);extra.uniform(6,9)
        anomaly_onset=float(extra.uniform(10,13))
    if condition=='stuck_noisy_readout':
        eps=np.random.default_rng(seed+4000000).normal(0,.25,len(tr))
        measured[1000:,2]+=eps[1000:]
    elif condition in ('aux1_bias','aux2_bias','two_aux_common_bias'):
        cols=[3] if condition=='aux1_bias' else ([4] if condition=='aux2_bias' else [3,4])
        for col in cols:measured[tr[:,0]>=late,col]+=signs*6
        anomaly_onset=late
        target=1 if condition=='aux1_bias' else (2 if condition=='aux2_bias' else None)
    elif condition=='all_common_bias':
        measured[tr[:,0]>=late,2:]+=signs*6
        primary_onset=late;anomaly_onset=late;target=None
    elif condition=='healthy_quantized':
        measured[:,2]=2*np.rint(measured[:,2]/2)
    elif condition=='healthy_slow_reporting':
        measured[:,2]=measured[(np.arange(len(tr))//50)*50,2]
    elif condition=='healthy_witness_delay':
        measured[:,3:]=measured[np.maximum(0,np.arange(len(tr))-10),3:]
    elif condition=='healthy_high_noise':
        measured[:,2]+=np.random.default_rng(seed+4000000).normal(0,math.sqrt(.75**2-.25**2),len(tr))
    metadata=dict(primary_onset=primary_onset,anomaly_onset=anomaly_onset,single_target=target,
                  condition=condition,seed=seed,active=active)
    costs=dict(tracking_rmse_base=float(np.sqrt(np.mean((tr[:,3]-reference)**2))),
               input_energy_j=float(.01*np.sum(tr[:,5]*tr[:,4])),
               energy_is_actual=condition!='healthy_voltage_bias',
               saturation_fraction=float(np.mean(np.abs(tr[:,5])>=12)))
    return measured,metadata,costs


def pair_features(speeds: np.ndarray):
    """Causal .4-second RMS pair differences and exact-flatline negative control."""
    speeds=np.asarray(speeds,float)
    if speeds.ndim!=2 or speeds.shape[1]!=3 or len(speeds)<201 or not np.isfinite(speeds).all():
        raise ValueError('Expected finite N>=201 by 3 speed observations')
    ticks=np.arange(200,len(speeds),20,dtype=int)
    pairs=((0,1),(0,2),(1,2))
    sq=np.column_stack([(speeds[:,a]-speeds[:,b])**2 for a,b in pairs])
    cs=np.vstack([np.zeros(3),np.cumsum(sq,axis=0)])
    d=np.sqrt(np.maximum(0,(cs[ticks+1]-cs[ticks-40])/41))
    flat=np.array([np.ptp(speeds[t-40:t+1,0])==0 for t in ticks],bool)
    return ticks*.01,d,flat


def features(measured: np.ndarray):
    y=np.asarray(measured,float)
    if y.ndim!=2 or y.shape[1]!=5 or len(y)<201 or not np.isfinite(y).all():
        raise ValueError('Expected [voltage,current,primary_speed,witness1,witness2] only')
    times,pairs,flat=pair_features(y[:,2:])
    raw,old=v3.diagnose(y[:,:3])
    np.testing.assert_allclose(times,raw[:,0],atol=1e-12)
    return times,np.c_[old[:,4],pairs,flat.astype(float)]


def decisions(feat: np.ndarray, thresholds: dict):
    """Return channel=-1 (no unique isolation) or 0/1/2, plus any-anomaly flags.
    v3_forced_primary is explicitly a FORCED interpretation of a conditional
    old score, not a claim that V3 proved unique causal identifiability.
    """
    x=np.asarray(feat,float)
    old=x[:,0]>thresholds['v3'];d=x[:,1:4];flat=x[:,4]>0
    dual=d[:,0]>thresholds['dual'];cross=d>thresholds['triple']
    isolation=np.full(len(x),-1,int)
    isolation[cross[:,0]&cross[:,1]&~cross[:,2]]=0
    isolation[cross[:,0]&cross[:,2]&~cross[:,1]]=1
    isolation[cross[:,1]&cross[:,2]&~cross[:,0]]=2
    out={}
    for method,hit in (('v3_forced_primary',old),('flatline',flat),('dual_forced_primary',dual)):
        out[method]=(np.where(hit,0,-1),hit.copy())
    out['triple_consensus']=(isolation,cross.any(axis=1))
    out['dual_unlocalized']=(np.full(len(x),-1,int),dual)
    out['v3_unlocalized']=(np.full(len(x),-1,int),old)
    out['always_abstain']=(np.full(len(x),-1,int),np.zeros(len(x),bool))
    return out


def calibration(out: Path):
    out=Path(out);lock=source_hashes();rng=np.random.default_rng(774413)
    assignments=['healthy_shift' if rng.random()<.5 else 'healthy' for _ in CAL_SEEDS]
    rows=[];tic=time.perf_counter()
    for mode in ('passive','active'):
        for seed,condition in zip(CAL_SEEDS,assignments):
            y,_,_=generate(seed,condition,mode=='active');_,f=features(y)
            rows.append(dict(mode=mode,seed=seed,condition=condition,
                             maxima=[float(f[:,0].max()),float(f[:,1].max()),float(f[:,1:4].max())]))
    thresholds={}
    for mode in ('passive','active'):
        a=np.array([r['maxima'] for r in rows if r['mode']==mode])
        thresholds[mode]={name:v3.mb.calibration_threshold(a[:,j]) for j,name in enumerate(('v3','dual','triple'))}
    result=dict(source_hashes=lock,rank=190,n_seed_groups=199,n_trajectories=398,
                thresholds=thresholds,rows=rows,elapsed_seconds=time.perf_counter()-tic)
    save_new(out/'calibration.json',result)
    print('CALIBRATED',thresholds,'seconds',result['elapsed_seconds'],flush=True)


def first_time(times: np.ndarray, mask: np.ndarray):
    ix=np.flatnonzero(mask)
    return None if not len(ix) else float(times[ix[0]])


def episode_record(times, assignment, any_alarm, meta):
    onset=meta['primary_onset'];anomaly_onset=meta['anomaly_onset'];target=meta['single_target']
    primary=first_time(times,assignment==0)
    any_first=first_time(times,any_alarm)
    unique=first_time(times,assignment>=0)
    unique_index=None if unique is None else int(assignment[np.flatnonzero(assignment>=0)[0]])
    valid=bool(onset is not None and primary is not None and primary>=onset)
    early=bool(onset is not None and primary is not None and primary<onset)
    unique_correct=bool(target is not None and unique is not None and anomaly_onset is not None
                        and unique>=anomaly_onset and unique_index==target)
    anomaly_valid=bool(anomaly_onset is not None and any_first is not None and any_first>=anomaly_onset)
    return dict(primary_fault=onset is not None,primary_alarm=primary,primary_valid=valid,
                primary_event=valid if onset is not None else primary is not None,
                primary_early=early,primary_delay=primary-onset if valid else None,
                any_alarm=any_first,anomaly_valid=anomaly_valid,
                any_unique=unique,isolated_channel=unique_index,unique_correct=unique_correct,
                unresolved_fraction=float(np.mean(any_alarm&(assignment<0))))


def evaluate(out: Path,condition: str):
    out=Path(out);cal=json.loads((out/'calibration.json').read_text())
    assert source_hashes()==cal['source_hashes']
    if condition not in CONDITIONS or (out/f'{condition}.json').exists():
        raise ValueError('Unknown condition or existing output')
    rows=[];meta_saved=[];all_features=[];costs=[];examples=[];tic=time.perf_counter()
    for mode in ('passive','active'):
        for seed in TEST_SEEDS:
            y,meta,cost=generate(seed,condition,mode=='active');times,f=features(y)
            all_features.append(f);meta_saved.append(meta);costs.append(dict(mode=mode,seed=seed,**cost))
            if seed==TEST_SEEDS.start:examples.append(y)
            for method,(labels,flags) in decisions(f,cal['thresholds'][mode]).items():
                rows.append(dict(condition=condition,mode=mode,seed=seed,method=method,
                                 **episode_record(times,labels,flags,meta)))
    np.savez_compressed(out/f'{condition}_features.npz',features=np.array(all_features),times=times,
                        example_measurements=np.array(examples))
    result=dict(source_hashes=source_hashes(),calibration_sha256=sha(out/'calibration.json'),
                condition=condition,metadata=meta_saved,costs=costs,rows=rows,
                elapsed_seconds=time.perf_counter()-tic)
    save_new(out/f'{condition}.json',result)
    print('EVALUATED',condition,'seconds',result['elapsed_seconds'],flush=True)


def summarize(out: Path):
    out=Path(out);rows=[];costs=[];cal=json.loads((out/'calibration.json').read_text())
    for condition in CONDITIONS:
        d=json.loads((out/f'{condition}.json').read_text())
        assert d['source_hashes']==source_hashes() and d['calibration_sha256']==sha(out/'calibration.json')
        rows.extend(d['rows']);costs.extend([dict(condition=condition,**r) for r in d['costs']])
    rates=[];paired=[];rng=np.random.default_rng(44993)
    for condition in CONDITIONS:
        grouped={}
        for mode in ('passive','active'):
            for method in METHODS:
                rr=sorted([r for r in rows if (r['condition'],r['mode'],r['method'])==(condition,mode,method)],key=lambda r:r['seed'])
                assert [r['seed'] for r in rr]==list(TEST_SEEDS)
                n=len(rr);count=sum(r['primary_event'] for r in rr)
                delays=[r['primary_delay'] for r in rr if r['primary_delay'] is not None]
                rates.append(dict(condition=condition,mode=mode,method=method,n=n,count=count,rate=count/n,
                    wilson95=v3.mb.wilson(count,n),primary_early=sum(r['primary_early'] for r in rr),
                    unique_correct=sum(r['unique_correct'] for r in rr),anomaly_valid=sum(r['anomaly_valid'] for r in rr),
                    any_alarm_count=sum(r['any_alarm'] is not None for r in rr),
                    conditional_median_delay=None if not delays else float(np.median(delays)),
                    mean_unresolved_fraction=float(np.mean([r['unresolved_fraction'] for r in rr]))))
                grouped[mode,method]=np.array([r['primary_event'] for r in rr],int)
        for mode in ('passive','active'):
            diff=grouped[mode,'triple_consensus']-grouped[mode,'v3_forced_primary']
            boot=diff[rng.integers(0,len(diff),size=(10000,len(diff)))].mean(axis=1)
            paired.append(dict(condition=condition,mode=mode,contrast='triple minus forced-V3, different information budgets',
                               difference=float(diff.mean()),ci95=np.quantile(boot,[.025,.975]).tolist()))
    look={(r['condition'],r['mode'],r['method']):r for r in rates}
    healthy=('healthy','healthy_shift','healthy_late_shift','healthy_voltage_bias','healthy_current_bias','aux1_bias','aux2_bias')
    faults=('bias','bias_shift','bias_late_shift','drift','stuck','stuck_noisy_readout')
    criteria={}
    for mode in ('passive','active'):
        tests={**{c+'_false_primary':look[c,mode,'triple_consensus']['rate']<=.1 for c in healthy},
               **{c+'_primary_detection':look[c,mode,'triple_consensus']['rate']>=.9 for c in faults},
               **{c+'_correct_aux_isolation':look[c,mode,'triple_consensus']['unique_correct']>=90 for c in ('aux1_bias','aux2_bias')}}
        criteria[mode]=dict(criteria=tests,single_fault_screen_passed=all(tests.values()))
    doc=dict(parent_commit=PARENT_SHA,source_hashes=source_hashes(),calibration_sha256=sha(out/'calibration.json'),
             n_calibration_trajectories=398,n_evaluation_trajectories=len(CONDITIONS)*len(TEST_SEEDS)*2,
             independent_test_seed_groups=len(TEST_SEEDS),criteria=criteria,results=rates,paired=paired,
             evidence_scope='Simulation-only; extra measurements change information budget; common-mode/timing/noise stresses retained.')
    save_new(out/'summary.json',doc)
    for name,data in (('episode_metrics.csv',rows),('rates.csv',rates),('paired.csv',paired),('costs.csv',costs)):
        with (out/name).open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    for c in CONDITIONS:
        print(c,{mode:{m:look[c,mode,m]['count'] for m in ('v3_forced_primary','flatline','dual_forced_primary','triple_consensus')} for mode in ('passive','active')})
    print('SCREENS',criteria)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('calibrate','evaluate','summarize'))
    parser.add_argument('--out',type=Path,default=Path('results/run'))
    parser.add_argument('--condition',choices=CONDITIONS)
    args=parser.parse_args()
    if args.phase=='calibrate':calibration(args.out)
    elif args.phase=='evaluate':evaluate(args.out,args.condition)
    else:summarize(args.out)
