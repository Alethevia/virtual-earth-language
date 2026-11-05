import unittest
from pilot import run

class Tests(unittest.TestCase):
    def test_reproducible(self):
        self.assertEqual(run(n=1000), run(n=1000))

    def test_evidence_outperforms_for_fixed_toy_case(self):
        r = run(n=10000)
        self.assertLess(r["evidence_error"], 0.1)
        self.assertGreater(r["compressed_error"], 0.48)
        self.assertLess(abs(r["evidence_error"]-r["theoretical_evidence_error"]), 0.02)

    def test_invalid(self):
        for kwargs in ({"n": 0}, {"pairs": 0}, {"d": 0}, {"sigma": 0}):
            with self.assertRaises(ValueError):
                run(**kwargs)

if __name__ == "__main__":
    unittest.main()
