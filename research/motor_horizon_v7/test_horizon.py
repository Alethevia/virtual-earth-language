import unittest, math
import numpy as np
import horizon as h

class Integrity(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.y,cls.sd=h.acquired(45880,'dense_iid',18.)
  cls.p=h.packets(cls.y,cls.sd,'dense_iid');cls.f=h.raw_features(cls.p)
 def test_parent_sources(self):self.assertEqual(h.sources()['calibration_study.py'],h.EXPECTED_PARENT)
 def test_seed_disjoint(self):
  sets=[set(r) for r in h.CAL_RANGES]+[set(h.TEST_SEEDS),set(range(45880,45890))]
  for j,a in enumerate(sets):
   for b in sets[j+1:]:self.assertFalse(a&b)
 def test_rank(self):self.assertEqual(h.v6.rank_threshold(np.arange(199.)),189.)
 def test_prefix_generation(self):
  for profile in h.PROFILES:
   a,sd=h.acquired(45881,profile,20.);b,_=h.acquired(45881,profile,18.)
   np.testing.assert_array_equal(a[:1800],b)
 def test_plant_prefix(self):np.testing.assert_array_equal(h.background(45882,1800),h.background(45882,3000)[:1800])
 def test_plant_controller_parity(self):
  refs=np.linspace(25,110,300);loads=np.full(300,.02);A,B=h.nominal_dynamics()
  actual=h.plant_loop(A,B,refs,loads);x=np.zeros(2);pi=h.mb.PI();expected=[]
  for r,ld in zip(refs,loads):
   u=pi.step(r-x[1]);expected.append([x[1],x[0],u]);x=A@x+B@np.array([u,ld])
  np.testing.assert_allclose(actual,expected,rtol=1e-12,atol=1e-10)
 def test_voltage_limit(self):self.assertLessEqual(np.abs(h.background(45882,6000)[:,2]).max(),12.)
 def test_downstream_fault_preserves_other_channels(self):
  p=h.packets(self.y,self.sd,'dense_iid',.5,10.,1)
  np.testing.assert_array_equal(p.values[:1000],self.p.values[:1000])
  np.testing.assert_array_equal(p.values[:,1:],self.p.values[:,1:])
 def test_held_fault_starts_at_acquisition(self):
  p=h.packets(self.y,self.sd,'sparse_iid',1.,10.13,1);base=h.packets(self.y,self.sd,'sparse_iid')
  np.testing.assert_array_equal(p.values[:1050],base.values[:1050]);self.assertAlmostEqual(p.values[1050,0]-base.values[1050,0],1.)
 def test_packet_duplicates_not_multiplied(self):
  f=h.raw_features(h.packets(self.y,self.sd,'sparse_iid'))
  self.assertTrue(np.isin(f[2],[4,5]).all());self.assertTrue(f[1][:,3].all())
 def test_dense_count(self):self.assertTrue((self.f[2]==201).all())
 def test_causal_prefix(self):
  p=self.p
  for stop in (201,1001):
   pp=h.v5.Packets(p.values[:stop],p.stamps[:stop],p.sigma,p.quantum,p.offset_bound)
   got=h.raw_features(pp)
   for j in range(4):np.testing.assert_array_equal(got[j],self.f[j][:len(got[0])])
 def test_no_future_reading(self):
  y=self.y.copy();y[1201:]+=999.
  q=h.raw_features(h.packets(y,self.sd,'dense_iid'))
  np.testing.assert_array_equal(q[0][:51],self.f[0][:51])
 def test_common_waveform_cancels(self):
  y=self.y.copy();y+=np.linspace(0,100,len(y))[:,None]
  q=h.raw_features(h.packets(y,self.sd,'dense_iid'))
  np.testing.assert_allclose(q[0][:,3],self.f[0][:,3],atol=1e-12)
 def test_common_fault_invisible(self):
  y=self.y.copy();y[1000:]+=6.
  q=h.raw_features(h.packets(y,self.sd,'dense_iid'))
  np.testing.assert_allclose(q[0][:,3],self.f[0][:,3],atol=1e-12)
 def test_direct_score(self):
  p=self.p
  for row,t in enumerate(range(200,1800,20)):
   for j,(a,b) in enumerate(((0,1),(0,2),(1,2))):
    d=np.abs(p.values[t-200:t+1,a]-p.values[t-200:t+1,b])
    x=np.maximum(0,d-p.offset_bound[a]-p.offset_bound[b])
    ref=np.sqrt(np.mean(x*x)/(p.sigma[a]**2+p.sigma[b]**2))
    self.assertAlmostEqual(self.f[0][row,3,j],ref,places=12)
 def test_decision_grid(self):self.assertEqual(len(self.f[0]),80)
 def test_invalid_bias(self):
  with self.assertRaises(ValueError):h.packets(self.y,self.sd,'dense_iid',-1.)
 def test_invalid_packets(self):
  p=h.packets(self.y,self.sd,'dense_iid');p.values[0,0]=np.nan
  with self.assertRaises(ValueError):h.raw_features(p)
 def test_early_wrong_disqualifies(self):
  times=np.array([2.,10.,11.]);l=np.array([1,0,0]);f=l>=0
  r=h.record(times,l,f,np.ones(3,bool),10.,18.)
  self.assertFalse(r['first_correct']);self.assertTrue(r['eventual_correct']);self.assertTrue(r['wrong_any'])
 def test_censoring(self):
  r=h.record(np.array([2.,10.,11.]),np.array([-1,-1,0]),np.array([False,False,True]),np.ones(3,bool),10.,18.)
  self.assertTrue(r['first_correct']);self.assertEqual(r['first_correct_delay'],1.);self.assertTrue(r['within_5s'])
 def test_abstain_not_success(self):
  l,f,a=h.decisions(self.f,{'short':2.,'long':3.})
  self.assertTrue((l[-1]==-1).all());self.assertFalse(f[-1].any())
  r=h.record(np.arange(200,1800,20)*.01,l[-1],f[-1],a,10.,18.);self.assertFalse(r['first_correct'])
 def test_horizon_event_nested(self):
  l=np.full(2990,-1);f=np.zeros(2990,bool);f[100]=True;l[100]=0;tt=np.arange(200,60000,20)*.01
  vals=[h.record(tt,l,f,np.ones(len(l),bool),None,end)['generic_false'] for end in (18.,180.,600.)]
  self.assertEqual(vals,[False,True,True])
 def test_count_not_independence(self):
  y,sd=h.acquired(45883,'dense_ar',18.);f=h.raw_features(h.packets(y,sd,'dense_ar'))
  self.assertTrue((f[2]==201).all());self.assertEqual(sd[0],.75)
 def test_determinism(self):np.testing.assert_array_equal(h.acquired(45880,'dense_iid',18.)[0],self.y)

if __name__=='__main__':unittest.main(verbosity=2)
