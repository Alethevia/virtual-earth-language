# Motor model-bank V2 — completed simulation, scientific screen FAILED

2026-11-04. A follow-on to the AutoResearch audit. No hardware validation, novelty or publication claim. All original V1 code is unchanged; main is not modified.

## What actually ran

- Protocol committed before calibration/holdout: `907e4a13065f51a63d66f97b09c02266576a9298`.
- Tested implementation hashes committed before calibration/holdout: `0109a5bdf767c16e7cf1745a29318c3cc13b1158`.
- 159 new calibration episodes (76 healthy, 83 shifted healthy); 1,200 primary and 600 stress trajectories. Conditions share seeds: 200 primary + 100 stress seed groups, NOT 1,800 independent devices.
- Seven decision rules, 84 rate cells, 12,600 per-method episode records. 14 integrity tests passed.
- Separate NumPy/SciPy implementation replayed three score trajectories: maximum difference 4.263256414560601e-14; parameter-selection indices agreed. All five calibration thresholds and 84 rate cells were independently recomputed from saved outputs. Same-author verification, not third-party certification.

## Method

125 load-augmented Kalman filters span R=1.8–3.0 ohm, L=.018–.022 H. The primary rule selects a member using cumulative current-innovation costs computed only from applied voltage and measured current. Suspect speed is used to form the final residual, NOT to fit/select parameters. No true states/parameters, load, fault labels, onset or future samples enter the detector. No known-healthy startup is required. Baselines share sensors and, for matched versions, the exact same calibration episodes.

## Primary results (count / 200)

Healthy rows are false sensor-fault alarms (lower better); fault rows are valid detections (higher better). Alarms before a fault do not count as detections.

| Condition | No-load original threshold | No-load matched calibration | Load observer matched calibration | Cumulative bank |
|---|---:|---:|---:|---:|
| healthy | 1 | 0 | 0 | 21 |
| healthy_shift | 200 | 24 | 28 | 8 |
| bias | 55 | 0 | 0 | 183 |
| bias_shift | 0 | 33 | 33 | 194 |
| drift | 104 | 0 | 0 | 184 |
| stuck | 194 | 138 | 138 | 181 |

The candidate improves selected static-mismatch cases but is NOT uniformly better. Ordinary healthy false alarms are 10.5%, Wilson 95% interval 6.97%–15.52%. The locked screen demanded <=10% in each healthy case, so it **FAILED**. We did not relax the criterion. Bias/bias_shift detection is 91.5%/97%, but stuck detection 90.5% is below the original observer's 97%. Conditional median bias detection delay is .08 s; it excludes failures. There are 16 pre-fault alarms in each ordinary bias/drift/stuck case.

## Stress results (count / 100)

| Condition | No-load matched calibration | Cumulative bank |
|---|---:|---:|
| startup_bias (detection) | 0 | 99 |
| healthy_late_shift (false alarm) | 8 | 100 |
| bias_late_shift (valid detection) | 14 | 0 |
| healthy_outside_bank (false alarm) | 100 | 100 |
| healthy_nonlinear (false alarm) | 0 | 11 |
| bias_nonlinear (detection) | 0 | 89 |

The dominant failure is temporal change: parameter changes while running trigger 100/100 false sensor-fault alarms. With a subsequent real fault, all 100 cases have already alarmed early, so valid detections are zero. Learning an initially different device is not the same as tracking/attributing changes during operation.

## Ablations and limits

The 2-second discounted bank has only 8/200 ordinary healthy false alarms but detects just 11/200 bias and 11/200 bias_shift faults. Choosing the bank member that most closely matches suspect speed gives 0/200 healthy_shift alarms but only 21/200 bias_shift detections. Better fitting the suspect sensor can conceal its faults.

125 filters versus one per baseline is a substantial compute/state cost, not an equal-compute gain. Mixed-distribution calibration does not guarantee a 5% error rate in every subgroup. Bootstrap intervals are paired by seed, exploratory and unadjusted for multiple comparisons. The primary plant/model family is shared; nonlinear/time-varying stress is limited, not hardware validation.

Multiple-model filter banks are established methodology: Hanlon (1996), AFIT dissertation, https://scholar.afit.edu/etd/6058/ . Standard DC motor equations: University of Michigan Control Tutorials, https://ctms.engin.umich.edu/CTMS/index.php?example=MotorSpeed&section=SystemModeling . No literature-level superiority claim is made.

## Reproduce

Python 3.13.5 reference; pinned numerical dependencies in requirements.txt.

```bash
cd research/motor_bank_v2
python -m pip install -r requirements.txt
bash run_all.sh results/reproduced
```

Always use a NEW output directory. The script verifies all 84 reference counts and insists that the scientific screen remains false. Software/CI success means faithful reproduction of this mixed/negative result, not a successful diagnostic system. Full raw local outputs and a second-implementation verifier are supplied in the conversation archive; CI uploads newly generated raw outputs.

Next research question, not an implemented claim: detect model change and preserve an ambiguous diagnosis until parameter change, sensor fault and their coexistence can be distinguished with justified evidence.
