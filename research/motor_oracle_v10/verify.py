"""Independent V10 verification: AR precision/Woodbury, direct convolution,
Monte Carlo distribution checks and packed first-alarm reconstruction.
Same-author verification, not independent human peer review.
"""
from pathlib import Path
from functools import lru_cache
import argparse, json, math, hashlib
import numpy as np
from scipy.linalg import solve_banded, cho_factor, cho_solve
from scipy.stats import norm

@lru_cache(maxsize=None)
def direct_information(n,a,q,r,initial):
    if q==0:return n/r
    if n==1:
        return 1/(r+(q if initial=='stationary' else q*(1-a*a)))
    # AR latent precision is tridiagonal. Woodbury avoids the experimental
    # innovation recurrence entirely and handles long (n=3000) grids cheaply.
    innovation_var=q*(1-a*a)
    diagonal=np.full(n,(1+a*a)/innovation_var)
    diagonal[-1]=1/innovation_var
    if initial=='stationary':diagonal[0]=1/innovation_var
    elif initial!='perfect_state':raise ValueError(initial)
    ab=np.zeros((3,n));ab[1]=diagonal+1/r
    ab[0,1:]=-a/innovation_var;ab[2,:-1]=-a/innovation_var
    u=solve_banded((1,1),ab,np.ones(n))
    return n/r-float(u.sum())/(r*r)

def params(p):
    step=50 if p.startswith('sparse') else 1
    rho=.99 if p.endswith('ar99') else (.9 if p.endswith('ar') else 0.)
    return step*.01,rho**step,.5 if rho else 0.

def C(n,a,q,r,init):
    t=np.arange(n);c=q*a**np.abs(t[:,None]-t[None,:])+r*np.eye(n)
    if init=='perfect_state':c-=q*np.outer(a**(t+1),a**(t+1))
    return c

def run(root):
    root=Path(root);power=json.loads((root/'oracle_power.json').read_text())['rows']
    max_info=0.;max_power=0.
    for row in power:
        dt,a,q=params(row['profile']);n=row['n_observations']
        tier=row['tier'];r=.0625 if tier=='truth_speed_latent_genie' else .09375
        init='stationary' if tier=='contrast_post_only' else 'perfect_state'
        info=direct_information(n,a,q,r,init)
        max_info=max(max_info,abs(info-row['information_per_squared_amplitude']))
        assert math.isclose(info,row['information_per_squared_amplitude'],rel_tol=2e-10,abs_tol=2e-10)
        p=float(norm.sf(norm.isf(row['alpha'])-row['amplitude']*math.sqrt(info)))
        max_power=max(max_power,abs(p-row['power']));assert abs(p-row['power'])<1e-10
    mc=json.loads((root/'oracle_mc.json').read_text());zdata=np.load(root/'oracle_mc_inputs.npz')
    direct_mc_error=0.
    for row in mc['rows']:
        dt,a,q=params(row['profile']);n=round(5/dt)
        r=.0625 if row['tier']=='truth_speed_latent_genie' else .09375
        info=direct_information(n,a,q,r,'perfect_state')
        name=row['profile']+'__'+row['tier'];z=zdata[name+'__null_Z'];ys=zdata[name]
        one=np.ones(n);w=cho_solve(cho_factor(C(n,a,q,r,'perfect_state')),one)/math.sqrt(info)
        err=np.max(np.abs(ys@w-z[:len(ys)]));direct_mc_error=max(direct_mc_error,float(err))
        assert err<1e-10
        assert int((z>norm.isf(row['alpha'])).sum())==row['false_count']
        assert int((z+.5*math.sqrt(info)>norm.isf(row['alpha'])).sum())==row['power_count']
        assert abs(z.mean())<6/math.sqrt(len(z))
        assert abs(z.var(ddof=1)-1)<6*math.sqrt(2/(len(z)-1))
        for estimate,truth in ((row['false_rate'],row['alpha']),(row['power_rate'],row['analytic_power'])):
            assert abs(estimate-truth)<=6*math.sqrt(truth*(1-truth)/len(z))+1/len(z)
    cal=json.loads((root/'calibration.json').read_text());nthreshold=0
    for p,g in cal['groups'].items():
        maxima=np.array([r['maxima'] for r in g['rows']])
        for j,th in enumerate(g['thresholds']):
            assert th==sorted(maxima[:,j])[189];nthreshold+=1
    allrecords=[];record_count=0
    profiles=list(cal['groups'])
    for p in profiles:
        doc=json.loads((root/f'test_{p}.json').read_text())
        data=np.load(root/f'test_{p}_flags.npz');times=data['times'];packed=data['flags']
        groups={(r['seed'],r['mode'],r['amplitude'],r['model'],r['method']):r for r in doc['records']}
        for idx,case in enumerate(doc['index']):
            flags=np.unpackbits(packed[idx],axis=1,count=len(times)).astype(bool)
            for j,m in enumerate(('mean5','gls5')):
                r=groups[case['seed'],case['mode'],case['amplitude'],case['model'],m]
                ix=np.where(flags[j])[0];first=None if len(ix)==0 else float(times[ix[0]])
                on=case['onset'];ok=bool(first is not None and on is not None and first>=on)
                delay=first-on if ok else None
                expected=dict(first_alarm=first,any_alarm=bool(len(ix)),
                    pre_fault_alarm=bool(first is not None and on is not None and first<on),
                    first_alarm_valid=ok,within_5s=bool(ok and delay<=5),within_30s=bool(ok and delay<=30),delay=delay)
                for k,v in expected.items():assert v==r[k],(p,k,v,r[k])
                record_count+=1
        allrecords+=doc['records']
    summary=json.loads((root/'summary.json').read_text())
    for row in summary['rows']:
        rr=[r for r in allrecords if all(r[k]==row[k] for k in ('profile','mode','amplitude','model','method'))]
        assert len(rr)==row['n']
        for metric in ('any_alarm','pre_fault_alarm','first_alarm_valid','within_5s','within_30s'):
            count=sum(r[metric] for r in rr);assert count==row[metric+'_count']
            assert count/len(rr)==row[metric+'_rate']
    max_convolution=0.;examples=0
    for path in root.glob('example_*.npz'):
        d=np.load(path);name=path.stem
        p=next(p for p in sorted(profiles,key=len,reverse=True) if name.startswith('example_'+p+'_'))
        fit=p.replace('ar99','ar') if 'misspecified' in name else p
        dt,a,q=params(fit);n=round(5/dt);one=np.ones(n);cov=C(n,a,q,.09375,'stationary')
        inv=cho_solve(cho_factor(cov),one)
        ws=(one/math.sqrt(one@cov@one),inv/math.sqrt(one@inv))
        for j,w in enumerate(ws):
            score=np.convolve(d['contrast'],w[::-1],mode='valid')
            err=float(np.max(np.abs(score-d['scores'][j])))
            max_convolution=max(max_convolution,err);assert err<1e-9
            # Arithmetic may only change ties, not a reference binary decision.
            np.testing.assert_array_equal(np.abs(score)>d['thresholds'][j],np.abs(d['scores'][j])>d['thresholds'][j])
        examples+=1
    audit=dict(theory_rows_checked=len(power),mc_cells_checked=len(mc['rows']),
        explicit_MC_windows=mc['n_observation_windows'],calibration_thresholds_checked=nthreshold,
        packed_records_reconstructed=record_count,scan_cells_checked=len(summary['rows']),
        full_direct_convolution_examples=examples,max_information_abs_difference=max_info,
        max_power_abs_difference=max_power,max_direct_MC_Z_difference=direct_mc_error,
        max_direct_convolution_score_difference=max_convolution,
        scope='Same-author independently implemented calculations. Not human third-party certification.')
    with (root/'verification.json').open('x') as f:json.dump(audit,f,indent=2);f.write('\n')
    print(json.dumps(audit,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();run(a.root)
