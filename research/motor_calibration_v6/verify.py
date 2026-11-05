"""Separate V6 postprocessor: no calls to experiment decisions/record/summarize.
Checks full saved arrays/records; representative packet paths are reconstructed
with Python dictionaries and set intersections, not the compiled parent kernel.
"""
import argparse,json,math,hashlib
from pathlib import Path
import numpy as np

METHODS=('v5_frozen_quality','pooled_quality','count_quality','max_group_quality','count_time_only','always_abstain')
METRICS=('primary_event','unique_correct','wrong_any_episode','generic_false_episode','anomaly_valid','any_correct_after_onset')


def same(a,b):
    if a is None or b is None:return a is b
    if isinstance(a,(int,float,bool,np.number)):return math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-12)
    return a==b


def wilson(k,n):
    z=1.959963984540054
    denominator=n+z*z
    mid=(k+z*z/2)/denominator
    half=z/denominator*math.sqrt(k*(n-k)/n+z*z/4)
    return [max(0.,mid-half),min(1.,mid+half)]


def rebuild_scores(packet):
    y=packet['values'];stamp=packet['stamps'];sigma=packet['sigma'];q=packet['quantum'];b=packet['offset_bound']
    cache=[{}, {}, {}];times=[];aligned=[];normalized=[];counts=[];ages=[];oks=[]
    for t in range(len(y)):
        for j in range(3):
            k=int(stamp[t,j])
            if k>=0:cache[j][k]=float(y[t,j])
        if t<200 or (t-200)%20:continue
        common=sorted(k for k in (cache[0].keys() & cache[1].keys() & cache[2].keys()) if t-200<=k<=t)
        count=len(common);age=(t-common[-1])*.01 if common else -1.
        ok=count>=3 and age<=.60000000001
        av=[];nv=[]
        for j,k in ((0,1),(0,2),(1,2)):
            if ok:
                d=np.array([cache[j][v]-cache[k][v] for v in common])
                av.append(float(np.sqrt(np.mean(d*d))))
                r=np.maximum(0,np.abs(d)-(q[j]+q[k])/2-b[j]-b[k])
                nv.append(float(np.sqrt(np.mean(r*r)/(sigma[j]**2+sigma[k]**2))))
            else:av.append(0.);nv.append(0.)
        times.append(t*.01);aligned.append(av);normalized.append(nv);counts.append(count);ages.append(age);oks.append(ok)
    return np.array(aligned),np.array(normalized),np.array(counts),np.array(ages),np.array(oks)


def rebuild_record(feature,episode,method,meta,th):
    n=feature['counts'][episode];a=feature['available'][episode,:,3] & (n>=3)
    group=np.where(n<=5,0,np.where(n<=25,1,2))
    scores=feature['scores'][episode];times=feature['times']
    if method=='always_abstain':cross=np.zeros((len(n),3),bool)
    else:
        col=2 if method=='count_time_only' else 3
        if method=='v5_frozen_quality':threshold=np.full(len(n),1.694663815648237)
        elif method in ('pooled_quality','max_group_quality'):threshold=np.full(len(n),th[method])
        else:threshold=np.array(th[method])[group]
        cross=(scores[:,col,:]>threshold[:,None])&a[:,None]
    labels=np.full(len(n),-1,int)
    # Independent adjacency pattern: each uniquely isolated node has degree two,
    # and the opposite edge is absent.
    patterns={(True,True,False):0,(True,False,True):1,(False,True,True):2}
    for t,edges in enumerate(cross):labels[t]=patterns.get(tuple(edges),-1)
    flags=np.any(cross,axis=1)
    def first(mask):
        ix=np.nonzero(mask)[0]
        return None if len(ix)==0 else float(times[ix[0]])
    primary=first(labels==0);generic=first(flags);unique=first(labels>=0)
    first_channel=None if unique is None else int(labels[np.nonzero(labels>=0)[0][0]])
    onset=meta['primary_onset'];anomaly=meta['anomaly_onset'];target=meta['single_target']
    valid=onset is not None and primary is not None and primary>=onset
    early=onset is not None and primary is not None and primary<onset
    correct=target is not None and unique is not None and anomaly is not None and unique>=anomaly and first_channel==target
    wrong=(labels>=0) if target is None else ((labels>=0)&((times<anomaly)|(labels!=target)))
    r=dict(primary_fault=onset is not None,primary_alarm=primary,primary_valid=bool(valid),
      primary_event=bool(valid) if onset is not None else primary is not None,primary_early=bool(early),
      primary_delay=primary-onset if valid else None,any_alarm=generic,
      anomaly_valid=bool(anomaly is not None and generic is not None and generic>=anomaly),
      any_unique=unique,isolated_channel=first_channel,unique_correct=bool(correct),
      unresolved_fraction=float(np.mean(flags&(labels<0))),coverage=float(np.mean(a)),insufficient_fraction=float(np.mean(~a)),
      wrong_any_episode=bool(np.any(wrong)),any_unique_episode=unique is not None,
      generic_false_episode=bool(np.any(flags)) if anomaly is None else bool(np.any(flags&(times<anomaly))),
      first_correct_delay=unique-anomaly if correct else None,
      any_correct_after_onset=bool(target is not None and np.any((labels==target)&(times>=anomaly))) if anomaly is not None else False,
      post_fault_coverage=float(np.mean(a[times>=anomaly])) if anomaly is not None and np.any(times>=anomaly) else None)
    return r


def verify(out):
    out=Path(out);cal=json.loads((out/'calibration.json').read_text());summary=json.loads((out/'summary.json').read_text())
    rows=cal['rows'];th=cal['thresholds']
    def qt(xs):return sorted(xs)[math.ceil((len(xs)+1)*.95)-1]
    want_p=qt([r['quality_max'] for r in rows]);assert same(want_p,th['pooled_quality'])
    for g in range(3):
        r=[x for x in rows if x['group']==g];assert len(r)==199
        assert same(qt([x['quality_max'] for x in r]),th['count_quality'][g])
        assert same(qt([x['aligned_max'] for x in r]),th['count_time_only'][g])
    assert same(max(th['count_quality']),th['max_group_quality'])
    conditions=list(dict.fromkeys(r['condition'] for r in summary['results']))
    ratelook={(r['condition'],r['method']):r for r in summary['results']}
    pairlook={(r['condition'],r['contrast'],r['metric']):r for r in summary['paired']}
    max_error=0.;checked=0;ci_checked=0;wilson_checked=0;rng=np.random.default_rng(44996)
    for condition in conditions:
        d=json.loads((out/f'{condition}.json').read_text())
        assert d['source_hashes']==cal['source_hashes']==summary['source_hashes']
        assert d['calibration_sha256']==hashlib.sha256((out/'calibration.json').read_bytes()).hexdigest()
        stored={(r['seed'],r['method']):r for r in d['rows']}
        with np.load(out/f'{condition}_features.npz') as z:feature={k:z[k] for k in z.files}
        with np.load(out/f'{condition}_example.npz') as z:packet={k:z[k] for k in z.files}
        al,qu,n,age,ok=rebuild_scores(packet)
        np.testing.assert_array_equal(n,feature['counts'][0]);np.testing.assert_array_equal(ok,feature['available'][0,:,3])
        np.testing.assert_allclose(age,feature['ages'][0],rtol=0,atol=1e-12)
        for col,ref in ((2,al),(3,qu)):
            error=float(np.max(np.abs(ref-feature['scores'][0,:,col])))
            max_error=max(max_error,error);assert error<1e-10
        groups={}
        for method in METHODS:
            rr=[]
            for i,meta in enumerate(d['metadata']):
                r=rebuild_record(feature,i,method,meta,th);original=stored[meta['seed'],method]
                for k,v in r.items():assert same(v,original[k]),(condition,method,i,k,v,original[k])
                rr.append(r);checked+=1
            rate=ratelook[condition,method]
            for metric in METRICS:
                count=sum(r[metric] for r in rr)
                assert count==rate[metric+'_count'];assert same(count/len(rr),rate[metric+'_rate'])
                np.testing.assert_allclose(wilson(count,len(rr)),rate[metric+'_wilson95'],atol=1e-12)
                wilson_checked+=1
            assert sum(r['any_alarm'] is not None for r in rr)==rate['any_alarm_count']
            assert sum(r['any_unique_episode'] for r in rr)==rate['any_unique_count']
            assert same(np.mean([r['coverage'] for r in rr]),rate['coverage'])
            delay=[r['first_correct_delay'] for r in rr if r['first_correct_delay'] is not None]
            assert same(float(np.median(delay)) if delay else None,rate['conditional_median_first_correct_delay'])
            post=[r['post_fault_coverage'] for r in rr if r['post_fault_coverage'] is not None]
            assert same(float(np.mean(post)) if post else None,rate['post_fault_coverage'])
            groups[method]=rr
        indices=rng.integers(0,200,size=(10000,200))
        for cmp in ('v5_frozen_quality','pooled_quality','max_group_quality','count_time_only'):
            for metric in ('generic_false_episode','wrong_any_episode','unique_correct'):
                contrast='count_quality minus '+cmp
                dlt=np.array([int(a[metric])-int(b[metric]) for a,b in zip(groups['count_quality'],groups[cmp])])
                # Exact shortcut for degenerate paired differences; consumes same RNG indices.
                boot=dlt[indices].mean(axis=1) if np.ptp(dlt)>0 else np.repeat(dlt[0],10000)
                wanted=pairlook[condition,contrast,metric]
                assert same(float(dlt.mean()),wanted['difference'])
                np.testing.assert_allclose(np.quantile(boot,[.025,.975]),wanted['percentile95'],atol=1e-12);ci_checked+=1
    result=dict(calibration_thresholds_checked=8,episode_method_records_checked=checked,rate_cells_checked=len(ratelook),
        wilson_intervals_checked=wilson_checked,paired_intervals_checked=ci_checked,raw_packet_examples_checked=len(conditions),
        independent_score_max_abs_difference=max_error,scope='Same-author separate postprocessor; not external certification or new independent experiments.')
    dest=out/'verification.json'
    with dest.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('out');a=p.parse_args();verify(a.out)
