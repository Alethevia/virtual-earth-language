import unittest
import numpy as np
import experiment as e

class Integrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.y,cls.meta,_=e.generate(23990,'stuck',True)
        cls.times,cls.feat=e.features(cls.y)
    def test_parent_hashes(self):
        self.assertEqual(e.v3.source_hashes(),e.EXPECTED_PARENT)
    def test_original_observations_preserved(self):
        for c in e.v3.CONDITIONS:
            y,m,_=e.generate(23991,c,False);tr,on,_=e.v3.simulate(23991,c,False)
            np.testing.assert_array_equal(y[:,:3],tr[:,[5,7,6]])
            self.assertEqual(m['primary_onset'],on)
    def test_rms_independent_direct(self):
        times,d,flat=e.pair_features(self.y[:,2:])
        ref=np.array([[np.sqrt(np.mean((self.y[k-40:k+1,a]-self.y[k-40:k+1,b])**2))
                       for a,b in ((2,3),(2,4),(3,4))] for k in range(200,len(self.y),20)])
        np.testing.assert_allclose(d,ref,atol=1e-10,rtol=1e-10)
    def test_causal_prefix(self):
        for n in (201,701,1101):
            times,f=e.features(self.y[:n]);np.testing.assert_allclose(f,self.feat[:len(f)],atol=1e-10)
    def test_future_perturbation(self):
        y=self.y.copy();y[1201:]+=10
        times,f=e.features(y);mask=times<=12
        np.testing.assert_allclose(f[mask],self.feat[mask],atol=1e-10)
    def test_no_true_state_detector_input(self):
        with self.assertRaises(ValueError):e.features(np.zeros((1800,8)))
    def test_reject_nan(self):
        y=self.y.copy();y[0,4]=np.nan
        with self.assertRaises(ValueError):e.features(y)
    def test_reject_short(self):
        with self.assertRaises(ValueError):e.features(self.y[:200])
    def test_pair_permutation(self):
        th={'v3':1.,'dual':1.,'triple':1.}
        for ch in range(3):
            a=np.zeros((401,3));a[:,ch]=5
            _,pairs,flat=e.pair_features(a)
            f=np.c_[np.zeros(len(pairs)),pairs,flat]
            labels,_=e.decisions(f,th)['triple_consensus']
            np.testing.assert_array_equal(labels,np.full(len(labels),ch))
    def test_two_bad_witnesses_fool_majority(self):
        a=np.tile([0.,5.,5.],(401,1));_,pairs,flat=e.pair_features(a)
        f=np.c_[np.zeros(len(pairs)),pairs,flat]
        labels,_=e.decisions(f,{'v3':1,'dual':1,'triple':1})['triple_consensus']
        self.assertTrue(np.all(labels==0))
    def test_common_mode_invariance(self):
        a=self.y[:,2:].copy();_,first,_=e.pair_features(a)
        a+=7;_,second,_=e.pair_features(a)
        np.testing.assert_allclose(first,second,atol=1e-11)
    def test_dual_has_no_unique_cause(self):
        # [0,6] is compatible with true speed 0 + bad second, or true speed 6 + bad first.
        obs=np.array([0.,6.])
        np.testing.assert_array_equal(obs,np.array([0.,0.])+[0.,6.])
        np.testing.assert_array_equal(obs,np.array([6.,6.])+[-6.,0.])
    def test_electrical_bias_rank(self):
        r,k=2.,.05
        design=np.tile([1.,-r,-k],(200,1))
        self.assertEqual(np.linalg.matrix_rank(design),1)
        target=-.3
        for biases in ((target,0.,0.),(0.,-target/r,0.),(0.,0.,-target/k)):
            np.testing.assert_allclose(design@biases,target,atol=1e-14)
    def test_flatline_easy_case_not_noise_robust(self):
        a=np.zeros((401,3));self.assertTrue(e.pair_features(a)[2].all())
        a[:,0]=np.random.default_rng(23992).normal(0,.25,401)
        self.assertFalse(e.pair_features(a)[2].any())
    def test_unlocalized_not_counted_as_isolation(self):
        f=np.tile([2.,2.,2.,0.,0.],(4,1))
        ans=e.decisions(f,{'v3':1.,'dual':1.,'triple':1.})
        for name in ('v3_unlocalized','dual_unlocalized'):
            labels,flags=ans[name];self.assertTrue(flags.all());self.assertTrue(np.all(labels==-1))
    def test_pre_alarm_not_detection(self):
        m=dict(primary_onset=3.,anomaly_onset=3.,single_target=0)
        d=e.episode_record(np.array([2.,3.,4.]),np.array([0,0,0]),np.ones(3,bool),m)
        self.assertTrue(d['primary_early']);self.assertFalse(d['primary_valid']);self.assertFalse(d['unique_correct'])
    def test_calibration_rank(self):
        self.assertEqual(e.v3.mb.calibration_threshold(np.arange(199.)),189.)
    def test_seeds_separated(self):
        sets=[set(range(23990,24000)),set(e.CAL_SEEDS),set(e.TEST_SEEDS),set(range(21000,21100))]
        for j,a in enumerate(sets):
            for b in sets[j+1:]:self.assertFalse(a&b)
    def test_witnesses_do_not_change_original_control(self):
        y,m,c=e.generate(23993,'aux1_bias',True);base,_,cb=e.generate(23993,'healthy',True)
        np.testing.assert_array_equal(y[:,:3],base[:,:3]);self.assertEqual(c,cb)
    def test_reproducibility(self):
        y,m,c=e.generate(23990,'stuck',True);np.testing.assert_array_equal(y,self.y);self.assertEqual(m,self.meta)
    def test_screen_timing_grid(self):
        np.testing.assert_allclose(self.times,np.arange(2,17.81,.2),atol=1e-12)

if __name__=='__main__':unittest.main(verbosity=2)
