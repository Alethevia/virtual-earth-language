# V3: electrical-consistency triage and active probing

**Simulation research, both predeclared scientific screens FAILED.** Partial improvement is not uniform superiority. No hardware, original-algorithm, safety-certification or publication claim. This draft builds on motor-bank V2 without modifying its source or results.

## Execution and provenance

Protocol/source hashes committed before calibration: `6e90b4e6ce4c83c3efac9be6c7b14eab589e362a`.
Calibration committed before holdout: `03e69df9bb06f776aac52a9bce5ac04f3d224d87`.
159 calibration seed groups x 2 modes = 318 trajectories. Holdout: 100 new base seed groups x 14 conditions x 2 modes = 2,800 trajectories. Six rules yield 16,800 episode-method records and 168 rate cells. Paired copies are NOT independent devices or independent scientific experiments.

19 integrity tests passed locally, including 400 bounded-solver comparisons to SciPy, input/prefix causality, no true-state detector input, exact old-plant parity without probes and a static ambiguity construction. Source hashes match the pre-evaluation commitment. CI must be checked separately; a successful replay means software reproduction, not a successful scientific screen.

## Mechanism and comparison boundaries

Use u = R*i + L*di/dt + K*w in trailing two-second integrated windows. Compare healthy constant-parameter, healthy one-resistance-change, and additive-speed-bias-compatible explanations. A conditional sensor-bias declaration requires rejecting healthy explanations while retaining a compatible bias explanation. Otherwise retain uncertainty/compatibility; do not certify health.

Unlike V2's current-only selection, V3 deliberately uses the suspect speed within competing electrical explanations. V3 uses wider R/L bounds and a K interval, different compute, and a common 0.2-second decision grid for all comparators. Thus this is not an equal-prior/architecture-only comparison. The old bank is actually rerun and recalibrated, not copied from its old results.

Active mode adds a fixed +/-8 rad/s target perturbation alternating every .4 seconds from t=2 seconds, keeping the original +/-12-V PI limit. Passive mode uses the original target. Same seeds/noise/algorithm are paired; changed control input is an explicit intervention, NOT free passive-diagnostic improvement.

## Main results, each count / 100

Healthy rows report false speed-fault declarations; fault rows report valid first declarations, excluding pre-fault alarms.

| Condition | V2 bank passive | V2 bank active | V3 triage passive | V3 triage active |
|---|---:|---:|---:|---:|
| healthy | 8 | 7 | 0 | 0 |
| healthy_shift | 3 | 2 | 8 | 11 |
| bias | 96 | 94 | 58 | 94 |
| bias_shift | 97 | 98 | 45 | 73 |
| drift | 96 | 95 | 100 | 100 |
| stuck | 95 | 95 | 44 | 43 |
| startup_bias | 100 | 100 | 80 | 98 |
| healthy_late_shift | 100 | 100 | 3 | 3 |
| bias_late_shift | 0 | 0 | 33 | 72 |
| healthy_outside_bank | 100 | 100 | 74 | 75 |
| healthy_nonlinear | 9 | 10 | 69 | 67 |
| bias_nonlinear | 94 | 90 | 38 | 53 |
| healthy_voltage_bias | 100 | 99 | 57 | 97 |
| healthy_current_bias | 100 | 100 | 49 | 96 |

Key result: active-minus-passive triage valid detection improves by 36 percentage points for bias (paired bootstrap interval 27–45), 28 for bias_shift (19–38), and 39 for bias_late_shift (30–49). These intervals are exploratory and not multiplicity-adjusted. There is no universal superiority over the V2 bank.

The targeted screen required <=10% false alarms in each of healthy, healthy_shift, healthy_late_shift. Active healthy_shift is **11/100**, so the screen FAILED without changing its threshold. The extended screen also fails stuck detection: **43/100**, below its >=90% criterion. Zero observed false alarms in one cell is not a guarantee of zero population risk.

## What the ablations and negative controls reveal

Always-abstain makes zero false alarms but detects zero faults. In active mode, removing the switch alternative increases late-change healthy false alarms from 3 to 6, while improving subsequent-fault detection from 72 to 79 and stuck detection from 43 to 80. Thus the extra mechanism is not automatically better. Full per-rule results are in REFERENCE.json and regenerated outputs.

The nonlinear/noisier healthy condition produces 67/100 false declarations; these two stress factors were changed together, so their separate causal contributions have NOT been identified. The outside-bank R case remains poor despite V3's wider parameter range. Do not present noise-aware calibration as an already-implemented fix.

When the speed sensor is healthy but the voltage/current reading is biased, active triage declares speed-bias-compatible anomalies in 97/100 and 96/100 cases. That is wrong specific attribution if interpreted as a speed-sensor diagnosis. Trusted voltage/current is a critical assumption, not a detail to hide. The method can flag an inconsistency without uniquely identifying its source.

## Control costs

Across healthy, healthy_shift and healthy_late_shift (300 paired seed-condition cases), mean model electrical input energy was 575.837 J passive and 569.436 J active (-1.11%); original-target tracking RMSE rose from 19.7855 to 20.3001 rad/s (+2.60%). This is not a free intervention or an energy-saving claim: tracking worsened, actuator saturation is frequent, and the comparison is specific to these simulated trajectories. Voltage-squared integral is recorded separately and is NOT measured in joules. Corrupted-voltage controls are excluded from actual-energy claims.

## An explicit identifiability limit

At equilibrium, two admissible worlds give exactly the same measurements [u=6 V, i=2 A, measured speed=40 rad/s]:
- Healthy: R=2 ohm, true speed=40, load=.020 Nm.
- Biased: R=2.15 ohm, true speed=34, speed offset=+6, load=.032 Nm.

Both satisfy the nominal electrical/mechanical equations. A detector receiving identical inputs cannot always distinguish the worlds without additional information. This is an elementary illustrative construction, not a new general theorem. Probing helps selected cases; it does not eliminate all ambiguity or identify which measurement channel is wrong.

Prior art: Joshi et al. (2014), NASA record https://ntrs.nasa.gov/citations/20140006008 ; Tsolakis et al. (2024), https://arxiv.org/abs/2411.03011 . Set consistency, informative excitation and fault identifiability are established ideas. This bounded least-squares implementation does not inherit formal set-membership guarantees: Gaussian noise is unbounded and regressors/integration are imperfect.

## Reproduce

```bash
cd research/motor_consistency_v3
python -m pip install -r requirements.txt
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m unittest -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python run_all.py --out results/reproduced
```

Use a new output directory. Preserve all failures. No paid LLM/GPU or live machine/trading API is used; GitHub Actions consumes workflow resources. Neither CI success nor model-generated review is independent human peer review.
