"""Synthetic diagnostic memory pilot; no control-system safety claim."""
import json
from math import erf, sqrt
import numpy as np

def run(n=10000, d=0.4, sigma=1.0, pairs=8, seed=20261029):
    if n <= 0 or pairs <= 0 or d <= 0 or sigma <= 0:
        raise ValueError("positive n, pairs, d and sigma required")
    rng = np.random.default_rng(seed)
    truth = rng.integers(0, 2, n)
    sign = np.where(truth == 0, 1.0, -1.0)
    a = rng.normal(sign[:, None] * d, sigma, (n, pairs))
    b = rng.normal(-sign[:, None] * d, sigma, (n, pairs))
    compressed = (a.sum(axis=1) + b.sum(axis=1)) / (2 * pairs)
    # Compression has exactly the same distribution under both hypotheses.
    compressed_guess = np.zeros(n, dtype=int)
    contrast = (a - b).sum(axis=1)
    evidence_guess = (contrast < 0).astype(int)
    theory_error = 0.5 * (1 - erf(sqrt(pairs) * d / sigma))
    return {
        "n": n, "pairs": pairs, "d": d, "sigma": sigma, "seed": seed,
        "compressed_error": float(np.mean(compressed_guess != truth)),
        "evidence_error": float(np.mean(evidence_guess != truth)),
        "theoretical_evidence_error": theory_error,
        "compressed_mean_H0": float(compressed[truth == 0].mean()),
        "compressed_mean_H1": float(compressed[truth == 1].mean()),
        "status": "Synthetic sanity check only; not an original theorem or safe controller."
    }

if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
