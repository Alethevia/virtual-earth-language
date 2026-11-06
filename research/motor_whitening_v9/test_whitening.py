import unittest
import numpy as np
from scipy.signal import lfilter
import whitening as w

class Integrity(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.models={}
  for i,p in enumerate(w.PROFILES):
   y,sd=w.old.acquire(64880+i,p,12.)
   packets=w.old.make_packets(y,sd,p,dict(mode='healthy',onset=None))
   stamp,d,b,v=w.common(packets);dt=float(np.diff(stamp)[0])*.01
   m=w.fit_ar([d],20 if dt<.1 else 1);m['dt']=dt
   cls.models[p]=m
  cls.y,cls.sd=w.old.acquire(64890,'dense_ar',12.)
  cls.p=w.old.make_packets(cls.y,cls.sd,'dense_ar',dict(mode='primary_bias',amplitude=.5,onset=6.,sign=1,target=0))
  cls.model=cls.models['dense_ar'];cls.f=w.features(cls.p,cls.model)
 def test_parent_hash(self):self.assertEqual(w.sources()['cusum_study.py'],w.PARENT_HASH)
 def test_seed_separation(self):
  xs=[set(range(64800,64999)),*[set(x) for x in w.TRAIN_RANGES],*[set(x) for x in w.CAL_RANGES],set(w.TEST_SEEDS)]
  for j,x in enumerate(xs):
   for y in xs[j+1:]:self.assertFalse(x&y)
 def test_causal_prefix(self):
  p=self.p
  for n in (501,751,1001):
   q=w.old.h.v5.Packets(p.values[:n],p.stamps[:n],p.sigma,p.quantum,p.offset_bound)
   t,s,v=w.features(q,self.model);np.testing.assert_allclose(s,self.f[1][:len(t)],atol=2e-10)
 def test_future_perturbation(self):
  p=self.p;val=p.values.copy();val[801:,0]+=100
  q=w.old.h.v5.Packets(val,p.stamps,p.sigma,p.quantum,p.offset_bound)
  t,s,v=w.features(q,self.model);np.testing.assert_allclose(s[t<8],self.f[1][t<8],atol=1e-10)
 def test_direct_scans(self):
  stamp,d,B,var=w.common(self.p);t,s,valid=self.f;dt=self.model['dt']
  for j in range(3):
   phi=np.array(self.model['phi'][j]);p=len(phi);sd=self.model['innovation_sd'][j];marg=self.model['marginal_sd'][j]
   e=np.array([d[z,j]-sum(phi[l-1]*d[z-l,j] for l in range(1,p+1) if z>=l) for z in range(len(d))])
   g=np.r_[1.,1-np.cumsum(phi)];ginf=g[-1]
   for row in (5,20,35):
    k=int(np.searchsorted(stamp,round(t[row]/.01),side='right'))-1
    vals=[0.,0.,0.]
    for n in sorted(set(max(p,int(np.ceil(sec/dt))) for sec in w.WINDOWS)):
     if k<n-1+p:continue
     start=k+1-n;ww=np.r_[g[:p],np.full(n-p,ginf)]
     raw=max(0.,abs(d[start:k+1,j].sum())-n*B[j])/(marg*np.sqrt(n))
     naive=max(0.,abs(e[start:k+1].sum())-n*B[j]*abs(ginf))/(sd*np.sqrt(n))
     match=max(0.,abs(ww@e[start:k+1])-B[j]*abs(ginf*ww.sum()))/(sd*np.linalg.norm(ww))
     vals=np.maximum(vals,[raw,naive,match])
    np.testing.assert_allclose(s[row,2:5,j],vals,atol=1e-10)
 def test_filter_applied_to_step(self):
  phi=np.array(self.model['phi'][0]);n=len(phi);x=np.r_[np.zeros(40),np.ones(n+10)]
  out=lfilter(np.r_[1.,-phi],[1.],x)
  np.testing.assert_allclose(out[40:40+n+1],np.r_[1.,1-np.cumsum(phi)],atol=1e-14)
 def test_dense_rms_parity(self):
  _,s,v=w.features(self.p,self.model);old,ov,_=w.old.features(self.p)
  np.testing.assert_allclose(s[:,0],old[:,0],atol=1e-10)
 def test_sparse_rms_parity(self):
  y,sd=w.old.acquire(64894,'sparse_iid',12.);p=w.old.make_packets(y,sd,'sparse_iid',dict(mode='healthy',onset=None))
  _,s,_=w.features(p,self.models['sparse_iid']);old,_,_=w.old.features(p)
  np.testing.assert_allclose(s[:,0],old[:,0],atol=1e-10)
 def test_cusum_parity(self):
  old,_,_=w.old.features(self.p);np.testing.assert_allclose(self.f[1][:,5],old[:,2],atol=1e-10)
 def test_sparse_distinct_packets(self):
  y,sd=w.old.acquire(64895,'sparse_iid',12.);p=w.old.make_packets(y,sd,'sparse_iid',dict(mode='healthy',onset=None))
  stamp,_,_,_=w.common(p);self.assertEqual(len(stamp),24);np.testing.assert_array_equal(np.diff(stamp),50)
 def test_reject_wrong_rate(self):
  with self.assertRaises(ValueError):w.features(self.p,self.models['sparse_iid'])
 def test_finite(self):self.assertTrue(np.isfinite(self.f[1]).all())
 def test_no_fault_metadata_argument(self):
  import inspect
  self.assertEqual(list(inspect.signature(w.features).parameters),['p','model'])
 def test_always_abstain(self):
  lab,flag=w.labels(self.f[1],self.f[2],np.ones(5),.01)
  self.assertTrue((lab[-1]==-1).all());self.assertFalse(flag[-1].any())
 def test_common_signal_cancels(self):
  p=self.p;val=p.values+np.arange(len(p.values))[:,None]*.02
  q=w.old.h.v5.Packets(val,p.stamps,p.sigma,p.quantum,p.offset_bound)
  np.testing.assert_allclose(w.features(q,self.model)[1],self.f[1],atol=1e-10)
 def test_first_wrong_not_later_success(self):
  t=np.array([2.,10.,12.]);lab=np.array([1,0,0]);flags=np.ones(3,bool)
  case=dict(onset=9.,target=0,mode='primary_bias')
  r=w.old.record(t,lab,flags,flags,case,20.)
  self.assertFalse(r['first_correct']);self.assertTrue(r['eventual_correct'])
 def test_pre_alarm_not_detection(self):
  t=np.array([2.,10.,12.]);lab=np.array([0,0,0]);flags=np.ones(3,bool)
  r=w.old.record(t,lab,flags,flags,dict(onset=9.,target=0,mode='primary_bias'),20.)
  self.assertFalse(r['first_correct']);self.assertTrue(r['pre_fault_unique'])
 def test_no_online_model_change(self):
  import json
  before=json.dumps(self.model,sort_keys=True);w.features(self.p,self.model)
  self.assertEqual(before,json.dumps(self.model,sort_keys=True))
 def test_fit_training_only(self):
  x=np.random.default_rng(64896).normal(size=(200,3));m=w.fit_ar([x],1)
  self.assertEqual(m['training_samples'],200)
 def test_rank(self):self.assertEqual(w.old.h.mb.calibration_threshold(np.arange(199.)),189.)
 def test_pulse_not_counted_after_recovery(self):
  flag=np.ones(1,bool)
  r=w.old.record(np.array([12.]),np.array([0]),flag,flag,dict(onset=9.,target=0,mode='two_second_pulse'),20.)
  self.assertFalse(r['first_correct']);self.assertTrue(r['wrong_any'])
 def test_train_offset_invariance(self):
  x=np.random.default_rng(64898).normal(size=(500,3));a=w.fit_ar([x],3);b=w.fit_ar([x+3.],3)
  np.testing.assert_allclose(a['phi'],b['phi'],atol=1e-14)
 def test_duplicate_mutation_rejected(self):
  y,sd=w.old.acquire(64895,'sparse_iid',12.);p=w.old.make_packets(y,sd,'sparse_iid',dict(mode='healthy',onset=None));p.values[1,0]+=1.
  with self.assertRaises(ValueError):w.common(p)
 def test_training_orders_fixed(self):self.assertEqual([m['order'] for m in self.models.values()],[20,1,20,1])

if __name__=='__main__':unittest.main(verbosity=2)
