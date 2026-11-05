# Dynamic diagnostic-memory benchmark — V1 results

**Status: completed simulation/baseline audit, not an original theorem or accepted paper.**

## What was executed

A dimensionless scalar dynamic plant under two known explanations: changed actuation gain with a healthy sensor, or nominal gain with sensor offset. Both produce the same output at the initial steady operating point. Safe open-loop probes change the mean trajectories. All model assumptions and the candidate class were fixed before evaluation.

- Pre-evaluation protocol commit: `3876398b3f8c3183d9c6a14f7764c808454f4fae`.
- 7,920 candidate schedules, exactly four half-unit probes in the first 12 steps, 18 observations total; 7,234 pass both-model state bounds.
- Exhaustive design search over this schedule class and seven quantizer spans; no fitting on test observations.
- 40,000 independent noise trajectories (20,000 per hypothesis) reused as paired evaluations across four schedule labels and three noise scales. This is 480,000 scenario-trajectory evaluations, NOT 480,000 independent experiments. Two optimized schedule labels selected identical inputs.
- 22 local tests passed. Batch and recursive LLR decisions agree in every evaluation; maximum numeric LLR difference is 6.22e-15.
- `design.json` SHA256: `261db8756cb349cbbff06710ac3d2f9089e06ed0430da02ae0bac1f6f0256d20`.

## Matched-model results on the selected equal-energy probe

Lower error is better. 'Bits' covers only data-dependent diagnostic state, NOT clock, models, arithmetic or ROM. Full-history reference stores 18 float64 observations.

| Method | State/storage bits | Exact model error | Observed error | Errors / 40,000 |
|---|---:|---:|---:|---:|
| full_history_llr | 1152 | 17.9825% | 17.8375% | 7135 |
| recursive_llr | 64 | 17.9825% | 17.8375% | 7135 |
| fixed_center | 2 | 22.5728% | 22.4075% | 8963 |
| posterior | 2 | 20.7656% | 20.4625% | 8185 |
| fixed_center | 3 | 19.3642% | 19.0100% | 7604 |
| posterior | 3 | 19.2122% | 18.9175% | 7567 |
| fixed_center | 4 | 18.4966% | 18.2175% | 7287 |
| posterior | 4 | 18.3487% | 18.1475% | 7259 |
| fixed_center | 8 | 17.9875% | 17.7775% | 7111 |
| posterior | 8 | 17.9875% | 17.7825% | 7113 |

The quantized 8-bit empirical error is very slightly BELOW the empirical full-information error in this one paired sample. This is Monte Carlo fluctuation, not a violation of Bayes optimality: its exact model risk is higher. Report theoretical and empirical risks together, not a cherry-picked accuracy claim.

## What changed our research conclusion

1. **Raw history is not necessary in this model.** A single recursive likelihood statistic is equivalent to full history. Pilot 0's grand-mean baseline was deliberately lossy; its dramatic advantage was not an advance over optimal inference.
2. **Few state bits need not cause catastrophic failure.** The 4-bit posterior filter has exact error 18.3487%, versus 17.9825% for full information, a 0.3662-percentage-point gap under these assumptions. Additional read-only reconstruction storage is not free.
3. **Co-design did not improve probe choice here.** Full-information optimization and 2-bit posterior-filter optimization both selected four negative pulses at steps 0-3, then zero perturbation. Both use energy 1.0. Within this fixed design family, memory-aware probing has no advantage.
4. **Probe choice matters compared with the declared random reference.** Full-information exact error is 28.1498% for the seeded random admissible schedule, 17.9825% for the selected schedule, and 50% without probing. This is a standard optimal-experiment-design effect, not a new control algorithm. No-probe has zero energy and is not an equal-budget method.

## Reproduce

Requires Python 3.11+ compatible with the locked dependencies (reference: Python 3.13.5), NumPy 2.3.5 and SciPy 1.17.0.

```bash
python -m pip install -r requirements.txt
python -m unittest -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python run_experiment.py --out results/reproduction --phase design
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python run_experiment.py --out results/reproduction --phase evaluate
```

Use a NEW output directory. The runner refuses to overwrite design or results. Generated outputs include all 7,234 admissible candidate design scores, 120 summary rows, per-episode error vectors, settings and hashes. The conversation archive includes these raw artifacts; the GitHub module includes the code, compact results and protocol. Different platforms may change floating-point hashes without changing substantive results.

Read `THEORY_AND_PRIOR_ART.md` for equations, memory accounting, old finite-memory literature and safety limitations. The local protocol file is a verbatim copy of the pre-evaluation GitHub protocol; the theory note documents how zero-information samples are handled.

## Limits

Known two-model family, independent Gaussian measurement noise, deterministic states conditional on the model, finite horizon and open-loop inputs. No continual online parameter adaptation, arbitrary unknown faults, hardware, new theorem, literature-level state-of-the-art performance or total embedded-RAM optimization is claimed. The finite-state Bayesian baseline is established methodology. AI-assisted code and analysis need personal reproduction and expert review before use as evidence of individual research competence.
