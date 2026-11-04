# V4: information-budget intervention and attribution audit

Locked before calibration or holdout, 2026-11-04. Simulation-only. Parent commit `57768d20b2bcd161fac90fcddc3b191c257a6d14` (active-triage V3, PR #7), NOT the older local passive-only V3 archive. Parent code is unchanged. No hardware, new-algorithm, safety-certification or publication claim. No paid LLM/GPU or real-machine control.

## Question

Does an improvement require better software or additional independent observations? Separate generic anomaly detection from unique speed-channel attribution. Compare the old conditional V3 output, intentionally forced-primary interpretation, unlocalized reporting, an exact-flatline baseline, one additional speed witness, and two additional speed witnesses. This is an information-budget intervention, NOT equal-input algorithmic superiority. Majority voting/redundancy are established techniques.

## Development and immutable implementation

No hyperparameter search or empirical development sweep. Integrity-only seeds 23990–23993; 21 tests passed, including original-plant parity, source hashes, causal prefixes, second implementation of RMS windows, no truth-state detector input, sensor permutation, common-mode counterexamples and bias-rank algebra. Calibration/evaluation below not run at commitment.

SHA-256:
- motorbench.py caea2a328becfff82cf915511b157c76b7dd01ca43a2c884e1f2804c566a4834
- bank_study.py e6aa4ccba89aa53c20f9586331344093301947c6c8e59edcde20ca3ab7bf6f1d
- study.py 419240774aabbd96d84a60ad72d91567ab55c1ffa4dc33fed6128ff6b246b0ca
- box_solver.py e0f4cf9863787a905e02a0c79f84d090f50d020f0d6cb116811416b84bf62b7d
- experiment.py 15eddca6510854e8f791d14aab6b7b13e3566909c078314dff6e6c09947a9e3d

## Inputs and algorithms

V3 input remains measured voltage, current and primary speed. Two optional witnesses observe the SAME physical true speed, independently adding Gaussian SD .25 rad/s and an episode-fixed uniform offset in [-.03,.03] rad/s. RNG seed+3000000; these are simulated sensors, not privileged truth supplied to the detector. Original primary sensing/PI behavior remains untouched. All detectors are pure functions of received measurements; no true parameters, states, fault labels or onsets enter them.

Common decision grid 2.0,2.2,...,17.8 s; trailing 41 samples (0.4 s) for RMS differences. Pair distances d01,d02,d12 use all samples in each causal window.

Seven fixed rules:
1. v3_forced_primary: recalibrate original triage score and interpret threshold exceedance as primary attribution. This FORCED interpretation does not mean V3 itself proved unique causality.
2. flatline: declare primary when its complete .4-s window is EXACTLY constant; intentionally a simple baseline for synthetic shortcut auditing.
3. dual_forced_primary: d01>Tdual, naively trusting witness1; potentially confounds which of two sensors failed.
4. triple_consensus: uniquely isolate channel j iff its two pair distances exceed Ttriple and the remaining pair agrees (<=Ttriple). Any pair exceedance is a generic anomaly; no unique channel means unresolved.
5. dual_unlocalized: same dual anomaly, never unique primary attribution.
6. v3_unlocalized: same V3 anomaly, never unique primary attribution.
7. always_abstain: no anomaly or isolation.

Zero attribution errors by refusing all answers is not successful isolation; report both alarm and unique-correct rates. No online fault-tolerant controller is implemented.

## Calibration and fresh holdout

199 seed groups 26000–26198. RNG 774413 assigns healthy or healthy_shift with probability .5, paired across passive/active modes. 398 calibration trajectories. Rank ceil(200*.95)=190, strict > alarm. Per-mode thresholds: V3 episode max; dual d01 episode max; triple maximum over all three pairs and all decision ticks. Triple calibration controls a combined score, not every conditional subgroup. Fixed rules, no threshold selection on faults.

Holdout 28000–28099: 100 base seed groups x 23 conditions x 2 modes = 4,600 trajectories. Seven rules ->32,200 episode-method records and 322 rate cells. Conditions/modes share base seeds; do NOT claim 4,600 independent devices. Active adds the SAME V3 +/-8 rad/s target perturbation every .4 s after t=2. Passive has none. Extra witnesses never affect control. Compare passive vs active and report their actual tracking/energy costs separately; extra sensor power/price is not modeled.

Original 14 V3 conditions unchanged: healthy, healthy_shift, bias, bias_shift, drift, stuck, startup_bias, healthy_late_shift, bias_late_shift, healthy_outside_bank, healthy_nonlinear, bias_nonlinear, healthy_voltage_bias, healthy_current_bias.

Nine additional controls (post-controller diagnostic telemetry unless otherwise specified):
- stuck_noisy_readout: original closed-loop stuck sensor, with fresh .25-rad/s downstream readout noise from t=10 (seed+4000000). It is not a new noisy-sensor feedback simulation.
- aux1_bias / aux2_bias: one witness gets signed 6 rad/s at independent uniform [10,13] time; primary and plant are healthy.
- two_aux_common_bias: both witnesses receive the SAME signed offset at the same time; breaks the at-most-one-fault assumption.
- all_common_bias: all three received speeds acquire the SAME signed offset; controller/true plant unchanged; tests common-mode telemetry blindness.
- healthy_quantized: primary telemetry rounded to 2 rad/s, sensor/plant healthy; undeclared resolution mismatch with calibration is explicitly a stress.
- healthy_slow_reporting: primary telemetry updated every .5 s, held between updates; diagnostic algorithms do not receive age metadata. This is healthy lower-rate reporting, not an injected sensor freeze.
- healthy_witness_delay: both witnesses delayed .1 s; tests synchronization assumption.
- healthy_high_noise: all three received speeds have SD .75 rad/s (primary gets independent extra noise to reach this variance); benign noise mismatch, not frozen data.

## Predeclared screens, metrics, and failure retention

For each mode, single-fault screen requires triple primary false attribution <=10% separately in healthy, healthy_shift, healthy_late_shift, healthy_voltage_bias, healthy_current_bias, aux1_bias and aux2_bias; primary valid detection >=90% separately in bias, bias_shift, bias_late_shift, drift, stuck and stuck_noisy_readout; and correct FIRST unique isolation >=90% in each single-witness fault. Both passive and active reported, no choosing a winner. These are empirical engineering screens, not certification.

Every common-mode, nonlinear/noise, quantization, delay and slow-reporting failure remains visible regardless of targeted screen outcome. A targeted pass is not a general robustness pass.

Report primary first-declaration false alarms, valid detections, early declarations, misses, conditional delays; first unique channel and correctness; generic anomaly alarms/detections; unresolved time fractions. A pre-fault declaration cannot count as valid detection. Never credit unlocalized/always-abstain with unique detection.

Wilson 95% intervals per rate. Seed-paired bootstrap, 10,000 resamples, RNG44993, triple minus forced-V3, exploratory and unadjusted; contrast changes information budget. No independence or significance claims from multiplying methods/timesteps.

Save all decision features and per-episode records, representative received traces, reproducible simulator/source, calibration and source hashes. Verify all threshold ranks and result counts independently from archived features, replay representative direct RMS calculations. Do not overwrite outcomes or relax criteria.

## Analytical check and prior work

For constant offsets and fixed R,K, electrical residual offset is d=bu-R*bi-K*bw (away from current-offset transition). The three bias columns [1,-R,-K] are collinear, rank1; this electrical relation alone cannot uniquely attribute all three offsets. This is restricted algebra, NOT a universal impossibility claim about all additional dynamics/controller metadata. Two disagreeing speed readings also do not identify which sensor is wrong without additional assumptions. Triplex uses the explicit assumption that at most one speed channel is faulty and the others are synchronized/independent.

Checked primary sources: NASA Joshi et al. (2014), https://ntrs.nasa.gov/citations/20140006008 ; NASA Software Engineering Handbook, section 8.09 software safety analysis (mid-value selection and common-cause paths), https://swehb.nasa.gov/spaces/SWEHBVD/pages/102695725/8.09+-+Software+Safety+Analysis ; MathWorks Fault Analyzer fault properties, https://www.mathworks.com/help/fault-analyzer/ug/fault-properties.html . No literature-level novelty claim.
