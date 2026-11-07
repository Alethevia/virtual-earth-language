"""Integrity tests; no calibration/evaluation seeds are used here."""
import unittest
import math
import numpy as np
from scipy.linalg import toeplitz
from scipy.signal import lfilter
import study as s

class Integrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg=s.Config(20,.5)
        cls.y=s.original_sensors(900001,cls.cfg,duration=12.)
        cls.score=s.scores(cls.y,cls.cfg)
    def test_finite(self):self.assertTrue(np.isfinite(self.score).all())
    def test_causal_prefix(self):
        for n in (121,161,201):
            np.testing.assert_allclose(s.scores(self.y[:n],self.cfg),self.score[:,:,:n],atol=2e-11,rtol=1e-11)
    def test_future_invariance(self):
        yy=self.y.copy();yy[181:]+=np.arange(3)*123
        np.testing.assert_allclose(s.scores(yy,self.cfg)[:,:,:181],self.score[:,:,:181],atol=2e-10,rtol=1e-11)
    def test_common_waveform_cancels(self):
        yy=self.y+np.sin(np.arange(len(self.y))/7)[:,None]*70
        np.testing.assert_allclose(s.scores(yy,self.cfg),self.score,atol=2e-10,rtol=1e-11)
    def test_same_noise_across_rates(self):
        y=s.original_sensors(900002,s.Config(100),duration=12.)
        for fs in (2,10,20):
            np.testing.assert_array_equal(s.original_sensors(900002,s.Config(fs),duration=12.),y[::100//fs])
    def test_scaling(self):
        a=s.original_sensors(900003,s.Config(20),duration=12.)
        np.testing.assert_array_equal(self.cfg.scale*a,s.original_sensors(900003,self.cfg,duration=12.))
    def test_innovation_template(self):
        for cfg in (s.Config(20),s.Config(100),s.Config(2),s.Config(100,1.,0.)):
            a=cfg.rho**(100/cfg.fs);q=.5 if cfg.rho else 0.;r=.125
            b,c,S=s.steady(a,q,r)
            expected=c+(1-c)*b**np.arange(100)
            actual=lfilter([1,-a],[1,-b],np.ones(100))
            np.testing.assert_allclose(actual,expected,atol=2e-14)
    def test_mean_variance_direct(self):
        for n in (1,5,40,100):
            for a in (0.,.3,.9):
                C=.5*toeplitz(a**np.arange(n))+.125*np.eye(n)
                self.assertAlmostEqual(s.covariance_sum(n,a,.5,.125),C.sum(),places=10)
    def test_fft_scan_direct(self):
        cfg=self.cfg;d=np.stack([self.y[:,a]-self.y[:,b] for a,b in s.PAIRS])
        ns,nfft,weights,spectra,norms,params=s.templates(cfg,len(self.y))
        raw=np.zeros_like(d);innovation=np.zeros_like(d)
        for j,(a,b,c,S) in enumerate(params):
            e=lfilter([1,-a],[1,-b],d[j])
            for k,n in enumerate(ns):
                m=np.convolve(d[j],np.ones(n)/norms[j,k],mode='valid')
                raw[j,n-1:]=np.maximum(raw[j,n-1:],abs(m))
                v=np.convolve(e,weights[j][k],mode='valid')
                innovation[j,n-1:]=np.maximum(innovation[j,n-1:],abs(v))
        raw[:,:100]=0;innovation[:,:100]=0
        np.testing.assert_allclose(raw,self.score[1],atol=2e-11)
        np.testing.assert_allclose(innovation,self.score[2],atol=2e-11)
    def test_iid_scan_equivalence(self):
        cfg=s.Config(20,1.,0.);y=s.original_sensors(900004,cfg,duration=12.)
        z=s.scores(y,cfg)
        np.testing.assert_allclose(z[1],z[2],atol=2e-11)
    def test_generator_repeat(self):np.testing.assert_array_equal(self.y,s.original_sensors(900001,self.cfg,duration=12.))
    def test_independent_recurrence(self):
        z=np.random.default_rng(900005).normal(size=100)
        for a in (0.,.59,.99):
            e=z*math.sqrt(.5*(1-a*a));e[0]=z[0]*math.sqrt(.5)
            np.testing.assert_allclose(s.explicit_state(z,a,.5),lfilter([1],[1,-a],e),atol=1e-14)
    def test_independent_generator_repeat(self):
        for fam in s.FAMILIES:
            np.testing.assert_array_equal(s.independent_sensors(900006,self.cfg,fam,duration=12.),s.independent_sensors(900006,self.cfg,fam,duration=12.))
    def test_rank(self):self.assertEqual(s.rank95(np.arange(199.)),189.)
    def test_before_monitor_zero(self):self.assertTrue((self.score[:,:,:100]==0).all())
    def test_invalid_inputs(self):
        for y in (np.zeros((5,3)),np.zeros((220,4)),np.full((220,3),np.nan)):
            with self.assertRaises(ValueError):s.scores(y,self.cfg)
    def test_unknown_target_logic(self):
        c=np.array([[1,1,0,1],[1,0,1,1],[0,1,1,1]],bool)
        np.testing.assert_array_equal(s.labels_from_cross(c),[0,1,2,-1])
    def test_early_mistake_not_success(self):
        cfg=s.Config(2);sc=np.zeros((3,30));sc[[0,2],10]=2;sc[[0,1],25]=2
        r=s.record(sc,1.,cfg,0,10.,None)
        self.assertFalse(r['first_correct']);self.assertTrue(r['wrong_any'])
    def test_generic_not_isolation(self):
        sc=np.ones((3,30))*2;r=s.record(sc,1.,s.Config(2),0,10.,None)
        self.assertTrue(r['any_alarm']);self.assertFalse(r['any_unique']);self.assertFalse(r['first_correct'])
    def test_common_mode_ambiguity(self):
        yy=self.y+np.arange(len(self.y))[:,None]*.03
        np.testing.assert_allclose(s.scores(yy,self.cfg),self.score,atol=2e-10)
    def test_two_bad_witnesses(self):
        y=np.zeros((300,3));y[:,1:]=6
        sc=s.scores(y,s.Config(20,1.,0.))
        lab=s.labels_from_cross(sc[0]>2)
        self.assertEqual(lab[-1],0)
    def test_pulse_after_recovery_not_success(self):
        sc=np.zeros((3,40));sc[[0,1],30]=2
        r=s.record(sc,1.,s.Config(2),0,10.,12.)
        self.assertFalse(r['first_correct']);self.assertTrue(r['post_recovery_accusation'])
    def test_seed_ranges_disjoint(self):
        groups=[set(range(a,a+n)) for a,n in ((900000,100),(910000,199),(920000,300),(930000,199),(940000,200),(950000,400))]
        for i,a in enumerate(groups):
            for b in groups[i+1:]:self.assertFalse(a&b)
    def test_exact_scenario_counts(self):
        self.assertEqual(len(s.R11_CONFIGS),12);self.assertEqual(len(s.R12_CONFIGS),5)
        self.assertEqual(len(s.R12_CASES),9);self.assertEqual(len(s.R13_CASES),18)
    def test_fault_does_not_mutate_background(self):
        yy=self.y.copy();out,_,_=s.inject(yy,self.cfg,900007,0,.5,'step')
        np.testing.assert_array_equal(yy,self.y)
    def test_wilson_known(self):
        self.assertAlmostEqual(s.wilson(0,200)[1],.018845326377266575)
        self.assertEqual(s.wilson(200,200)[1],1.)

if __name__=='__main__':unittest.main(verbosity=2)
