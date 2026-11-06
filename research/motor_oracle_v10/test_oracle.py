"""Integrity tests use only development seeds 79900-79920, no calibration/test paths."""
import sys,unittest
from pathlib import Path
import numpy as np
from scipy.linalg import cho_solve,cho_factor
from scipy.stats import norm
import oracle as o

class Integrity(unittest.TestCase):
 def test_parent_hashes(self):o.sources()
 def test_covariance_positive(self):
  for p in o.PROFILES:
   _,_,a,q=o.config(p)
   for init in ('stationary','perfect_state'):
    np.linalg.cholesky(o.covariance(12,a,q,.0625,init))
 def test_recurrence_matches_dense_solve(self):
  for p in o.PROFILES:
   _,_,a,q=o.config(p)
   for n in (1,5,17,101):
    for r in (o.VAR_WHITE_PRIMARY,o.VAR_WHITE_CONTRAST):
     for init in ('stationary','perfect_state'):
      C=o.covariance(n,a,q,r,init);one=np.ones(n)
      direct=one@cho_solve(cho_factor(C),one)
      value=o.info_recurrence(n,a,q,r,init)[0]
      self.assertAlmostEqual(value/direct,1.,places=10)
 def test_white_limit(self):
  for n in (1,10,500):self.assertAlmostEqual(o.info_recurrence(n,0,0,.0625)[0],n/.0625)
 def test_perfect_state_more_information(self):
  for p in o.PROFILES:
   _,_,a,q=o.config(p)
   self.assertGreaterEqual(o.info_recurrence(10,a,q,.0625,'perfect_state')[0]+1e-10,o.info_recurrence(10,a,q,.0625,'stationary')[0])
 def test_true_speed_more_information(self):
  for p in o.PROFILES:
   _,_,a,q=o.config(p)
   self.assertGreaterEqual(o.info_recurrence(10,a,q,.0625,'perfect_state')[0],o.info_recurrence(10,a,q,.09375,'perfect_state')[0])
 def test_more_observations_not_less_information(self):
  for p in o.PROFILES:
   _,_,a,q=o.config(p);values=[o.info_recurrence(n,a,q,.0625,'perfect_state')[0] for n in range(1,50)]
   self.assertTrue(np.all(np.diff(values)>0))
 def test_np_power_zero_shift_equals_alpha(self):
  for alpha in o.ALPHAS:self.assertAlmostEqual(float(norm.cdf(-norm.isf(alpha))),alpha)
 def test_covariance_conditioning_rank_one(self):
  a=.9;q=.5;n=20
  difference=o.covariance(n,a,q,.0625)-o.covariance(n,a,q,.0625,'perfect_state')
  self.assertEqual(np.linalg.matrix_rank(difference,tol=1e-10),1)
 def test_five_seconds_ten_sparse_samples(self):
  rng=np.random.default_rng(79900)
  grid=np.arange(0,600,.5)
  for onset in rng.uniform(300,330,100):self.assertEqual(int(((grid>=onset)&(grid<=onset+5)).sum()),10)
 def test_parent_noise_reduction(self):
  sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'motor_cusum_v8'))
  import cusum_study as parent
  for j,p in enumerate(o.PROFILES):
   y,sd=parent.acquire(79901+j,p,3.)
   offset=np.r_[0.,np.random.default_rng(79901+j+10000001).uniform(-.03,.03,2)]
   actual=y[:,0]-.5*(y[:,1]+y[:,2])+.5*(offset[1]+offset[2])
   step,*_=o.config(p)
   np.testing.assert_allclose(actual[::step],o.generate_contrast(79901+j,p,3.),atol=5e-14,rtol=1e-12)
 def test_scan_direct_convolution(self):
  x=np.random.default_rng(79908).normal(size=1200)
  for p in ('dense_ar','sparse_ar'):
   actual=o.scan(x,p)
   direct=np.stack([np.convolve(x,w[::-1],mode='valid') for w in o.weights(p)])
   np.testing.assert_allclose(actual,direct,atol=1e-11,rtol=1e-11)
 def test_scan_prefix_causality(self):
  x=np.random.default_rng(79909).normal(size=2000)
  for p in ('dense_ar','sparse_ar'):
   full=o.scan(x,p);prefix=o.scan(x[:1000],p)
   np.testing.assert_allclose(prefix,full[:,:prefix.shape[1]],atol=1e-11,rtol=1e-11)
 def test_future_does_not_change_scores(self):
  x=np.random.default_rng(79910).normal(size=2000);y=x.copy();y[1000:]+=100
  for p in ('dense_ar','sparse_ar'):
   stop=1000-o.weights(p).shape[1]+1
   np.testing.assert_allclose(o.scan(x,p)[:,:stop],o.scan(y,p)[:,:stop],atol=1e-10,rtol=1e-10)
 def test_null_variance_one(self):
  for p in o.PROFILES:
   _,_,a,q=o.config(p);w=o.weights(p);C=o.covariance(w.shape[1],a,q,o.VAR_WHITE_CONTRAST)
   for ww in w:self.assertAlmostEqual(ww@C@ww,1.,places=10)
 def test_gls_no_worse_fixed_look_mean(self):
  for p in o.PROFILES:
   w=o.weights(p);self.assertGreaterEqual(w[1].sum()+1e-10,w[0].sum())
 def test_fault_response_linearity(self):
  x=np.random.default_rng(79911).normal(size=1600);step=(np.arange(len(x))>700).astype(float)
  np.testing.assert_allclose(o.scan(x+.5*step,'dense_ar'),o.scan(x,'dense_ar')+.5*o.scan(step,'dense_ar'),atol=1e-11)
 def test_pre_alarm_never_success(self):
  d=o.outcomes(np.arange(10.),np.array([0,1,0,0,0,0,1,0,0,0],bool),5.)
  self.assertFalse(d['first_alarm_valid']);self.assertFalse(d['within_5s']);self.assertTrue(d['pre_fault_alarm'])
 def test_exact_deadline(self):
  self.assertTrue(o.outcomes(np.array([10.]),np.array([True]),5.)['within_5s'])
  self.assertFalse(o.outcomes(np.array([10.01]),np.array([True]),5.)['within_5s'])
 def test_no_alarm_not_detection(self):self.assertFalse(o.outcomes(np.arange(10.),np.zeros(10,bool),5.)['first_alarm_valid'])
 def test_invalid_input_rejected(self):
  with self.assertRaises(ValueError):o.scan(np.array([1.,float('nan')]),'dense_iid')
  with self.assertRaises(ValueError):o.info_recurrence(10,1.,.5,.1)
 def test_seed_groups_disjoint(self):
  groups=[set(range(s,s+o.CAL_N)) for s in o.CAL_STARTS]+[set(range(o.TEST_START,o.TEST_START+o.TEST_N)),set(range(79900,79921))]
  for i,a in enumerate(groups):
   for b in groups[i+1:]:self.assertFalse(a&b)
 def test_parent_test_seeds_not_reused(self):
  new=set(range(o.TEST_START,o.TEST_START+o.TEST_N))
  for s in (50000,61000,70000):self.assertFalse(new&set(range(s,s+200)))
 def test_no_posthoc_model_selection(self):self.assertEqual(o.WINDOW,5.)

if __name__=='__main__':unittest.main(verbosity=2)
