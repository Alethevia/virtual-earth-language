"""Development-only integrity tests. No calibration/holdout seeds used."""
import unittest
from dataclasses import replace
import numpy as np
import telemetry as t

class Integrity(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.p,_,_=t.generate(30990,'bias_witness_delay');cls.f=t.features(cls.p)
 def test_parent_hashes(self):
  self.assertEqual(t.source_hashes()['experiment.py'],'15eddca6510854e8f791d14aab6b7b13e3566909c078314dff6e6c09947a9e3d')
 def test_original_packets_and_raw_scores(self):
  for condition in ('healthy','bias','healthy_nonlinear','healthy_high_noise','two_aux_common_bias'):
   p,_,_=t.generate(30991,condition);y,_,_=t.v4.generate(30991,condition,False)
   np.testing.assert_array_equal(p.values,y[:,2:])
   _,ref,_=t.v4.pair_features(y[:,2:]);np.testing.assert_allclose(t.features(p)[0][:,0],ref,atol=1e-9)
 def test_prefix_causality(self):
  for n in (201,701,1201):
   got=t.features(replace(self.p,values=self.p.values[:n],stamps=self.p.stamps[:n]))
   for a,b in zip(got,self.f):np.testing.assert_array_equal(a,b[:len(a)])
 def test_future_values(self):
  y=self.p.values.copy();y[1201:]+=100
  f=t.features(replace(self.p,values=y))
  for a,b in zip(f,self.f):np.testing.assert_array_equal(a[:51],b[:51])
 def test_common_constant_offset_invariance(self):
  q=replace(self.p,values=self.p.values+9.)
  np.testing.assert_allclose(t.features(q)[0],self.f[0],atol=1e-12)
 def test_slow_packets_not_counted_repeatedly(self):
  p,_,_=t.generate(30991,'healthy_slow_reporting');f=t.features(p)
  self.assertTrue(set(f[2]).issubset({4,5}));self.assertTrue(f[1][:,2].all())
 def test_delayed_packet_matches_old_signal(self):
  p,_,_=t.generate(30991,'healthy_witness_delay');base,_,_=t.generate(30991,'healthy')
  np.testing.assert_array_equal(p.values[10:,1:],base.values[:-10,1:])
  np.testing.assert_array_equal(p.stamps[10:,1],np.arange(1790))
 def test_no_common_times_not_success(self):
  p,_,_=t.generate(30991,'bias_asynchronous');f=t.features(p)
  self.assertFalse(f[1][:,2:].any());self.assertTrue(np.all(f[0][:,2:]==0))
 def test_dropout_becomes_insufficient(self):
  p,_,_=t.generate(30991,'bias_dropout');f=t.features(p)
  self.assertFalse(f[1][-1,2]);self.assertTrue(f[1][0,2])
 def test_quantization_bound(self):
  p,_,_=t.generate(30991,'healthy_quantized');base,_,_=t.generate(30991,'healthy')
  self.assertLessEqual(abs(p.values[:,0]-base.values[:,0]).max(),1.)
 def test_quality_score_decreases_with_declared_resolution(self):
  p,_,_=t.generate(30991,'bias');a=t.features(p)[0][:,3]
  b=t.features(replace(p,quantum=np.array([20.,0.,0.])))[0][:,3]
  self.assertTrue(np.all(b<=a+1e-12))
 def test_no_truth_input(self):
  self.assertEqual(set(t.Packets.__dataclass_fields__),{'values','stamps','sigma','quantum','offset_bound'})
  with self.assertRaises(ValueError):t.features(replace(self.p,values=np.ones((1800,8))))
 def test_duplicate_packet_mutation_rejected(self):
  p,_,_=t.generate(30991,'healthy_slow_reporting');y=p.values.copy();y[1,0]+=1
  with self.assertRaises(ValueError):t.features(replace(p,values=y))
 def test_future_stamp_rejected(self):
  s=self.p.stamps.copy();s[1,0]=100
  with self.assertRaises(ValueError):t.features(replace(self.p,stamps=s))
 def test_negative_quality_rejected(self):
  with self.assertRaises(ValueError):t.features(replace(self.p,quantum=np.array([-1.,0,0])))
 def test_bad_nan_rejected(self):
  y=self.p.values.copy();y[50,0]=np.nan
  with self.assertRaises(ValueError):t.features(replace(self.p,values=y))
 def test_decreasing_stamp_rejected(self):
  s=self.p.stamps.copy();s[50,0]=40
  with self.assertRaises(ValueError):t.features(replace(self.p,stamps=s))
 def test_integer_stamps_required(self):
  with self.assertRaises(ValueError):t.features(replace(self.p,stamps=self.p.stamps.astype(float)))
 def test_seed_separation(self):
  pools=[set(range(30000,31000)),set(t.CAL_SEEDS),set(t.TEST_SEEDS),set(range(28000,28100))]
  for i,a in enumerate(pools):
   for b in pools[i+1:]:self.assertFalse(a&b)
 def test_finite_features(self):self.assertTrue(np.isfinite(self.f[0]).all())
 def test_determinism(self):
  p,_,_=t.generate(30990,'bias_witness_delay')
  np.testing.assert_array_equal(p.values,self.p.values)
  for a,b in zip(t.features(p),self.f):np.testing.assert_array_equal(a,b)
 def test_calibration_rank(self):self.assertEqual(t.v4.v3.mb.calibration_threshold(np.arange(199.)),189.)
 def test_always_abstain_no_detection(self):
  d=t.decisions(self.f,{s:1. for s in t.STREAMS})['always_abstain']
  self.assertTrue((d[0]==-1).all());self.assertFalse(d[1].any())
 def test_pre_alarm_not_detection(self):
  times=np.array([2.,10.]);meta={'primary_onset':9.,'anomaly_onset':9.,'single_target':0}
  r=t.record(times,np.array([0,0]),np.array([True,True]),np.ones(2,bool),meta)
  self.assertFalse(r['primary_valid']);self.assertTrue(r['primary_early'])
 def test_standard_alignment_equal_long_window(self):
  p,_,_=t.generate(30991,'healthy');s=t.features(p)[0]
  np.testing.assert_allclose(s[:,1],s[:,2],atol=1e-14)

if __name__=='__main__':unittest.main(verbosity=2)
