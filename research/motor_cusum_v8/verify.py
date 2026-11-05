"""Separately implemented V8 postprocessing and full representative packet scores.
Same-author verification, not independent human peer review. No experimental edits.
"""
import sys,json,math,hashlib
from pathlib import Path
import numpy as np
import cusum_study as s

def close(a,b,tol=1e-9):
 if a is None or b is None:assert a is b,(a,b)
 elif isinstance(a,(bool,str)):assert a==b,(a,b)
 else:assert np.allclose(a,b,atol=tol,rtol=1e-10),(a,b)

def reconstruct(times,label,flag,valid,case,end):
 ix=np.where(times<end)[0];tt=times[ix];ll=label[ix];ff=flag[ix];vv=valid[ix]
 unique=np.flatnonzero(ll>=0);alarms=np.where(ff)[0]
 first=None if len(unique)==0 else float(tt[unique[0]])
 ident=None if len(unique)==0 else int(ll[unique[0]])
 alarm=None if len(alarms)==0 else float(tt[alarms[0]])
 onset=case['onset'];target=case['target'];fault=onset is not None
 stop=onset+2 if case['mode']=='two_second_pulse' else float('inf')
 correct=bool(fault and target is not None and first is not None and onset<=first<stop and ident==target)
 delay=first-onset if correct else None
 wrong=bool(np.any(ll>=0)) if not fault or target is None else bool(np.any((ll>=0)&((tt<onset)|(tt>=stop)|(ll!=target))))
 return dict(generic_alarm=bool(len(alarms)),generic_false=bool(np.any(ff if not fault else ff&(tt<onset))),
   wrong_any=wrong,first_unique=first,first_label=ident,first_generic=alarm,first_correct=correct,
   delay=delay,within_5s=bool(correct and delay<=5),within_30s=bool(correct and delay<=30),
   eventual_correct=bool(fault and target is not None and np.any((ll==target)&(tt>=onset)&(tt<stop))),
   first_generic_valid=bool(fault and alarm is not None and alarm>=onset),
   pre_fault_unique=bool(fault and np.any((ll>=0)&(tt<onset))),coverage=float(np.sum(vv)/len(vv)),
   restricted_delay_30s=min(30.,delay) if correct else 30.,unresolved_fraction=float(np.sum(ff&(ll<0))/len(ff)))

def independent_scores(z):
 values=z['values'];stamps=z['stamps'];n=len(values)
 # Distinct acquisition records and their FIRST reception; no simulator truth.
 maps=[]
 for c in range(3):
  use=np.r_[True,stamps[1:,c]!=stamps[:-1,c]]&(stamps[:,c]>=0)
  ix=np.where(use)[0];maps.append({int(stamps[i,c]):(i,float(values[i,c])) for i in ix})
 common=np.array(sorted(set(maps[0])&set(maps[1])&set(maps[2])))
 arrival=np.array([max(m[int(k)][0] for m in maps) for k in common])
 obs=np.array([[m[int(k)][1] for m in maps] for k in common]);assert (np.diff(arrival)>=0).all()
 pairs=((0,1),(0,2),(1,2));D=np.array([obs[:,a]-obs[:,b] for a,b in pairs]).T
 bound=np.array([(z['quantum'][a]+z['quantum'][b])/2+z['offset_bound'][a]+z['offset_bound'][b] for a,b in pairs])
 var=np.array([z['sigma'][a]**2+z['sigma'][b]**2 for a,b in pairs])
 curves=[]
 for direction in (1,-1):
  walk=np.cumsum(direction*D-.25-bound,axis=0)
  floor=np.minimum.accumulate(np.vstack([np.zeros((1,3)),walk]),axis=0)[1:]
  curves.append(walk-floor)
 cs=np.maximum(curves[0],curves[1]);out=np.zeros_like(z['scores']);valid=np.zeros(len(out),bool);counts=np.zeros(len(out),int)
 for j,t in enumerate(np.arange(200,n,20)):
  hi=np.searchsorted(arrival,t,side='right');lo=np.searchsorted(common,t-200,side='left');count=max(0,hi-lo);counts[j]=count
  if count<3 or t-common[hi-1]>60:continue
  valid[j]=True;x=D[lo:hi]
  out[j,0]=np.sqrt(np.mean(np.maximum(0,np.abs(x)-bound)**2/var,axis=0))
  out[j,1]=np.maximum(0,np.abs(np.mean(x,axis=0))-bound)
  out[j,2]=cs[hi-1]
 return out,valid,counts

def main(root):
 cal=json.loads((root/'calibration.json').read_text());summary=json.loads((root/'summary.json').read_text())
 assert cal['source_hashes']==s.sources()==summary['source_hashes']
 actualhash=hashlib.sha256((root/'calibration.json').read_bytes()).hexdigest()
 for p in s.PROFILES:
  rows=[r for r in cal['rows'] if r['profile']==p];assert len(rows)==199
  for j,m in enumerate(s.STREAMS):close(sorted(r['maxima'][j] for r in rows)[189],cal['groups'][p][m])
 for m in s.STREAMS:
  for j,prefix in enumerate(('dense','sparse')):close(max(v[m] for p,v in cal['groups'].items() if p.startswith(prefix)),cal['rate'][m][j])
  close(max(cal['rate'][m]),cal['universal'][m])
 groups={};checked=0
 for profile in s.PROFILES+s.STRESS:
  for fn in sorted(root.glob(profile+'_*.json')):
   doc=json.loads(fn.read_text());assert doc['source_hashes']==s.sources();assert doc['calibration_sha256']==actualhash
   z=np.load(fn.with_name(fn.stem+'_decisions.npz'));labs=z['labels'];flgs=z['flags']
   rows={(r['seed'],r['mode'],r['amplitude'],r['horizon'],r['method']):r for r in doc['records']}
   for i,case in enumerate(doc['cases']):
    times=np.arange(200,60000,20)*.01;valid=np.ones(len(times),bool)
    for end in ((18.,180.,600.) if case['mode']=='healthy' else (600.,)):
     for j,method in enumerate(s.METHODS):
      r=rows[case['seed'],case['mode'],case['amplitude'],end,method]
      got=reconstruct(times,labs[i,j],flgs[i,j],valid,case,end)
      for k,v in got.items():close(v,r[k])
      groups.setdefault(tuple(r[k] for k in s.KEYS),[]).append(r);checked+=1
   z.close()
 for key,rr in groups.items():
  rr.sort(key=lambda r:r['seed']);assert [r['seed'] for r in rr]==list(s.TEST_SEEDS)
 for row in summary['results']:
  rr=groups[tuple(row[k] for k in s.KEYS)]
  for metric in s.METRICS:
   count=sum(r[metric] for r in rr);assert count==row[metric+'_count'];n=len(rr);p=count/n;z=1.959963984540054
   center=(p+z*z/(2*n))/(1+z*z/n);half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
   close([max(0,center-half),min(1,center+half)],row[metric+'_wilson95'])
  delays=[r['delay'] for r in rr if r['first_correct']];close(None if not delays else np.median(delays),row['conditional_median_delay'])
  close(np.mean([r['restricted_delay_30s'] for r in rr]),row['mean_restricted_delay_30s'])
 rng=np.random.default_rng(45008);k=0
 for key in sorted(set(x[:-1] for x in groups)):
  ix=rng.integers(0,200,size=(5000,200));aa=groups[key+('cusum_rate',)]
  for cmp in ('v7_rms_frozen','rms_rate','mean_rate','cusum_universal'):
   bb=groups[key+(cmp,)]
   for metric in ('generic_false','wrong_any','within_5s','first_correct'):
    delta=np.array([int(a[metric])-int(b[metric]) for a,b in zip(aa,bb)])
    row=summary['paired'][k];close(delta.mean(),row['difference']);close(np.quantile(delta[ix].mean(axis=1),[.025,.975]),row['percentile95']);k+=1
 maxdiff=np.zeros(3);examples=0
 for fn in sorted(root.glob('example_*.npz')):
  z=np.load(fn);got,v,c=independent_scores(z)
  for j in range(3):maxdiff[j]=max(maxdiff[j],float(np.max(np.abs(got[:,j]-z['scores'][:,j]))))
  close(got,z['scores'],tol=1e-6);np.testing.assert_array_equal(v,z['valid']);np.testing.assert_array_equal(c,z['counts'])
  # Independently reconstruct all decision rules from the separate scores.
  g=(c<26).astype(int)
  opts=[(0,s.FROZEN_RMS),(0,cal['universal']['rms']),(0,np.asarray(cal['rate']['rms'])[g]),(1,np.asarray(cal['rate']['mean'])[g]),(2,cal['universal']['cusum']),(2,np.asarray(cal['rate']['cusum'])[g])]
  for j,(stream,threshold) in enumerate(opts):
   threshold=np.full(len(v),threshold) if np.isscalar(threshold) else threshold
   cross=(got[:,stream]>threshold[:,None])&v[:,None];lab=np.full(len(v),-1)
   lab[cross[:,0]&cross[:,1]&~cross[:,2]]=0;lab[cross[:,0]&cross[:,2]&~cross[:,1]]=1;lab[cross[:,1]&cross[:,2]&~cross[:,0]]=2
   np.testing.assert_array_equal(lab,z['labels'][j]);np.testing.assert_array_equal(cross.any(axis=1),z['flags'][j])
  examples+=1;z.close()
 report=dict(calibration_values_checked=21,records_checked=checked,rate_cells=len(groups),wilson_intervals=9*len(groups),paired_intervals=k,
  complete_packet_examples=examples,independent_score_max_abs_difference=dict(zip(s.STREAMS,maxdiff.tolist())),
  scope='Same-author independent postprocessor; all records reconstructed, representative packet paths separately recomputed. Not third-party human review.')
 print(json.dumps(report,indent=2));s.save(root/'verification.json',report)

if __name__=='__main__':main(Path(sys.argv[1]))
