"""Independent postprocessor: does not use the experiment decision/metric functions."""
import argparse,json,hashlib,math
from pathlib import Path
import numpy as np


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def independent_rules(f,th):
    old=f[:,0]>th['v3'];flat=f[:,4]==1;pair=f[:,1]>th['dual']
    labels=np.full(len(f),-1,int)
    pairs=((0,1),(0,2),(1,2));D=np.zeros((len(f),3,3))
    for col,(i,j) in enumerate(pairs,1):D[:,i,j]=D[:,j,i]=f[:,col]
    for k in range(len(f)):
        candidates=[]
        for j in range(3):
            other=[i for i in range(3) if i!=j]
            if all(D[k,j,i]>th['triple'] for i in other) and D[k,other[0],other[1]]<=th['triple']:
                candidates.append(j)
        assert len(candidates)<=1
        if candidates:labels[k]=candidates[0]
    return {'v3_forced_primary':(np.where(old,0,-1),old),
            'flatline':(np.where(flat,0,-1),flat),
            'dual_forced_primary':(np.where(pair,0,-1),pair),
            'triple_consensus':(labels,(f[:,1:4]>th['triple']).any(axis=1)),
            'dual_unlocalized':(np.full(len(f),-1),pair),
            'v3_unlocalized':(np.full(len(f),-1),old),
            'always_abstain':(np.full(len(f),-1),np.zeros(len(f),bool))}


def run(root):
    root=Path(root);cal=json.loads((root/'calibration.json').read_text());summary=json.loads((root/'summary.json').read_text())
    thresholds_checked=0
    for mode in ('passive','active'):
        a=np.array([r['maxima'] for r in cal['rows'] if r['mode']==mode])
        for j,name in enumerate(('v3','dual','triple')):
            assert float(sorted(a[:,j])[189])==cal['thresholds'][mode][name]
            thresholds_checked+=1
    rate_lookup={(r['condition'],r['mode'],r['method']):r for r in summary['results']}
    files=sorted(root.glob('*_features.npz'));records_checked=0;cells=0;direct_max=0.;identical=[]
    for archive in files:
        c=archive.name.removesuffix('_features.npz');doc=json.loads((root/(c+'.json')).read_text())
        assert doc['calibration_sha256']==sha(root/'calibration.json')
        with np.load(archive) as z:
            times=z['times'];fs=z['features'];examples=z['example_measurements']
            assert fs.shape==(200,80,5)
            for i,y in enumerate(examples):
                expected=[]
                for t in times:
                    end=int(round(t/.01));w=y[end-40:end+1,2:]
                    expected.append([np.sqrt(np.mean((w[:,a]-w[:,b])**2)) for a,b in ((0,1),(0,2),(1,2))])
                err=float(np.max(np.abs(np.array(expected)-fs[i*100,:,1:4])))
                direct_max=max(direct_max,err);assert err<1e-8
            flat_by_mode={}
            for i,meta in enumerate(doc['metadata']):
                mode='active' if meta['active'] else 'passive';seed=meta['seed']
                rules=independent_rules(fs[i],cal['thresholds'][mode])
                records=[r for r in doc['rows'] if r['mode']==mode and r['seed']==seed]
                assert len(records)==7
                for r in records:
                    label,flags=rules[r['method']];ids=np.where(label==0)[0]
                    alarm=None if len(ids)==0 else float(times[ids[0]])
                    onset=meta['primary_onset']
                    valid=onset is not None and alarm is not None and alarm>=onset
                    event=valid if onset is not None else alarm is not None
                    early=onset is not None and alarm is not None and alarm<onset
                    unique_ids=np.where(label>=0)[0]
                    unique_time=None if not len(unique_ids) else float(times[unique_ids[0]])
                    target=meta['single_target'];anomaly_onset=meta['anomaly_onset']
                    correct=bool(target is not None and unique_time is not None and anomaly_onset is not None
                                 and unique_time>=anomaly_onset and label[unique_ids[0]]==target)
                    assert r['primary_alarm']==alarm and r['primary_event']==event and r['primary_early']==early
                    assert r['unique_correct']==correct
                    raw_ids=np.where(flags)[0]
                    raw_time=None if not len(raw_ids) else float(times[raw_ids[0]])
                    assert r['any_alarm']==raw_time
                    assert r['anomaly_valid']==bool(anomaly_onset is not None and raw_time is not None and raw_time>=anomaly_onset)
                    assert abs(r['unresolved_fraction']-float(np.mean(flags&(label<0))))<1e-15
                    records_checked+=1
            for mode in ('passive','active'):
                for method in rules:
                    rr=[r for r in doc['rows'] if r['mode']==mode and r['method']==method]
                    a=rate_lookup[c,mode,method]
                    assert len(rr)==a['n']==100
                    assert sum(r['primary_event'] for r in rr)==a['count']
                    assert sum(r['unique_correct'] for r in rr)==a['unique_correct']
                    assert sum(r['anomaly_valid'] for r in rr)==a['anomaly_valid']
                    cells+=1
    output=dict(calibration_thresholds_checked=thresholds_checked,episode_method_records_checked=records_checked,
                rate_cells_checked=cells,representative_raw_traces_checked=len(files)*2,
                independent_pair_RMS_max_abs_difference=direct_max,
                all_source_hashes=summary['source_hashes'],scope='Same-author independently implemented postprocessing; not third-party validation.')
    path=root/'independent_verification.json'
    with path.open('x') as f:json.dump(output,f,indent=2);f.write('\n')
    print(json.dumps(output,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);run(p.parse_args().root)
