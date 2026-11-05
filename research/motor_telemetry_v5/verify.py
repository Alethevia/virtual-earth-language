"""Separately implemented replay from saved arrays/packets, not third-party review.
Does not call the experimental feature, decision, or record implementations.
"""
from pathlib import Path
import sys,json,math,hashlib
import numpy as np
from scipy.stats import binomtest

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def first(times,mask):
    ids=np.where(mask)[0]
    return None if ids.size==0 else float(times[ids[0]])
def direct_packets(p):
    y=p['values'];st=p['stamps'];sigma=p['sigma'];quantum=p['quantum'];offset=p['offset_bound']
    pairs=[(0,1),(0,2),(1,2)];ticks=range(200,len(y),20)
    score=np.zeros((len(ticks),4,3));available=np.zeros((len(ticks),4),bool)
    count=np.zeros(len(ticks),int);age=np.full(len(ticks),-1.)
    # Independently reconstruct only packets that have arrived by each tick.
    for r,t in enumerate(ticks):
        for m,w in [(0,40),(1,200)]:
            values=y[t-w:t+1]
            if np.isfinite(values).all():
                available[r,m]=True
                score[r,m]=[np.sqrt(np.mean((values[:,a]-values[:,b])**2)) for a,b in pairs]
        maps=[]
        for c in range(3):
            mask=(st[:t+1,c]>=t-200)&(st[:t+1,c]>=0)
            maps.append(dict(zip(st[:t+1,c][mask].tolist(),y[:t+1,c][mask].tolist())))
        common=sorted(set(maps[0])&set(maps[1])&set(maps[2]))
        count[r]=len(common)
        if common:age[r]=(t-common[-1])*.01
        if len(common)<3 or t-common[-1]>60:continue
        available[r,2:]=True
        z=np.array([[maps[c][k] for c in range(3)] for k in common])
        for j,(a,b) in enumerate(pairs):
            diff=np.abs(z[:,a]-z[:,b]);score[r,2,j]=np.sqrt(np.mean(diff**2))
            excess=np.maximum(0,diff-(quantum[a]+quantum[b])/2-offset[a]-offset[b])
            score[r,3,j]=np.sqrt(np.mean(excess**2)/(sigma[a]**2+sigma[b]**2))
    return score,available,count,age


def verify(root):
    root=Path(root);cal=json.loads((root/'calibration.json').read_text());summary=json.loads((root/'summary.json').read_text())
    methods=('v4_frozen','raw_matched','window_only','time_aligned','time_quality','always_abstain')
    streams=('raw_short','raw_long','aligned','quality');columns=(0,0,1,2,3)
    values=np.array([r['maxima'] for r in cal['rows']]);rank=math.ceil((len(values)+1)*.95)
    assert rank==cal['rank']==190
    for j,name in enumerate(streams):assert float(sorted(values[:,j])[rank-1])==cal['thresholds'][name]
    records=[];maximum=0.;examples=0;generic={};rng=np.random.default_rng(44994);paired=[]
    conditions=list(dict.fromkeys(r['condition'] for r in summary['results']))
    for condition in conditions:
        d=json.loads((root/f'{condition}.json').read_text());archive=np.load(root/f'{condition}_features.npz');features={k:archive[k] for k in archive.files};archive.close();times=features['times']
        assert d['calibration_sha256']==sha(root/'calibration.json') and d['source_hashes']==cal['source_hashes']
        packet=np.load(root/f'{condition}_example.npz');expected=direct_packets(packet)
        for name,want in zip(('scores','available','counts','ages'),expected):
            got=features[name][0]
            if name=='scores':maximum=max(maximum,float(abs(want-got).max()));np.testing.assert_allclose(got,want,atol=1e-10,rtol=1e-11)
            else:np.testing.assert_array_equal(got,want)
        examples+=1
        bykey={(r['seed'],r['method']):r for r in d['rows']}
        assert len(bykey)==600
        for i,meta in enumerate(d['metadata']):
            for mi,method in enumerate(methods):
                labels=np.full(len(times),-1,int);flags=np.zeros(len(times),bool);avail=np.ones(len(times),bool)
                if mi<5:
                    col=columns[mi];avail=features['available'][i,:,col]
                    th=.49060564088478326 if mi==0 else cal['thresholds'][streams[col]]
                    bad=(features['scores'][i,:,col,:]>th)&avail[:,None]
                    flags=np.any(bad,axis=1)
                    for q in range(len(times)):
                        a,b,c=bad[q]
                        if a and b and not c:labels[q]=0
                        if a and c and not b:labels[q]=1
                        if b and c and not a:labels[q]=2
                pt=first(times,labels==0);at=first(times,flags);ut=first(times,labels>=0)
                channel=None if ut is None else int(labels[np.where(labels>=0)[0][0]])
                po=meta['primary_onset'];ao=meta['anomaly_onset'];target=meta['single_target']
                valid=bool(po is not None and pt is not None and pt>=po)
                early=bool(po is not None and pt is not None and pt<po)
                row=dict(condition=condition,seed=meta['seed'],method=method,primary_fault=po is not None,
                    primary_alarm=pt,primary_valid=valid,primary_event=valid if po is not None else pt is not None,
                    primary_early=early,primary_delay=pt-po if valid else None,any_alarm=at,
                    anomaly_valid=bool(ao is not None and at is not None and at>=ao),any_unique=ut,isolated_channel=channel,
                    unique_correct=bool(target is not None and ut is not None and ao is not None and ut>=ao and channel==target),
                    unresolved_fraction=float(np.mean(flags&(labels<0))),coverage=float(avail.mean()),insufficient_fraction=float((~avail).mean()))
                expectedrow=bykey[meta['seed'],method]
                for k,v in row.items():
                    if isinstance(v,float):assert math.isclose(v,expectedrow[k],rel_tol=0,abs_tol=1e-12),(condition,method,k)
                    else:assert v==expectedrow[k],(condition,method,k,v,expectedrow[k])
                records.append(row)
        groups={m:np.array([r['primary_event'] for r in records if r['condition']==condition and r['method']==m],int) for m in methods}
        for cmp in ('v4_frozen','raw_matched','time_aligned'):
            diff=groups['time_quality']-groups[cmp]
            b=diff[rng.integers(0,100,size=(10000,100))].mean(axis=1)
            paired.append((condition,cmp,float(diff.mean()),np.quantile(b,[.025,.975])))
    for cell in summary['results']:
        r=[x for x in records if x['condition']==cell['condition'] and x['method']==cell['method']]
        k=sum(x['primary_event'] for x in r);assert len(r)==cell['n']==100 and k==cell['count']
        interval=binomtest(k,100).proportion_ci(method='wilson');np.testing.assert_allclose(cell['wilson95'],[interval.low,interval.high],atol=1e-12)
        for key,stat in [('early',sum(x['primary_early'] for x in r)),('unique_correct',sum(x['unique_correct'] for x in r)),
            ('any_alarm_count',sum(x['any_alarm'] is not None for x in r)),('anomaly_valid',sum(x['anomaly_valid'] for x in r)),
            ('coverage',float(np.mean([x['coverage'] for x in r]))),('unresolved_fraction',float(np.mean([x['unresolved_fraction'] for x in r])))]:
            assert math.isclose(cell[key],stat,abs_tol=1e-12),(key,cell['condition'],cell['method'])
        delays=[x['primary_delay'] for x in r if x['primary_delay'] is not None]
        assert cell['conditional_median_delay']==(None if not delays else float(np.median(delays)))
    for expected,(c,cmp,delta,ci) in zip(summary['paired'],paired):
        assert expected['condition']==c and expected['contrast']=='time_quality minus '+cmp
        assert expected['difference']==delta;np.testing.assert_array_equal(expected['ci95'],ci)
    result={'calibration_thresholds':4,'records_reconstructed':len(records),'rate_cells':len(summary['results']),
            'paired_intervals_recomputed':len(paired),'packet_examples':examples,'direct_score_max_abs_difference':maximum,
            'scope':'Same-author separately implemented verification, not third-party certification. Full saved records and representative raw packet windows checked.'}
    with (root/'verification.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))

if __name__=='__main__':verify(sys.argv[1])
