import unittest
import numpy as np
import calibration_study as s

class Integrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p,cls.meta,_=s.generate(37880,'bias_slow_reporting')
        cls.f=s.v5.features(cls.p)
        cls.th=dict(pooled_quality=2.,count_quality=[2.,1.8,1.5],max_group_quality=2.,count_time_only=[1.,.9,.8])
    def test_parent_commit_hash(self):self.assertEqual(s.sources()['telemetry.py'],s.EXPECTED_V5)
    def test_group_boundaries(self):np.testing.assert_array_equal(s.group_ids(np.array([0,2,3,5,6,25,26,201])),[-1,-1,0,0,1,1,2,2])
    def test_group_reject_float(self):
        with self.assertRaises(ValueError):s.group_ids(np.array([3.5]))
    def test_group_reject_negative(self):
        with self.assertRaises(ValueError):s.group_ids(np.array([-1]))
    def test_rank199(self):self.assertEqual(s.rank_threshold(np.arange(199.)),189.)
    def test_rank597(self):self.assertEqual(s.rank_threshold(np.arange(597.)),568.)
    def test_small_calibration_is_infinite(self):self.assertTrue(np.isinf(s.rank_threshold([1.,2.])))
    def test_bad_calibration(self):
        for x in ([],[1.,np.nan]):
            with self.assertRaises(ValueError):s.rank_threshold(x)
    def test_causal_prefix(self):
        for n in (401,801,1201):
            q=s.v5.Packets(self.p.values[:n],self.p.stamps[:n],self.p.sigma,self.p.quantum,self.p.offset_bound)
            f=s.v5.features(q)
            for actual,want in zip(f,self.f):np.testing.assert_array_equal(actual,want[:len(actual)])
    def test_decision_prefix(self):
        a=s.decisions(tuple(v[:7] for v in self.f),self.th);b=s.decisions(self.f,self.th)
        for m in s.METHODS:
            for x,y in zip(a[m],b[m]):np.testing.assert_array_equal(x,y[:7])
    def test_future_values_not_used(self):
        y=self.p.values.copy();start=1200;y[start:]+=10
        # Starts at an acquisition boundary to retain duplicate-packet consistency.
        q=s.v5.Packets(y,self.p.stamps,self.p.sigma,self.p.quantum,self.p.offset_bound)
        f=s.v5.features(q)
        np.testing.assert_array_equal(f[0][:50],self.f[0][:50])
    def test_selection_does_not_read_values(self):
        q=s.v5.Packets(self.p.values+1,self.p.stamps,self.p.sigma,self.p.quantum,self.p.offset_bound)
        np.testing.assert_array_equal(s.v5.features(q)[2],self.f[2])
    def test_no_truth_in_detector_signature(self):
        import inspect
        self.assertEqual(list(inspect.signature(s.decisions).parameters),['f','thresholds'])
    def test_packet_validation_retained(self):
        q=s.v5.Packets(self.p.values,self.p.stamps+1,self.p.sigma,self.p.quantum,self.p.offset_bound)
        with self.assertRaises(ValueError):s.v5.features(q)
    def test_repeated_packets_not_independent(self):self.assertTrue((self.f[2]<=5).all())
    def test_all_three_count_groups_reached(self):
        for g in range(3):
            p,_,_=s.calibration_episode(37885,g)
            _,a,n,_=s.v5.features(p)
            self.assertTrue(a[:,3].all());self.assertTrue((s.group_ids(n)==g).all())
    def test_metadata_not_changed_by_resampling(self):
        p,_,_=s.v5.generate(37884,'healthy')
        q=s.resample_primary(p,20)
        for a,b in zip((p.sigma,p.quantum,p.offset_bound),(q.sigma,q.quantum,q.offset_bound)):np.testing.assert_array_equal(a,b)
        np.testing.assert_array_equal(p.values[:,1:],q.values[:,1:])
    def test_dynamic_rates_keep_valid_stamps(self):
        for c in ('healthy_rate_switch','healthy_many_rate_changes'):
            p,_,_=s.generate(37884,c);s.v5.validate(p)
            self.assertGreater(len(np.unique(s.group_ids(s.v5.features(p)[2]))),1)
    def test_seeds_do_not_overlap(self):
        sets=[set(x) for x in s.CAL_RANGES]+[set(s.TEST_SEEDS),set(range(37000,38000)),set(s.v5.CAL_SEEDS),set(s.v5.TEST_SEEDS)]
        for i,x in enumerate(sets):
            for y in sets[i+1:]:self.assertFalse(x&y)
    def test_deterministic(self):
        p,_,_=s.generate(37880,'bias_slow_reporting');np.testing.assert_array_equal(p.values,self.p.values)
    def test_any_unique_requires_generic_flag(self):
        for _,(label,flag,_) in s.decisions(self.f,self.th).items():self.assertTrue((flag[label>=0]).all())
    def test_insufficient_is_not_an_accurate_diagnosis(self):
        p,meta,_=s.generate(37881,'bias_asynchronous');f=s.v5.features(p)
        label,flag,ok=s.decisions(f,self.th)['count_quality']
        self.assertFalse(ok.any());r=s.record(np.arange(2.,18.,.2),label,flag,ok,meta)
        self.assertFalse(r['unique_correct']);self.assertEqual(r['coverage'],0)
    def test_historical_rule_identical(self):
        old=s.v5.decisions(self.f,{'raw_short':2.,'raw_long':2.,'aligned':1.,'quality':s.FROZEN_QUALITY})['time_quality']
        new=s.decisions(self.f,self.th)['v5_frozen_quality']
        for a,b in zip(old,new):np.testing.assert_array_equal(a,b)
    def test_wrong_any_not_hidden_by_correct_primary(self):
        t=np.array([2.,3.,4.]);lab=np.array([1,0,0]);meta={'primary_onset':2.5,'anomaly_onset':2.5,'single_target':0}
        r=s.record(t,lab,np.ones(3,bool),np.ones(3,bool),meta)
        self.assertTrue(r['primary_valid']);self.assertFalse(r['unique_correct']);self.assertTrue(r['wrong_any_episode'])
    def test_multi_fault_not_credited_as_single_correct(self):
        meta={'primary_onset':3.,'anomaly_onset':3.,'single_target':None}
        r=s.record(np.array([2.,3.]),np.array([-1,0]),np.array([False,True]),np.ones(2,bool),meta)
        self.assertFalse(r['unique_correct']);self.assertTrue(r['wrong_any_episode'])
    def test_abstain_retains_data_availability(self):
        label,flags,ok=s.decisions(self.f,self.th)['always_abstain']
        self.assertFalse(flags.any());self.assertTrue((label==-1).all());self.assertTrue(ok.all())
    def test_whole_episode_max_includes_all_pairs(self):
        x=np.arange(240.).reshape(80,3);self.assertEqual(x.max(),239)
    def test_correlated_noise_declared_marginal_sd(self):
        p,_,_=s.generate(37882,'healthy_correlated_noise');self.assertEqual(p.sigma[0],.75)
    def test_constant_common_offset_invariant(self):
        q=s.v5.Packets(self.p.values+5,self.p.stamps,self.p.sigma,self.p.quantum,self.p.offset_bound)
        f=s.v5.features(q)
        np.testing.assert_allclose(f[0],self.f[0],atol=1e-12)

if __name__=='__main__':unittest.main(verbosity=2)
