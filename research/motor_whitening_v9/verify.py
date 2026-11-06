"""Second implementation: rederive full decisions/records and direct FIR scans.
Does not call the experiment's score, label or record functions. Same-author
verification, NOT third-party certification.
"""
import sys,json,math,hashlib,time
from pathlib import Path
import numpy as np
from scipy.signal import fftconvolve
from scipy.linalg import solve_toeplitz
import whitening as w

def first_where(mask,times):
    any_=mask.any(axis=1);idx=mask.argmax(axis=1)
    return np.where(any_,times[idx],np.nan),idx,any_

def reconstruct(lab,flag,times,case,end):
    keep=times<end;ll=lab[:,keep];ff=flag[:,keep];tt=times[keep]
    first,ix,have=first_where(ll>=0,tt);channels=ll[np.arange(len(ll)),ix]
    alarm,_,ha=first_where(ff,tt)
    on=case['onset'];target=case['target'];fault=on is not None
    upper=on+2 if case['mode']=='two_second_pulse' else math.inf
    correct=have & (first>=on) & (first<upper) & (channels==target) if fault and target is not None else np.zeros(len(ll),bool)
    wrong=ll>=0 if not fault or target is None else ((ll>=0)&((tt[None,:]<on)|(tt[None,:]>=upper)|(ll!=target)))
    pre=ff if not fault else ff&(tt[None,:]<on)
    delay=np.where(correct,first-(0 if on is None else on),np.nan)
    eventual=((ll==target)&(tt[None,:]>=on)&(tt[None,:]<upper)).any(axis=1) if fault and target is not None else np.zeros(len(ll),bool)
    out=[]
    for j in range(len(ll)):
        out.append(dict(generic_alarm=bool(ff[j].any()),generic_false=bool(pre[j].any()),wrong_any=bool(wrong[j].any()),
            first_unique=float(first[j]) if have[j] else None,first_label=int(channels[j]) if have[j] else None,
            first_generic=float(alarm[j]) if ha[j] else None,first_correct=bool(correct[j]),delay=float(delay[j]) if correct[j] else None,
            within_5s=bool(correct[j] and delay[j]<=5),within_30s=bool(correct[j] and delay[j]<=30),eventual_correct=bool(eventual[j]),
            first_generic_valid=bool(fault and ha[j] and alarm[j]>=on),
            pre_fault_unique=bool(fault and ((ll[j]>=0)&(tt<on)).any()),coverage=1.,
            restricted_delay_30s=min(30.,float(delay[j])) if correct[j] else 30.,
            unresolved_fraction=float(np.mean(ff[j]&(ll[j]<0)))))
    return out

def score_reference(raw,model):
    y=raw['values'];st=raw['stamps'];dt=model['dt'];tt=raw['times']
    idx=np.flatnonzero((st[:,0]==st[:,1])&(st[:,0]==st[:,2])&(st[:,0]>=0))
    idx=idx[np.r_[True,np.diff(st[idx,0])>0]];kac=st[idx,0]
    d=np.column_stack((y[idx,0]-y[idx,1],y[idx,0]-y[idx,2],y[idx,1]-y[idx,2]))
    ends=np.searchsorted(kac,np.rint(tt/.01).astype(int),side='right')-1
    starts=np.searchsorted(kac,np.rint(tt/.01).astype(int)-200,side='left');counts=ends-starts+1
    out=np.zeros_like(raw['scores']);diag=[]
    for j,(a,b) in enumerate(((0,1),(0,2),(1,2))):
        x=d[:,j];phi=np.array(model['phi'][j]);order=len(phi);N=len(x)
        B=(raw['quantum'][a]+raw['quantum'][b])/2+raw['offset_bound'][a]+raw['offset_bound'][b]
        var=raw['sigma'][a]**2+raw['sigma'][b]**2
        e=x.copy()
        for lag in range(1,order+1):e[lag:]-=phi[lag-1]*x[:-lag]
        dinf=1.-sum(phi);marg=model['marginal_sd'][j];sd=model['innovation_sd'][j]
        # Direct slice means for original streams, not the experiment prefix-sum implementation.
        for r,(start,end) in enumerate(zip(starts,ends)):
            segment=x[start:end+1]
            out[r,0,j]=np.sqrt(np.mean(np.maximum(0.,np.abs(segment)-B)**2)/var)
            out[r,1,j]=max(0.,abs(float(segment.mean()))-B)/marg
        for length in sorted(set(max(order,int(math.ceil(sec/dt))) for sec in w.WINDOWS)):
            weights=np.array([1.-sum(phi[:min(i,order)]) for i in range(length)])
            keep=ends>=length-1+order;end=ends[keep]
            sx=fftconvolve(x,np.ones(length),mode='full')[:N]
            se=fftconvolve(e,np.ones(length),mode='full')[:N]
            sm=fftconvolve(e,weights[::-1],mode='full')[:N]
            v0=np.maximum(0.,np.abs(sx[end])-length*B)/(marg*np.sqrt(length))
            v1=np.maximum(0.,np.abs(se[end])-length*B*abs(dinf))/(sd*np.sqrt(length))
            v2=np.maximum(0.,np.abs(sm[end])-B*abs(dinf*weights.sum()))/(sd*np.linalg.norm(weights))
            for col,vals in zip((2,3,4),(v0,v1,v2)):out[keep,col,j]=np.maximum(out[keep,col,j],vals)
        positive=np.cumsum(x-.25-B);negative=np.cumsum(-x-.25-B)
        pu=positive-np.minimum.accumulate(np.r_[0.,positive])[1:]
        pd=negative-np.minimum.accumulate(np.r_[0.,negative])[1:]
        out[:,5,j]=np.maximum(pu,pd)[ends]
        mid=len(x)//2
        xx=x[order:mid]-x[order:mid].mean();ee=e[order:mid]-e[order:mid].mean()
        diag.append(dict(pair=j,raw_lag1=float(xx[1:]@xx[:-1]/(xx@xx)),innovation_lag1=float(ee[1:]@ee[:-1]/(ee@ee))))
    return out,diag

def decide_reference(score,threshold,dt):
    labs=np.full((7,len(score)),-1,np.int8);flags=np.zeros_like(labs,bool)
    th=list(threshold)+[w.CUSUM_H[0 if dt<.1 else 1]]
    for j in range(6):
        cross=score[:,j]>th[j];flags[j]=cross.any(axis=1)
        for target,opposite,adjacent in [(0,2,(0,1)),(1,1,(0,2)),(2,0,(1,2))]:
            mask=cross[:,adjacent[0]]&cross[:,adjacent[1]]&~cross[:,opposite];labs[j,mask]=target
    return labs,flags

def wilson(c,n):
    z=1.959963984540054;p=c/n
    center=(p+z*z/(2*n))/(1+z*z/n);radius=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return [max(0.,center-radius),min(1.,center+radius)]

def verify(root):
    root=Path(root);tic=time.perf_counter();tr=json.loads((root/'training.json').read_text());cal=json.loads((root/'calibration.json').read_text());summary=json.loads((root/'summary.json').read_text())
    assert tr['source_hashes']==cal['source_hashes']==summary['source_hashes']==w.sources()
    fitchecks=0
    for m in tr['models'].values():
        for j in range(3):
            gamma=np.array(m['autocovariance'][j]);diag=gamma[:-1].copy();diag[0]+=gamma[0]*1e-6
            phi=solve_toeplitz((diag,diag),gamma[1:]);np.testing.assert_allclose(phi,m['phi'][j],atol=1e-12)
            assert abs(np.sqrt(gamma[0]-phi@gamma[1:])-m['innovation_sd'][j])<1e-12
            fitchecks+=1
    thresholds=0
    for profile in w.PROFILES:
        d=json.loads((root/f'cal_{profile}.json').read_text());a=np.array([r['maxima'] for r in d['rows']])
        want=np.sort(a,axis=0)[189];np.testing.assert_allclose(want,cal['thresholds'][profile],atol=1e-12);thresholds+=5
    all_records=[];count=0
    for profile in w.PROFILES+w.STRESS:
        for p in sorted(root.glob(profile+'_*.json')):
            doc=json.loads(p.read_text());a=np.load(p.with_name(p.stem+'_decisions.npz'));L=a['labels'];F=a['flags']
            lookup={(r['seed'],r['mode'],r['amplitude'],r['horizon'],r['method']):r for r in doc['records']}
            times=np.arange(2.,600.,.2);times=np.arange(200,60000,20)*.01
            for i,case in enumerate(doc['cases']):
                for end in ((18.,180.,600.) if case['mode']=='healthy' else (600.,)):
                    rr=reconstruct(L[i],F[i],times,case,end)
                    for j,method in enumerate(w.METHODS):
                        got=lookup[(case['seed'],case['mode'],case['amplitude'],end,method)]
                        for k,v in rr[j].items():
                            if isinstance(v,float):assert math.isclose(v,got[k],rel_tol=1e-11,abs_tol=1e-11),(p,k,v,got[k])
                            else:assert v==got[k],(p,k,v,got[k])
                        count+=1
            all_records+=doc['records']
    keys=('profile','mode','amplitude','horizon','method');groups={}
    for r in all_records:groups.setdefault(tuple(r[k] for k in keys),[]).append(r)
    intervals=0
    for row in summary['results']:
        rr=groups[tuple(row[k] for k in keys)];rr.sort(key=lambda r:r['seed']);assert len(rr)==200
        for metric in w.METRICS:
            c=sum(r[metric] for r in rr);assert c==row[metric+'_count']
            np.testing.assert_allclose(wilson(c,200),row[metric+'_wilson95'],atol=1e-14);intervals+=1
        de=[r['delay'] for r in rr if r['first_correct']]
        assert (None if not de else float(np.median(de)))==row['conditional_median_delay']
    pairmap={tuple(d[k] for k in keys[:-1])+(d['contrast'],d['metric']):d for d in summary['paired']}
    rng=np.random.default_rng(45009);paired=0
    for key in sorted(set(k[:-1] for k in groups)):
        ix=rng.integers(0,200,size=(3000,200));a=groups[key+(w.PRIMARY,)]
        for comp in ('rms_matched','mean_2s','signed_scan','whiten_naive','v8_cusum_frozen'):
            b=groups[key+(comp,)]
            for metric in ('generic_false','wrong_any','within_5s','first_correct'):
                delta=np.array([r[metric] for r in a],float)-np.array([r[metric] for r in b],float)
                want=pairmap[key+(w.PRIMARY+' - '+comp,metric)]
                np.testing.assert_allclose(np.quantile(delta[ix].mean(axis=1),[.025,.975]),want['percentile95'],atol=1e-14);paired+=1
    discrepancies=np.zeros(6);examples=0;diagnostics={}
    for p in sorted(root.glob('example_*.npz')):
        profile=next(pf for pf in w.PROFILES+w.STRESS if p.name.startswith('example_'+pf+'_'))
        m=tr['models'][profile.replace('ar99','ar')];raw=np.load(p);ref,diag=score_reference(raw,m)
        discrepancies=np.maximum(discrepancies,np.max(np.abs(ref-raw['scores']),axis=(0,2)))
        np.testing.assert_allclose(ref,raw['scores'],atol=1e-6,rtol=1e-8)
        lab,flag=decide_reference(ref,cal['thresholds'][profile.replace('ar99','ar')],m['dt'])
        np.testing.assert_array_equal(lab,raw['labels']);np.testing.assert_array_equal(flag,raw['flags'])
        examples+=1
        if 'healthy' in p.name:diagnostics[profile]=diag
    result=dict(training_model_equations_checked=fitchecks,thresholds_checked=thresholds,records_reconstructed=count,rate_cells=len(summary['results']),
        wilson_intervals=intervals,paired_intervals=paired,full_packet_score_examples=examples,max_score_discrepancy_by_stream=discrepancies.tolist(),
        heldout_representative_lag1=diagnostics,elapsed_seconds=time.perf_counter()-tic,
        scope='Same-author second implementation; not third-party certification. Entire representative score paths, all saved outcome records/intervals checked.')
    with (root/'verification.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))
if __name__=='__main__':verify(sys.argv[1])
