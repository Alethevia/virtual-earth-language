"""Separately implemented V7 postprocessing. No horizon.record/decisions calls.
Full decisions/records/rates/intervals and representative raw packets checked.
Same-author verification, not third-party certification.
"""
import csv,json,math,sys
from pathlib import Path
import numpy as np

METHODS=('v6_count','v6_universal','new_short_universal','new_long_universal','always_abstain')
PROFILES=('dense_iid','sparse_iid','dense_ar','sparse_ar')

def wilson(k,n):
    z=1.959963984540054;p=k/n;c=(p+z*z/(2*n))/(1+z*z/n)
    w=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return [max(0.,c-w),min(1.,c+w)]

def ref_record(case,label,flag,horizon):
    time=np.arange(len(label))*.2+2.;sel=time<horizon;time=time[sel];label=label[sel];flag=flag[sel]
    # Integer ticks avoid floating endpoints and match the actual decision clock.
    time=np.arange(200,200+20*len(time),20)*.01
    onset=case['onset'];fault=onset is not None
    unique=np.where(label>=0)[0];alarm=np.where(flag)[0]
    t1=None if len(unique)==0 else float(time[unique[0]])
    who=None if len(unique)==0 else int(label[unique[0]])
    ta=None if len(alarm)==0 else float(time[alarm[0]])
    correct=bool(fault and t1 is not None and t1>=onset and who==0)
    delay=t1-onset if correct else None
    wrong=(label>=0) if not fault else ((label>=0)&((label!=0)|(time<onset)))
    false=flag if not fault else (flag&(time<onset))
    epochs=((time-2)//18).astype(int)
    # Use floor explicitly (same mathematical definition, no detector code).
    epochs=np.floor((time-2)/18).astype(int)
    bad=len(set(epochs[np.where(flag)[0]].tolist()))
    return dict(generic_alarm=bool(flag.any()),generic_false=bool(false.any()),wrong_any=bool(wrong.any()),
        first_unique=t1,first_label=who,first_generic=ta,first_correct=correct,first_correct_delay=delay,
        within_5s=bool(correct and delay<=5),within_30s=bool(correct and delay<=30),
        eventual_correct=bool(fault and ((label==0)&(time>=onset)).any()),coverage=1.,
        post_fault_coverage=1. if fault else None,pre_fault_unique=bool(fault and ((label>=0)&(time<onset)).any()),
        unresolved_fraction=float(np.mean(flag&(label<0))),flagged_decisions=int(flag.sum()),
        alarm_bursts=int(len(alarm)-sum(np.diff(alarm)==1)),flagged_epoch_count=bad,
        epochs_observed=len(set(epochs.tolist())),restricted_delay_30s=min(30.,delay) if correct else 30.)

def eq(a,b):
    if isinstance(a,(float,int)) and isinstance(b,(float,int)):return math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-10)
    return a==b

def verify_packets(p,cal):
    z=np.load(p);y=z['values'];stamp=z['stamps'];sigma=z['sigma'];off=z['offset_bound'];n=len(y)
    cache=np.zeros_like(y);arrival=np.full(y.shape,n+1,int)
    for c in range(3):
        keys,idx=np.unique(stamp[:,c],return_index=True)
        cache[keys,c]=y[idx,c];arrival[keys,c]=idx
    times=z['times'];expected=z['scores'];mx=0.
    ref=np.zeros_like(expected)
    for row,t in enumerate(np.rint(times*100).astype(int)):
        ix=np.arange(t-200,t+1);ix=ix[np.all(arrival[ix]<=t,axis=1)]
        assert len(ix)>=3 and t-ix[-1]<=60
        for j,(a,b) in enumerate(((0,1),(0,2),(1,2))):
            for col,width in ((0,40),(1,200)):
                d=y[t-width:t+1,a]-y[t-width:t+1,b];ref[row,col,j]=np.sqrt(np.dot(d,d)/(width+1))
            d=cache[ix,a]-cache[ix,b];ref[row,2,j]=np.sqrt(np.mean(d*d))
            excess=np.maximum(0,np.abs(d)-off[a]-off[b]);ref[row,3,j]=np.sqrt(np.mean(excess*excess)/(sigma[a]**2+sigma[b]**2))
    mx=float(np.max(np.abs(ref-expected)));assert mx<1e-9,(p.name,mx)
    threshold=(2.0307216952958402 if 'sparse' in p.name else 1.275003768049613,
               2.0307216952958402,cal['thresholds']['short'],cal['thresholds']['long'])
    for j,th in enumerate(threshold):
        c=ref[:,3]>th;labels=np.full(len(times),-1,int)
        for k,(a,b,other) in enumerate(((0,1,2),(0,2,1),(1,2,0))):labels[c[:,a]&c[:,b]&~c[:,other]]=k
        np.testing.assert_array_equal(labels,z['labels'][j]);np.testing.assert_array_equal(c.any(axis=1),z['flags'][j])
    return mx

def main(root):
    root=Path(root);cal=json.loads((root/'calibration.json').read_text());summary=json.loads((root/'summary.json').read_text())
    from hashlib import sha256
    assert summary['calibration_sha256']==sha256((root/'calibration.json').read_bytes()).hexdigest()
    checked_thresholds=0
    for p in PROFILES:
        for name in ('short','long'):
            vals=sorted(r[name] for r in cal['rows'] if r['profile']==p)
            assert len(vals)==199 and eq(vals[189],cal['groups'][p][name]);checked_thresholds+=1
    for name in ('short','long'):
        assert eq(max(cal['groups'][p][name] for p in PROFILES),cal['thresholds'][name]);checked_thresholds+=1
    records=[];checked=0;case_count=0
    for profile in PROFILES:
        for path in sorted(root.glob(profile+'_*.json')):
            doc=json.loads(path.read_text());arrays=np.load(path.with_name(path.stem+'_decisions.npz'))
            labels=arrays['labels'];flags=arrays['flags'];lookup={}
            for r in doc['records']:
                lookup[(r['seed'],r['mode'],r['amplitude'],r['horizon'],r['method'])]=r
            for ix,case in enumerate(doc['cases']):
                case_count+=1;steps=80 if case['end']==18 else 2990
                for end in ((18.,180.,600.) if case['mode']=='healthy' else (case['end'],)):
                    for j,method in enumerate(METHODS):
                        want=ref_record(case,labels[ix,j,:steps],flags[ix,j,:steps],end)
                        actual=lookup[case['seed'],case['mode'],case['amplitude'],end,method]
                        for key,value in want.items():assert eq(value,actual[key]),(path.name,case,key,value,actual[key])
                        records.append(actual);checked+=1
    groups={}
    for r in records:
        key=tuple(r[k] for k in ('profile','mode','amplitude','horizon','method'));groups.setdefault(key,[]).append(r)
    for rr in groups.values():rr.sort(key=lambda r:r['seed']);assert [r['seed'] for r in rr]==list(range(50000,50200))
    n_wilson=0
    for rate in summary['results']:
        key=tuple(rate[k] for k in ('profile','mode','amplitude','horizon','method'));rr=groups[key]
        for metric in ('generic_alarm','generic_false','wrong_any','first_correct','within_5s','within_30s','eventual_correct','pre_fault_unique'):
            k=sum(r[metric] for r in rr);assert k==rate[metric+'_count'];np.testing.assert_allclose(wilson(k,len(rr)),rate[metric+'_wilson95'],rtol=1e-12);n_wilson+=1
        ds=[r['first_correct_delay'] for r in rr if r['first_correct']]
        assert eq(float(np.median(ds)) if ds else None,rate['conditional_median_delay'])
        assert eq(float(np.mean([r['restricted_delay_30s'] for r in rr])),rate['mean_restricted_delay_30s'])
    rng=np.random.default_rng(44997);j=0
    for key in sorted(set(k[:-1] for k in groups)):
        idx=rng.integers(0,200,size=(5000,200))
        for cmp in ('v6_count','v6_universal','new_short_universal'):
            for metric in ('generic_false','wrong_any','within_5s','first_correct'):
                a=np.array([r[metric] for r in groups[key+('new_long_universal',)]],int)
                b=np.array([r[metric] for r in groups[key+(cmp,)]],int);diff=a-b
                got=summary['paired'][j];np.testing.assert_allclose(np.quantile(diff[idx].mean(axis=1),[.025,.975]),got['percentile95'],atol=1e-12)
                assert eq(float(diff.mean()),got['difference']);j+=1
    mx=0.;examples=sorted(root.glob('example_*.npz'))
    for path in examples:mx=max(mx,verify_packets(path,cal))
    result=dict(calibration_values=checked_thresholds,scenario_cases=case_count,records=checked,cells=len(groups),
        wilson_intervals=n_wilson,paired_intervals=j,full_packet_examples=len(examples),direct_score_max_abs_difference=mx,
        scope='Separately coded same-author postprocessing; not independent human certification.')
    with (root/'verification.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main(sys.argv[1])
