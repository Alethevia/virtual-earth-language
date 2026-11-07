"""Separate aggregate/uncertainty reconstruction and direct-convolution checks.
Does NOT claim independent human review or independent real-world data.
"""
from __future__ import annotations
import argparse,json,math,csv,hashlib
from pathlib import Path
import numpy as np
from scipy.linalg import toeplitz
from scipy.signal import convolve
from scipy.stats import norm
from numba import njit
import study as defs  # constants/config only; never call main scoring/outcome functions.

@njit(cache=True)
def innovation_recursion(d,a,gain):
    out=np.empty(len(d));state=0.
    for t in range(len(d)):
        pred=a*state;out[t]=d[t]-pred;state=pred+gain*out[t]
    return out

def parameters(a,q,r):
    Q=q*(1-a*a);coef=r*(1-a*a)-Q
    prior=.5*(-coef+math.sqrt(coef*coef+4*Q*r))
    return prior/(prior+r),prior+r

def direct_scores(y,cfg,binary=False):
    N=len(y);start=round(5*cfg.fs);a=cfg.rho**(100/cfg.fs)
    if binary:
        d=y[:,0]-(y[:,1]+y[:,2])/2;n=round(5*cfg.fs)
        C=(.5 if cfg.rho else 0.)*cfg.scale**2*toeplitz(a**np.arange(n))+1.5*.25**2*cfg.scale**2*np.eye(n)
        w=np.ones(n)/math.sqrt(C.sum());out=np.zeros(N)
        out[n-1:]=convolve(d,w,mode='valid',method='direct');out=abs(out);out[:start]=0.
        return out
    result=np.zeros((3,3,N));ns=sorted(set(max(1,round(w*cfg.fs)) for w in defs.WINDOWS))
    for pair,(aa,bb) in enumerate(defs.PAIRS):
        d=y[:,aa]-y[:,bb];q=.5*cfg.scale**2 if cfg.rho and pair<2 else 0.;r=.125*cfg.scale**2
        K,S=parameters(a,q,r)
        aa_model=a if q else 0.;K=K if q else 0.
        e=innovation_recursion(d,aa_model,K)
        for n in ns:
            C=q*toeplitz(a**np.arange(n))+r*np.eye(n)
            m=abs(convolve(d,np.ones(n)/math.sqrt(C.sum()),mode='valid',method='direct'))
            result[1,pair,n-1:]=np.maximum(result[1,pair,n-1:],m)
            if n==round(5*cfg.fs):result[0,pair,n-1:]=m
            g=innovation_recursion(np.ones(n),aa_model,K)
            v=abs(convolve(e,g[::-1]/math.sqrt(S*np.dot(g,g)),mode='valid',method='direct'))
            result[2,pair,n-1:]=np.maximum(result[2,pair,n-1:],v)
    result[:,:,:start]=0.
    return result

def independent_outcome(score,threshold,cfg,target,onset,recovery):
    cross=np.asarray(score)>threshold
    if cross.ndim==1:alarm=cross;who=np.where(alarm,0,-1)
    else:
        alarm=cross.any(axis=0);who=np.full(cross.shape[1],-1)
        for channel,edges in ((0,(0,1,2)),(1,(0,2,1)),(2,(1,2,0))):
            i,j,k=edges;who[cross[i]&cross[j]&~cross[k]]=channel
    at=np.where(alarm)[0];uni=np.where(who>=0)[0];first=None if len(at)==0 else at[0]/cfg.fs
    ut=None if len(uni)==0 else uni[0]/cfg.fs;ul=-1 if len(uni)==0 else int(who[uni[0]])
    valid=bool(target>=0 and ut is not None and ut>=onset and ul==target and (recovery is None or ut<recovery))
    delay=ut-onset if valid else None
    wrong=False
    for label in range(3):
        ids=np.where(who==label)[0]
        if not len(ids):continue
        if target<0 or label!=target:wrong=True;break
        tt=ids/cfg.fs
        if (tt<onset).any() or (recovery is not None and (tt>=recovery).any()):wrong=True;break
    return dict(any_alarm=bool(len(at)),first_alarm=first,first_unique_time=ut,first_unique_label=ul,
                wrong_any=wrong,first_correct=valid,within5=bool(valid and delay<=5),within30=bool(valid and delay<=30),
                delay=delay,early_alarm=bool(onset is not None and first is not None and first<onset),
                early_unique=bool(onset is not None and ut is not None and ut<onset),
                post_recovery_accusation=bool(recovery is not None and np.any((np.arange(len(who))/cfg.fs>=recovery)&(who>=0))),
                any_unique=bool(len(uni)),coverage=1.)

def phase_meta(seed,target,shape):
    if target==-1:return None,None
    rng=np.random.default_rng(np.random.SeedSequence([seed,99]));on=float(rng.uniform(300,330))
    return on,on+2 if shape=='pulse' else None

def verify(root:Path):
    counters=dict(calibration_values=0,aggregate_cells=0,binomial_intervals=0,individual_records=0,representative_paths=0,
                  representative_outcomes=0,maximum_score_difference=0.)
    for rnd in (11,12,13):
        out=root/f'r{rnd}'
        if not (out/'summary.json').exists():continue
        summary=json.loads((out/'summary.json').read_text());rows=[]
        if rnd<13:
            cal=json.loads((out/'calibration.json').read_text())
            for g in cal['groups']:
                mx=np.asarray(g['maxima']);th=np.sort(mx,axis=0)[189]
                expected=np.array(g['threshold']) if rnd==11 else np.array([g['thresholds'][m] for m in defs.METHODS])
                np.testing.assert_array_equal(th,expected);counters['calibration_values']+=expected.size
            configs=defs.R11_CONFIGS if rnd==11 else defs.R12_CONFIGS
            for cfg in configs:
                doc=json.loads((out/(cfg.name+'.json')).read_text());rows.extend(doc['rows'])
        else:
            for case,*_ in defs.R13_CASES:rows.extend(json.loads((out/(case+'.json')).read_text())['rows'])
        counters['individual_records']+=len(rows)
        for rr in summary['results']:
            r=[x for x in rows if (x['config'],x['case'],x['method'])==(rr['config'],rr['case'],rr['method'])]
            assert len(r)==rr['n'] and len({x['seed'] for x in r})==len(r)
            for metric in defs.METRICS:
                k=sum(bool(x[metric]) for x in r);n=len(r);assert k==rr[metric]
                z=norm.ppf(.975);p=k/n
                lo=(p+z*z/(2*n)-z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)))/(1+z*z/n)
                hi=(p+z*z/(2*n)+z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)))/(1+z*z/n)
                np.testing.assert_allclose([max(0,lo),min(1,hi)],rr[metric+'_wilson95'],atol=2e-15)
                counters['binomial_intervals']+=1
            d=[x['delay'] for x in r if x['delay'] is not None]
            assert (None if not d else float(np.median(d)))==rr['conditional_median_delay']
            counters['aggregate_cells']+=1
        if rnd<13:
            for cfg in configs:
                pack=np.load(out/(cfg.name+'_examples.npz'))
                cases=('healthy','primary05') if rnd==11 else ('healthy','primary05','pulse')
                seed=920000 if rnd==11 else 940000
                g=next(g for g in cal['groups'] if g['name']==cfg.name)
                for case in cases:
                    target=-1 if case=='healthy' else 0;on,rec=phase_meta(seed,target,'pulse' if case=='pulse' else 'step')
                    computed=direct_scores(pack[case+'_input'],cfg,binary=rnd==11);saved=pack[case+'_scores']
                    diff=float(np.max(abs(computed-saved)));counters['maximum_score_difference']=max(counters['maximum_score_difference'],diff)
                    np.testing.assert_allclose(computed,saved,atol=2e-9,rtol=1e-10)
                    methods=('known_target_mean5',) if rnd==11 else defs.METHODS
                    for j,m in enumerate(methods):
                        th=g['threshold'] if rnd==11 else g['thresholds'][m]
                        rr=next(x for x in rows if (x['config'],x['case'],x['method'],x['seed'])==(cfg.name,case,m,seed))
                        calc=independent_outcome(computed if rnd==11 else computed[j],th,cfg,target,on,rec)
                        for key,val in calc.items():assert val==rr[key],(rnd,cfg.name,case,m,key,val,rr[key])
                        counters['representative_outcomes']+=1
                    counters['representative_paths']+=1
        else:
            lock=json.loads((root/'SELECTION_LOCK.json').read_text());cfg=defs.Config(**lock['config']);seed=950000
            methods=tuple(dict.fromkeys(('mean5',lock['selected'])))
            for case,family,target,amp,shape in defs.R13_CASES:
                pack=np.load(out/(case+'_example.npz'));computed=direct_scores(pack['input'],cfg);saved=pack['scores']
                diff=float(np.max(abs(computed-saved)));counters['maximum_score_difference']=max(counters['maximum_score_difference'],diff)
                np.testing.assert_allclose(computed,saved,atol=2e-9,rtol=1e-10)
                on,rec=phase_meta(seed,target,shape)
                for m in methods:
                    rr=next(x for x in rows if (x['case'],x['method'],x['seed'])==(case,m,seed))
                    calc=independent_outcome(computed[defs.METHODS.index(m)],lock['thresholds'][m],cfg,target,on,rec)
                    for key,val in calc.items():assert val==rr[key],(case,m,key,val,rr[key])
                    counters['representative_outcomes']+=1
                counters['representative_paths']+=1
        print('VERIFIED ROUND',rnd,flush=True)
    counters['scope']='All aggregates/intervals recomputed from records; representative complete scores/outcomes independently recomputed. Other raw paths regenerable. Same-author checks, not third-party validation.'
    return counters

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args()
    result=verify(a.root)
    print(json.dumps(result,indent=2))
    with (a.root/'VERIFICATION.json').open('x') as f:json.dump(result,f,indent=2)
