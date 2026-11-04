"""Integrity tests use development/test-only seeds, never the calibration/holdout seeds."""
import unittest
import numpy as np
from scipy.optimize import lsq_linear
import study as s
from box_solver import box_fit

class Integrity(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.trace,_,_=s.simulate(17891,'bias_late_shift',True)
  cls.y=cls.trace[:,[5,7,6]];cls.raw,cls.scores=s.diagnose(cls.y)
 def test_unprobed_simulator_matches_v2_all12(self):
  for c in s.v2.CORE+s.v2.STRESS:
   tr,on,_=s.simulate(17890,c,False);ref,oldon=s.v2.episode(17890,c)
   np.testing.assert_allclose(tr,ref,atol=1e-12,rtol=1e-13);self.assertEqual(on,oldon)
 def test_causal_prefix(self):
  for n in (201,701,1101):
   raw,sc=s.diagnose(self.y[:n]);np.testing.assert_allclose(raw,self.raw[:len(raw)],atol=1e-12)
   np.testing.assert_allclose(sc,self.scores[:len(sc)],atol=1e-12)
 def test_future_perturbation(self):
  y=self.y.copy();y[1201:]+=3;raw,sc=s.diagnose(y)
  keep=raw[:,0]<=12.;np.testing.assert_allclose(sc[keep],self.scores[keep],atol=1e-12)
 def test_true_states_not_input(self):
  tr=self.trace.copy();tr[:,[2,3,4]]=-999.
  np.testing.assert_array_equal(s.diagnose(tr[:,[5,7,6]])[1],self.scores)
 def test_reject_full_trace(self):
  with self.assertRaises(ValueError):s.diagnose(self.trace)
 def test_reject_nan(self):
  y=self.y.copy();y[5,0]=np.nan
  with self.assertRaises(ValueError):s.diagnose(y)
 def test_reject_short(self):
  with self.assertRaises(ValueError):s.diagnose(self.y[:100])
 def test_solver_against_scipy(self):
  rng=np.random.default_rng(17888)
  for d in (3,4):
   for k in range(200):
    A=rng.normal(size=(20,d))*rng.uniform(.01,5,d);y=rng.normal(size=20)
    if k%7==0:A[:,1]=A[:,0]
    lo=np.full(d,-1.);hi=np.full(d,1.)
    rms,_,_=box_fit(A,y,lo,hi);ref=lsq_linear(A,y,bounds=(lo,hi),method='bvls',tol=1e-10)
    self.assertLess(abs(rms-np.sqrt(np.mean((A@ref.x-y)**2))),1e-8)
 def test_switch_nesting(self):self.assertTrue(np.all(self.raw[:,2]<=self.raw[:,1]+1e-12))
 def test_bias_nesting(self):self.assertTrue(np.all(self.raw[:,3]<=self.raw[:,1]+1e-8))
 def test_all_finite(self):self.assertTrue(np.isfinite(self.scores).all())
 def test_no_answer_control(self):self.assertTrue(np.all(self.scores[:,-1]==0))
 def test_decision_grid(self):np.testing.assert_allclose(self.raw[:,0],np.arange(2.,17.81,.2),atol=1e-12)
 def test_calibration_rank(self):self.assertEqual(s.mb.calibration_threshold(np.arange(159.)),151.)
 def test_seed_separation(self):
  sets=[set(range(17000,17900)),set(s.CAL_SEEDS),set(s.TEST_SEEDS),set(range(11000,11200)),set(range(12000,12100))]
  for j,a in enumerate(sets):
   for b in sets[j+1:]:self.assertFalse(a&b)
 def test_probe_bounded_and_before2_unchanged(self):
  for c in ('healthy','bias_late_shift'):
   tr,_,base=s.simulate(17892,c,True);old,_,_=s.simulate(17892,c,False)
   np.testing.assert_array_equal(tr[:200],old[:200]);self.assertLessEqual(np.abs(tr[:,5]).max(),12.)
   np.testing.assert_allclose(np.abs(tr[200:,1]-base[200:]),8.)
 def test_deterministic(self):np.testing.assert_array_equal(s.simulate(17891,'bias_late_shift',True)[0],self.trace)
 def test_channel_negative_controls_do_not_change_actual_states(self):
  clean,_,_=s.simulate(17893,'healthy',True)
  for c in ('healthy_voltage_bias','healthy_current_bias'):
   tr,on,_=s.simulate(17893,c,True);self.assertIsNone(on)
   np.testing.assert_array_equal(tr[:,[0,1,2,3,4,6]],clean[:,[0,1,2,3,4,6]])
 def test_exact_steady_ambiguity(self):
  # Two distinct admissible plants/fault explanations, identical measured u,i,w.
  worlds=[(s.mb.Motor(R=2.),np.array([2.,40.]),.02,0.),
          (s.mb.Motor(R=2.15),np.array([2.,34.]),.032,6.)]
  observations=[]
  for motor,x,load,bias in worlds:
   A,B=motor.continuous();np.testing.assert_allclose(A@x+B@np.array([6.,load]),0.,atol=1e-12)
   ad,bd=s.mb.discretize(A,B);np.testing.assert_allclose(ad@x+bd@np.array([6.,load]),x,atol=1e-12)
   observations.append(np.tile([6.,x[0],x[1]+bias],(1800,1)))
  np.testing.assert_array_equal(observations[0],observations[1])
  np.testing.assert_array_equal(s.diagnose(observations[0])[1],s.diagnose(observations[1])[1])

if __name__=='__main__':unittest.main(verbosity=2)
