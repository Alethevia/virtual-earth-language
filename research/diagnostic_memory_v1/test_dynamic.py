import inspect
import math
import unittest
import numpy as np
from scipy.special import ndtr
from dynamic import (Model, candidate_probes, admissible, trajectories, separation,
                     bayes_risk, batch_llr, online_llr, llr_increments, grid,
                     transition, state_filter, finite_predict, frozen_design_risk, wilson)


class DynamicsTests(unittest.TestCase):
    def test_no_probe_confounded(self):
        means, x = trajectories(np.zeros(18))
        np.testing.assert_allclose(means, 1.25, atol=1e-14)
        self.assertNotEqual(x[0,0,0], x[0,1,0])
        self.assertEqual(Model().offset, 0.25)

    def test_recurrence(self):
        v = np.zeros(18); v[:4] = -.5
        means, x = trajectories(v)
        np.testing.assert_allclose(x[0,:,1], .8*Model().initial+np.array([.25,.2])*.5)
        np.testing.assert_allclose(means[0,1], x[0,1,1:]+.25)

    def test_future_probe_does_not_change_past(self):
        a = np.zeros(18); b = a.copy(); b[9] = -.5
        ma, _ = trajectories(a); mb, _ = trajectories(b)
        np.testing.assert_array_equal(ma[:,:,:9], mb[:,:,:9])

    def test_candidate_count_and_energy(self):
        v = candidate_probes()
        self.assertEqual(v.shape, (math.comb(12,4)*2**4,18))
        np.testing.assert_allclose(np.sum(v*v,axis=1),1)
        np.testing.assert_array_equal(v[:,12:],0)

    def test_safety_filter_rejects_positive_burst(self):
        v = np.zeros((2,18)); v[0,:4] = .5; v[1,:4] = -.5
        np.testing.assert_array_equal(admissible(v), [False,True])

    def test_model_validation(self):
        for kw in ({'sigma':0},{'a':1},{'pulses':13},{'horizon':2},{'b0':.1},{'horizon':1.2},{'a':float('nan')}):
            with self.assertRaises(ValueError): Model(**kw)

    def test_probe_shape_validation(self):
        for v in (np.zeros(17), np.full(18,np.nan)):
            with self.assertRaises(ValueError): trajectories(v)


class LikelihoodTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        v = np.zeros(18); v[:4] = -.5
        cls.means = trajectories(v)[0][0]
        cls.q = separation(cls.means[None],.08)
        cls.y = cls.means[1]+.08*np.random.default_rng(42).normal(size=(200,18))

    def test_batch_recursive_equal(self):
        np.testing.assert_allclose(batch_llr(self.y,self.means,.08),online_llr(self.y,self.means,.08),atol=1e-12)

    def test_bayes_formula(self):
        self.assertAlmostEqual(float(bayes_risk(4)),float(ndtr(-1)))
        self.assertEqual(float(bayes_risk(0)),.5)

    def test_positive_sign_favors_h1(self):
        self.assertTrue((online_llr(self.means[1:2],self.means,.08)>0).all())
        self.assertTrue((online_llr(self.means[0:1],self.means,.08)<0).all())

    def test_prefix_causality(self):
        altered = self.y.copy(); altered[:,10:] += 200
        np.testing.assert_array_equal(llr_increments(self.y,self.means,.08)[:,:10],
                                      llr_increments(altered,self.means,.08)[:,:10])

    def test_inference_has_no_true_label_argument(self):
        for fn in (finite_predict,online_llr,llr_increments):
            parameters = inspect.signature(fn).parameters
            self.assertNotIn('truth',parameters); self.assertNotIn('true_state',parameters)

    def test_likelihood_validation(self):
        with self.assertRaises(ValueError): llr_increments(self.y,self.means,0)
        with self.assertRaises(ValueError): llr_increments(self.y,self.means[:,:5],.08)
        with self.assertRaises(ValueError): separation(self.means[None],float('nan'))
        with self.assertRaises(ValueError): bayes_risk(-1)


class FiniteStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        v = np.zeros(18); v[:4] = -.5
        cls.means = trajectories(v)[0][0]
        cls.q = separation(cls.means[None],.08)

    def test_state_alphabet(self):
        for b in (2,3,4,8):
            levels, bounds = grid(b,2)
            self.assertEqual(len(levels),2**b)
            self.assertEqual(len(bounds),2**b-1)
            np.testing.assert_allclose(levels,-levels[::-1])

    def test_transition_stochastic(self):
        levels,bounds = grid(3,2)
        for h in (0,1):
            tr = transition(levels[None],np.array([.3]),bounds,h)
            self.assertTrue((tr>=0).all())
            np.testing.assert_allclose(tr.sum(axis=2),1,atol=1e-14)

    def test_risk_not_better_than_full_information(self):
        full = bayes_risk(self.q.sum())
        for bits in (2,3,4):
            for span in (.25,1,4):
                for method in ('fixed_center','posterior'):
                    d=state_filter(self.q,bits,span,method)
                    self.assertGreaterEqual(d['risk'][0],full-1e-12)

    def test_zero_information(self):
        for method in ('fixed_center','posterior'):
            d=state_filter(np.zeros((1,18)),2,1,method,retain=True)
            self.assertEqual(d['risk'][0],.5)
            self.assertEqual(frozen_design_risk(d)[0],.5)

    def test_frozen_nominal_risk_matches(self):
        for method in ('fixed_center','posterior'):
            d=state_filter(self.q,3,2,method,retain=True)
            np.testing.assert_allclose(d['risk'],frozen_design_risk(d),atol=1e-13)

    def test_monte_carlo_matches_exact(self):
        # Unit-test seed distinct from declared confirmatory evaluation seed.
        rng=np.random.default_rng(742198)
        truth=np.repeat([0,1],6000)
        eps=rng.normal(size=(len(truth),18))
        for method in ('fixed_center','posterior'):
            d=state_filter(self.q,2,1,method,retain=True)
            for scale in (1.,1.25):
                y=self.means[truth]+.08*scale*eps
                prediction=finite_predict(y,self.means,.08,d)
                observed=np.mean(prediction!=truth)
                exact=frozen_design_risk(d,scale)[0]
                self.assertLess(abs(observed-exact),.025)

    def test_batch_design_matches_individual(self):
        q=np.r_[self.q,self.q*.7]
        for method in ('fixed_center','posterior'):
            combined=state_filter(q,2,1,method)['risk']
            singles=[state_filter(row,2,1,method)['risk'][0] for row in q]
            np.testing.assert_allclose(combined,singles,atol=1e-13)

    def test_invalid_design_inputs(self):
        for bits in (0,1.5,True,11):
            with self.assertRaises(ValueError): grid(bits,1)
        for span in (0,float('nan')):
            with self.assertRaises(ValueError): grid(2,span)
        with self.assertRaises(ValueError): state_filter(self.q,2,1,'invented')
        with self.assertRaises(ValueError): state_filter([[-1]],2,1,'posterior')

    def test_wilson_bounds(self):
        lo,hi=wilson(0,100)
        self.assertAlmostEqual(lo,0); self.assertLess(hi,.05)
        with self.assertRaises(ValueError): wilson(-1,100)


if __name__=='__main__': unittest.main(verbosity=2)
