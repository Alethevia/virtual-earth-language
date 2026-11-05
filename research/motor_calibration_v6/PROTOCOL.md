# V6: whole-episode count-stratified calibration — pre-evaluation protocol

2026-11-04 America/New_York. Simulation-only follow-on to PR #9. No paid model/GPU, machinery, trading, hardware/safety certification, novelty or peer-review claim. Original V1–V5 code/results unchanged. Base commit eb48c71c73fc38cdc7121b977bce817e77b6aaae.

## Question and immutable source

V5's primary-channel score obscured 45/100 generic alarms under healthy slow reporting. Test whether calibration stratified by distinct matched acquisition count improves ALL-alarm reliability without hiding wrong channels, abstention or detection loss. Do not add sensors or physical-model fusion. Parent packet generation, three speed channels, passive controller and V5 features remain unchanged.

Pre-calibration implementation SHA-256: calibration_study.py = 4934e3d5e531579cc6881198880c691e2dd7eeb2365b7dc1b6da1830aa385e37. Parent telemetry.py = e26f86c34c18cc57436efc2980134cf8a59c869375068b52acc7181c9ca6b956. Other parent hashes are verified transitively. Published source will match this commitment.

29 integrity tests already passed using development/test-only seeds 37880–37885. No V6 calibration or holdout seeds have run. There was no V6 performance search or tuning on those future seeds. Design is motivated by disclosed V5 results and established rank/group calibration, not invented research novelty.

## Fixed grouping and score

Use V5's exact common-acquisition-time matching, two-second trailing window, at least 3 distinct common acquisitions, latest common sample <=0.6 seconds old, and 0.2-second decision grid from 2.0 through 17.8 seconds. No interpolation, extrapolation, label access or future measurements. Bins: 3–5, 6–25, >=26 common acquisition stamps. Fewer than 3 is unavailable, not healthy. Counts denote distinct timestamps, NOT an estimate or proof of statistical effective independence.

Existing quality-adjusted RMS scores are unchanged. Calibration score is maximum over ALL three pairs and ALL 80 decision times in an episode. Thus dependent overlapping windows are not falsely treated as independent calibration examples. Each calibration episode remains in one fixed count bin. New grouped thresholds apply causally to the count observed at each decision, including separately labelled changing-rate stress.

## Equal-budget calibration and baselines

597 independent calibration seed groups, 199 per bin:
- sparse: 39000–39198, primary report period 50 ticks;
- medium: 39200–39398, primary period uniformly 10 or 20 ticks;
- dense: 39400–39598, primary period uniformly 1, 2 or 5 ticks.
A tick is .01 seconds. Each episode uses RNG seed+8000000 to select uniformly from healthy, healthy_shift, healthy_quantized, healthy_witness_delay, healthy_primary_noise, healthy_high_noise, healthy_nonlinear, then period from the specified bin. Sample/holding is downstream of the unchanged controller tap. Parent quality metadata remains unchanged. Assertions require all calibration decision times available and in the assigned bin.

All new methods receive exactly the SAME 597 calibration trajectories:
1. v5_frozen_quality: historical threshold 1.694663815648237, explicitly separate from equal-budget candidates.
2. pooled_quality: one threshold for all episodes, rank ceil(598*.95)=569.
3. count_quality: PRIMARY candidate; one quality threshold per bin, rank ceil(200*.95)=190 of 199.
4. max_group_quality: use maximum of three grouped quality thresholds everywhere; simpler conservative baseline.
5. count_time_only: same bins/calibration episodes, but unnormalized time-aligned RMS instead of quality correction; strong simpler ablation.
6. always_abstain: never flags or isolates; still reports actual data availability, never credited with detection.

All alarms use strict greater-than. Triple isolation logic is unchanged: a channel differs from both others while the others agree. No threshold is fitted on fault data. Freeze calibration artifact/hash before any holdout execution. The expanded calibration budget vs historical V5 is disclosed; only same-budget candidate comparisons isolate stratification effects.

## Untouched test set and stress

200 new base seeds 41000–41199 paired across ALL 48 conditions: 9,600 trajectories, NOT 9,600 independent physical devices; six rules ->57,600 method records,288 rate cells. Reuse V5's full 38 conditions unchanged, including coarse quantization, slow updates, delay, voltage/current corruption, asynchronous nonmatching stamps, dropout, false timestamps/quality, and common-mode faults.

Ten added stresses, each healthy/bias pair:
- mid_reporting: primary report period 20 ticks.
- rate_switch: primary period 50 ticks before t=8 s, 1 tick thereafter.
- many_rate_changes: alternate primary period 50/1 ticks every two seconds; last-acquired values are held, stamps remain causal/monotone.
- correlated_noise: add stationary AR(1) noise rho=.9 to primary, variance .75^2-.25^2, RNG seed+7000000, declare correct marginal SD .75. Temporal independence is violated, not marginal variance reporting.
- very_sparse: primary period 100 ticks; insufficient matched data explicitly counted.

Extra packet changes do not affect plant or controller. No added excitation. Calibration uses constant-rate episodes; changing-rate, changed temporal correlation and false metadata are OUTSIDE its assumed calibration regime.

## Metrics — no convenient substitution

Report separately for every method/condition:
- generic alarm episode; for a fault case, generic pre-fault alarm;
- ANY wrong unique-channel accusation anywhere in the episode;
- first unique diagnosis correct (no earlier wrong channel or early diagnosis), and conditional delay;
- historical primary-event metric for comparability, but NOT primary acceptance;
- eventual correct target after onset (labelled weaker than first-correct);
- data availability and post-fault availability; unresolved fraction.
For multiple-fault cases with no declared unique single target, no single-channel claim is credited as correct. Silence, unknown and unavailable are not successful detections.

Locked candidate screen (60 checks):
Healthy families healthy, healthy_shift, healthy_late_shift, healthy_nonlinear, healthy_quantized, healthy_slow_reporting, healthy_witness_delay, healthy_primary_noise, healthy_high_noise, healthy_mid_reporting each require generic false <=10%, ANY wrong-channel <=5%, and mean availability >=90%.
Fault families bias, bias_shift, bias_late_shift, drift, stuck, stuck_noisy_readout, bias_nonlinear, bias_quantized, bias_slow_reporting, stuck_slow_reporting, bias_witness_delay, bias_primary_noise, bias_mid_reporting, aux1_bias, aux2_bias each require FIRST correct unique diagnosis >=90% and post-fault availability >=90%.
All criteria are engineering point-rate screens, not statistical certification. Preserve failures; do not select a new primary method or loosen thresholds after evaluation. Other stresses stay fully visible even if this screen passes.

Wilson95 for each Bernoulli episode metric. Seed-paired 10,000-resample percentile bootstrap, RNG44996, for candidate-minus(frozen,pooled,max-group,time-only) on generic false, wrong-any and first-correct rates. 576 intervals, exploratory and NOT multiplicity-adjusted. Same resample indices within each condition; no independent-window or paired-condition sample inflation.

## Theoretical scope and prior art

The established rank argument applies to a fixed finite-horizon episode score when healthy calibration and future episode scores are exchangeable within a fixed bin. It averages over calibration/test randomness; it is NOT guaranteed conditional on this particular calibration set, for every finer profile, for arbitrary correlation/drift, or for a lifetime of monitoring. Distinct packet counts are not necessarily independent observations. Switching bins within an episode can expose multiple thresholds; no simultaneous 5% guarantee is claimed for that uncalibrated changing-rate process. Report those cases as stress, not a proven fix.

Established references checked: Angelopoulos and Bates, A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification, arXiv:2107.07511 (rank correction, group-balanced calibration, calibration variability); Vovk, Conditional validity of inductive conformal predictors, arXiv:1209.2673. These motivate standard methodology, not validation of this implementation or a new theorem.

## Verification and execution evidence

Retain all source/hash commitments, calibration assignments/maxima, full score/availability/count arrays, per-episode records, representative raw packets, tests, logs, summary and failed criteria. A separately implemented verifier will reconstruct thresholds, every record/rate and direct packet scores; it is same-author checking, not human independent peer review. Run a clean-source replay or cloud replay without modifying evaluation source. New directories only; no overwriting old results. Main and older experiments remain untouched.
