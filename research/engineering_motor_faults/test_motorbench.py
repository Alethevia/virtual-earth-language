"""Offline correctness tests, including an actually compiled C controller."""
import ctypes
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import numpy as np
from motorbench import (Motor, PI, DT, METHODS, generate_episode, residuals,
                        scores, observer_design, discretize, calibration_threshold,
                        first_alarm, wilson)


class PhysicsTests(unittest.TestCase):
    def test_parameter_validation(self):
        for field in ('J', 'b', 'K', 'R', 'L'):
            for bad in (0, -1, float('nan'), float('inf')):
                with self.assertRaises(ValueError):
                    Motor(**{field: bad})

    def test_torque_sign(self):
        A, B = Motor().continuous()
        self.assertLess((A@np.zeros(2)+B@np.array([0., .01]))[1], 0)

    def test_steady_state(self):
        p = Motor()
        A, B = p.continuous()
        v, tau = 6., .02
        x = -np.linalg.solve(A, B@np.array([v, tau]))
        w = (p.K*v-p.R*tau)/(p.R*p.b+p.K*p.K)
        self.assertAlmostEqual(x[1], w)
        Ad, Bd = discretize(A, B)
        np.testing.assert_allclose(Ad@x+Bd@np.array([v, tau]), x, atol=1e-12)

    def test_zoh_semigroup(self):
        A, B = Motor().continuous()
        F, G = discretize(A, B, DT)
        F2, G2 = discretize(A, B, 2*DT)
        np.testing.assert_allclose(F@F, F2, atol=1e-12)
        np.testing.assert_allclose(F@G+G, G2, atol=1e-12)

    def test_bad_discretization(self):
        A, B = Motor().continuous()
        for dt in (0, -1, float('nan')):
            with self.assertRaises(ValueError):
                discretize(A, B, dt)
        with self.assertRaises(ValueError):
            discretize(np.zeros((2, 3)), B)

    def test_augmented_observability(self):
        p = Motor()
        A = np.zeros((3, 3))
        A[:2, :2] = p.continuous()[0]
        A[1, 2] = -1/p.J
        C = np.array([[1., 0., 0.]])
        O = np.vstack([C, C@A, C@A@A])
        self.assertEqual(np.linalg.matrix_rank(O), 3)
        self.assertAlmostEqual(np.linalg.det(O)/(-p.K**2/(p.L**2*p.J)), 1.)

    def test_observer_error_stability(self):
        for aug in (False, True):
            F, _, K = observer_design(aug)
            C = np.zeros((1, len(K)))
            C[0, 0] = 1
            self.assertLess(max(abs(np.linalg.eigvals((np.eye(len(K))-K[:, None]@C)@F))), 1)


class ControllerTests(unittest.TestCase):
    def test_saturation(self):
        pi = PI()
        for _ in range(1000):
            self.assertEqual(pi.step(1000), 12)
        self.assertEqual(pi.integral, 0)
        self.assertEqual(pi.step(-1000), -12)

    def test_integration(self):
        pi = PI()
        self.assertEqual(pi.step(1.), .2)
        self.assertAlmostEqual(pi.integral, .006)
        self.assertAlmostEqual(pi.step(1.), .206)

    def test_invalid_inputs(self):
        for x in (float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                PI().step(x)
        for dt in (0, -1):
            with self.assertRaises(ValueError):
                PI().step(1, dt)


class DiagnosisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.trace = generate_episode(17)

    def test_reproducibility(self):
        np.testing.assert_array_equal(self.trace, generate_episode(17))

    def test_shape_and_voltage(self):
        self.assertEqual(self.trace.shape, (1800, 8))
        self.assertLessEqual(abs(self.trace[:, 5]).max(), 12.)

    def test_fault_has_no_preonset_effect(self):
        faulty = generate_episode(17, 'bias')
        np.testing.assert_array_equal(self.trace[:1000], faulty[:1000])
        self.assertAlmostEqual(abs(faulty[1000, 6]-self.trace[1000, 6]), 6.)

    def test_no_ground_truth_leakage(self):
        altered = self.trace.copy()
        altered[:, 2:5] = 123456.
        np.testing.assert_array_equal(residuals(self.trace), residuals(altered))

    def test_no_future_leakage(self):
        altered = self.trace.copy()
        altered[900:, 5:] += 10
        a, b = scores(residuals(self.trace)), scores(residuals(altered))
        np.testing.assert_array_equal(a[:900], b[:900])

    def test_input_used_with_one_step_delay(self):
        altered = self.trace.copy()
        altered[800, 5] += 10
        a, b = residuals(self.trace), residuals(altered)
        np.testing.assert_array_equal(a[:801], b[:801])
        self.assertGreater(abs(a[801, 2]-b[801, 2]), 0)

    def test_score_recursion(self):
        s = scores(np.ones((20, 3)))
        self.assertTrue(np.all(np.diff(s[:, 0]) > 0))
        self.assertAlmostEqual(s[0, 0], 1-math.exp(-DT/.1))

    def test_warmup_exclusion(self):
        s = np.zeros(400)
        s[:200] = 100
        self.assertIsNone(first_alarm(s, 1.))
        s[201] = 2
        self.assertEqual(first_alarm(s, 1.), 201)

    def test_strict_alarm(self):
        self.assertIsNone(first_alarm(np.ones(400), 1.))

    def test_invalid_trace(self):
        with self.assertRaises(ValueError):
            residuals(np.zeros((10, 4)))
        altered = self.trace.copy()
        altered[1, 7] = float('nan')
        with self.assertRaises(ValueError):
            residuals(altered)
        with self.assertRaises(ValueError):
            generate_episode(0, 'invented')


class CalibrationTests(unittest.TestCase):
    def test_rank(self):
        self.assertEqual(calibration_threshold(np.arange(1, 40)), 38.)

    def test_small_sample_conservative(self):
        self.assertEqual(calibration_threshold([1., 2., 3.]), math.inf)

    def test_calibration_validation(self):
        for values in ([], [float('nan')]):
            with self.assertRaises(ValueError):
                calibration_threshold(values)

    def test_wilson(self):
        lo, hi = wilson(0, 60)
        self.assertAlmostEqual(lo, 0.)
        self.assertGreater(hi, .05)
        self.assertLess(hi, .07)
        lo, hi = wilson(60, 60)
        self.assertGreater(lo, .93)
        self.assertAlmostEqual(hi, 1.)


class CParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cc = shutil.which('gcc') or shutil.which('cc')
        if not cc:
            raise RuntimeError('A C compiler is REQUIRED; parity verification must not silently skip')
        cls.tmp = tempfile.TemporaryDirectory()
        target = Path(cls.tmp.name)/'controller.so'
        subprocess.run([cc, '-std=c11', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
            str(Path(__file__).with_name('controller.c')), '-lm', '-o', str(target)], check=True)
        cls.lib = ctypes.CDLL(str(target))
        cls.step = cls.lib.pi_step
        cls.step.argtypes = [ctypes.c_double]*5+[ctypes.POINTER(ctypes.c_double)]
        cls.step.restype = ctypes.c_double

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_python_c_parity(self):
        rng = np.random.default_rng(71)
        pi, integ = PI(), ctypes.c_double(0.)
        for error in rng.normal(0, 100, 3000):
            actual = self.step(error, DT, pi.kp, pi.ki, pi.limit, ctypes.byref(integ))
            self.assertAlmostEqual(pi.step(error), actual, places=12)
            self.assertAlmostEqual(pi.integral, integ.value, places=12)

    def test_c_rejects_invalid_input(self):
        integ = ctypes.c_double(2.)
        result = self.step(float('nan'), DT, .2, .6, 12, ctypes.byref(integ))
        self.assertTrue(math.isnan(result))
        self.assertEqual(integ.value, 2.)


if __name__ == '__main__':
    unittest.main(verbosity=2)
