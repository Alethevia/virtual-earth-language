# Motor model-bank V2 — locked protocol, 2026-11-04

Simulation-only research; no hardware, machinery deployment, novelty, paper acceptance or safety certification is claimed. This follows the prior audit's failed threshold-inflation intervention. It is not the Google proprietary research system.

## Source and development

Base motor implementation: commit `95a46ec42e0bdb66002325e6bae11c28f7690249`, `research/engineering_motor_faults/motorbench.py`, Git blob `681bceb05fd29c17e131e5872291be556c9c2ca1` (7340 bytes). Preserve it unchanged.

Exploratory development used seeds 8100–8111 in the six original conditions (72 paired scenario trajectories). It compared cumulative current-innovation selection to a 2-second exponentially discounted selection. These observations motivated the cumulative candidate. They are NOT held-out evidence. No calibration or final test seeds below have been run when recording this protocol.

## Question and fixed candidates

Can resistance/inductance model selection using only applied voltage and measured current reduce shifted-healthy false alarms WITHOUT merely raising the diagnostic threshold and suppressing sensor-fault sensitivity?

All methods share the same measured voltage/current/speed stream and PI controller. No method reads the true speed, true current, load torque, true motor parameters, condition label or fault onset. Suspect speed participates only in the final diagnostic residual (except the explicitly labelled residual-minimization ablation); it does not enter current-based parameter selection. No known-healthy start is assumed. No additional probing is applied.

- A bank of 125 load-augmented fixed-gain Kalman filters: R = 1.80,1.85,...,3.00 ohm; L = .018,.019,.020,.021,.022 H. Other nominal model parameters and covariance matrices remain as in V1. True J, b, K and load remain mismatched/unknown.
- Primary `bank_cumulative`: select the bank member minimizing cumulative `(current_innovation**2 / predicted_variance + log(predicted_variance))`; compare its estimated speed against the measured speed.
- Ablation `bank_recent`: same bank, but discount accumulated innovation cost with exp(-.01/2).
- Ablation `bank_residual_min`: at each sample take the smallest absolute speed residual across all bank members. This is NOT an oracle, but intentionally demonstrates how accommodating the suspect channel can conceal faults.
- Original no-load and load-augmented observers are each evaluated with both their historical healthy-only threshold and a new threshold using the SAME mixed-healthy calibration as the bank.
- All five distinct score streams use the original causal .10-second exponential smoothing, 2-second warm-up, and 18-second horizon. Seven decision rules result from reusing the two baseline score streams with two thresholds each.

## Calibration and held-out data

Calibration: 159 independent seed episodes, 9400–9558. A separate RNG seed 774411 assigns each episode healthy or healthy_shift with probability .5. All five streams use the same episodes. Per-method episode-maximum order statistic rank ceil(160*.95)=152. No test-dependent threshold selection. Historical fixed thresholds remain 9.466770991995034 (no load) and 10.076904226760591 (load augmented).

Primary holdout: seeds 11000–11199, paired across original healthy, healthy_shift, bias, bias_shift, drift and stuck conditions: 1,200 scenario trajectories, NOT 1,200 independent devices. Original parameters, input/load schedules and fault definitions are unchanged.

Stress holdout: seeds 12000–12099, paired across six separately labelled conditions: 600 scenario trajectories.
1. startup_bias: a signed 6 rad/s sensor offset begins at 1 second, before monitoring begins.
2. healthy_late_shift: healthy sensor; resistance/friction multiply by 1.35/1.30 during operation at a separately sampled time uniformly between 6 and 9 seconds.
3. bias_late_shift: same late parameter change, plus signed 6 rad/s sensor offset starting at a separately sampled time uniformly between 10 and 13 seconds.
4. healthy_outside_bank: healthy sensor; initial resistance/friction multipliers 1.65/1.50, beyond the model-bank resistance range.
5. healthy_nonlinear: healthy sensor; unmodeled Coulomb torque .012*tanh(speed/3), and both measurement-noise standard deviations multiplied by 1.5.
6. bias_nonlinear: same nonlinear/noisy plant plus signed 6 rad/s sensor offset starting uniformly between 10 and 13 seconds.
Stress schedules use an extra RNG initialized with `seed+1000000`, without passing its draws to any detector. No tuning on stress outcomes.

## Outcomes and screening criteria

Report first-alarm-based healthy false alarms, valid fault detections, early alarms, misses, and conditional detection delay, always with episode denominators. Faults present before 2 seconds can only be detected after monitoring starts. A pre-fault alarm cannot be counted as a detection. Wilson 95% intervals describe per-condition rates. Paired differences use seed-paired bootstrap (10,000 resamples, RNG 44991); intervals are exploratory, not multiplicity-adjusted.

The predeclared primary engineering SCREEN passes only if bank_cumulative has <=10% false alarms in BOTH healthy and healthy_shift, >=60% valid detections in BOTH bias and bias_shift, and >=90% valid stuck detections. This screen is not a certification or statistical significance test. Compare against BOTH recalibrated observers and preserve every condition even if the screen passes. All stress results remain separately reported; primary success does not establish continual-drift robustness.

## Verification and accounting

Before final evaluation, lock source SHA-256 hashes and save calibration output. Test equivalence to the original two observers, causal prefix invariance, parameter-selection independence from speed values, no ground-truth input access, seed separation, finite outputs and reproducibility. Save per-episode metrics, calibration maxima/assignment, summary, paired intervals, execution manifest and all source code. Use read-only original files, isolated output directories and no overwriting previous results. Raw artifacts are provided in the conversation archive; compact reports/source can be committed.

The bank uses 125 filters versus one per baseline; computational/memory cost is a trade-off, not an equal-compute gain. This is established multiple-model/adaptive-estimation methodology, not a new algorithm claim. The plant and filters share a linear model family on the primary set; the explicit nonlinear and temporal stress tests probe, but do not exhaust, model mismatch. No real-world validation is implied.

## Prior work checked

Peter D. Hanlon (1996), Practical Implementation of Multiple Model Adaptive Estimation Using Neyman-Pearson Based Hypothesis Testing and Spectral Estimation Tools, AFIT dissertation: https://scholar.afit.edu/etd/6058/ . Bank-of-Kalman-filter model selection is established prior art.
University of Michigan, Control Tutorials, DC Motor Speed system modeling: https://ctms.engin.umich.edu/CTMS/index.php?example=MotorSpeed&section=SystemModeling . Standard electrical/mechanical model, not new physics.
