import unittest
import numpy as np
import cusum_study as s

class Integrity(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.y,cls.sd=s.acquire(54880,'dense_iid',18.)
  cls.p=s.h.packets(cls.y,cls.sd,'dense_iid')
  cls.f=s.features(cls.p)
 def test_parent_hash(self):s.sources()
 def test_v7_quality_parity_dense_and_sparse(self):
  for profile in s.PROFILES:
   y,sd=s.acquire(54880,profile,18.);p=s.h.packets(y,sd,profile)
   f=s.features(p);old=s.h.raw_features(p)
   np.testing.assert_allclose(f[0][:,0],old[0][:,3],atol=1e-10,rtol=1e-10)
   np.testing.assert_array_equal(f[1],old[1][:,3]);np.testing.assert_array_equal(f[2],old[2])
 def test_direct_cusum_reference(self):
  y,sd=s.acquire(54881,'sparse_ar',18.);p=s.h.packets(y,sd,'sparse_ar')
  score,_,_=s.features(p);up=np.zeros(3);down=np.zeros(3);got=[]
  pairs=((0,1),(0,2),(1,2));prev=-1
  for t in range(len(y)):
   k=p.stamps[t,0]
   if k!=prev:
    for j,(a,b) in enumerate(pairs):
     d=y[k,a]-y[k,b];bound=p.offset_bound[a]+p.offset_bound[b]
     up[j]=max(0.,up[j]+d-.25-bound);down[j]=max(0.,down[j]-d-.25-bound)
    prev=k
   if t>=200 and (t-200)%20==0:got.append(np.maximum(up,down).copy())
  np.testing.assert_allclose(score[:,2],got,atol=1e-11)
 def test_prefix_causality(self):
  for n in (201,701,1201):
   p=self.cls_packet(self.p.values[:n],self.p.stamps[:n]);f=s.features(p)
   for a,b in zip(f,self.f):np.testing.assert_allclose(a,b[:len(a)],atol=1e-11)
 def cls_packet(self,y,stamps):return s.h.v5.Packets(y,stamps,self.p.sigma,self.p.quantum,self.p.offset_bound)
 def test_future_perturbation(self):
  y=self.p.values.copy();y[1201:,0]+=10
  f=s.features(self.cls_packet(y,self.p.stamps))
  np.testing.assert_allclose(f[0][:51],self.f[0][:51],atol=1e-11)
 def test_common_offset_invariance(self):
  p=self.cls_packet(self.p.values+4.,self.p.stamps)
  np.testing.assert_allclose(s.features(p)[0],self.f[0],atol=1e-10)
 def test_sign_reversal_invariance(self):
  np.testing.assert_allclose(s.features(self.cls_packet(-self.p.values,self.p.stamps))[0],self.f[0],atol=1e-10)
 def test_accumulator_counts_unique_not_holds(self):
  n=1001;t=np.arange(n);stamp=np.tile((t//50*50)[:,None],(1,3));y=np.zeros((n,3));y[:,0]=1.
  p=s.h.v5.Packets(y,stamp,np.full(3,.25),np.zeros(3),np.zeros(3))
  f=s.features(p);np.testing.assert_allclose(f[0][-1,2,:2],21*.75)
 def test_decision_grid(self):self.assertEqual(self.f[0].shape,(80,3,3))
 def test_counts_sparse(self):
  p=s.h.packets(self.y,self.sd,'sparse_iid');self.assertTrue(set(s.features(p)[2]).issubset({4,5}))
 def test_reject_nan(self):
  y=self.p.values.copy();y[0,0]=np.nan
  with self.assertRaises(ValueError):s.features(self.cls_packet(y,self.p.stamps))
 def test_reject_future_stamps(self):
  st=self.p.stamps.copy();st[0,0]=1
  with self.assertRaises(ValueError):s.features(self.cls_packet(self.p.values,st))
 def test_reject_repeated_stamp_mutation(self):
  p=s.h.packets(self.y,self.sd,'sparse_iid');y=p.values.copy();y[1,0]+=.1
  with self.assertRaises(ValueError):s.features(s.h.v5.Packets(y,p.stamps,p.sigma,p.quantum,p.offset_bound))
 def test_no_fault_truth_in_features(self):self.assertEqual(s.features.__code__.co_argcount,1)
 def test_seed_disjoint(self):
  sets=[set(range(54880,54890)),set(s.TEST_SEEDS),set(s.h.TEST_SEEDS)]+[set(x) for x in s.CAL_RANGES]
  for i,a in enumerate(sets):
   for b in sets[i+1:]:self.assertFalse(a&b)
 def test_rank(self):self.assertEqual(s.h.mb.calibration_threshold(np.arange(199.)),189.)
 def test_target_independent_record(self):
  tt=np.array([2.,3.,4.]);c=dict(mode='aux1_bias',onset=2.5,target=1)
  r=s.record(tt,np.array([-1,1,1]),np.array([0,1,1],bool),np.ones(3,bool),c,6.)
  self.assertTrue(r['first_correct']);self.assertEqual(r['delay'],.5)
 def test_earlier_wrong_not_success(self):
  c=dict(mode='primary_bias',onset=3.5,target=0)
  r=s.record(np.array([2.,3.,4.]),np.array([-1,2,0]),np.array([0,1,1],bool),np.ones(3,bool),c,6.)
  self.assertFalse(r['first_correct']);self.assertTrue(r['eventual_correct']);self.assertTrue(r['wrong_any'])
 def test_pulse_expiration(self):
  c=dict(mode='two_second_pulse',onset=2.5,target=0)
  r=s.record(np.array([2.,3.,5.]),np.array([-1,-1,0]),np.array([0,0,1],bool),np.ones(3,bool),c,6.)
  self.assertFalse(r['first_correct']);self.assertFalse(r['eventual_correct']);self.assertTrue(r['wrong_any'])
 def test_always_abstain(self):
  cal={'rate':{m:[100.,100.] for m in s.STREAMS},'universal':{m:100. for m in s.STREAMS}}
  l,f,_=s.decide(self.f,cal);self.assertTrue((l[-1]==-1).all());self.assertFalse(f[-1].any())
 def test_no_postalarm_restart(self):
  n=1001;st=np.tile(np.arange(n)[:,None],(1,3));y=np.zeros((n,3));y[:,0]=1.
  p=s.h.v5.Packets(y,st,np.full(3,.25),np.zeros(3),np.zeros(3));scores=s.features(p)[0]
  self.assertGreater(scores[-1,2,0],scores[0,2,0]);self.assertAlmostEqual(scores[-1,2,0],1001*.75)
 def test_stress_marginal_metadata(self):
  a,sd=s.acquire(54882,'dense_ar99',18.);self.assertEqual(sd[0],.75);self.assertTrue(np.isfinite(a).all())
 def test_same_waveform_cancels(self):
  waveform=np.sin(np.arange(len(self.y))*.01)*100
  p=self.cls_packet(self.p.values+waveform[:,None],self.p.stamps)
  np.testing.assert_allclose(s.features(p)[0],self.f[0],atol=1e-9)
 def test_small_shift_below_slack_no_growth_in_noiseless_case(self):
  n=1001;st=np.tile(np.arange(n)[:,None],(1,3));y=np.zeros((n,3));y[:,0]=.125
  p=s.h.v5.Packets(y,st,np.full(3,.25),np.zeros(3),np.zeros(3))
  self.assertTrue((s.features(p)[0][:,2]==0).all())

if __name__=='__main__':unittest.main(verbosity=2)
