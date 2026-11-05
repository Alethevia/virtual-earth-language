# V7: small readout bias and monitoring horizon — locked protocol

2026-11-05. Bounded simulation audit following PR #10. Base d36ff9b2a57b548da007971e671cbcb0d87f8ad9. Original V1–V6 source/results remain unchanged. No paid LLM/GPU, live machine, trade, hardware validation, novelty, safety certification or publication claim.

## Questions and pre-evaluation commitment

H1: an 18-second-calibrated alarm cannot automatically be treated as a 600-second reliability guarantee. Measure cumulative generic alarms and wrong ANY channel at 18, 180 and 600 seconds on the SAME uninterrupted healthy paths.
H2: the conservative universal V6 threshold may hide smaller faults or increase delay compared with its more sensitive count-stratified baseline.
H3: calibrating explicitly for the 600-second horizon may reduce cumulative false alarms, but at a sensitivity cost. Retain all trade-offs; do not promote complexity or select a winner after testing.

horizon.py SHA256 BEFORE calibration: 3e026b467693184d2b26a256e0f00a643ba5c9242eeb64678ae00bcaaa0ebdb1.
Parent calibration_study.py SHA256: 4934e3d5e531579cc6881198880c691e2dd7eeb2365b7dc1b6da1830aa385e37. Parent hashes checked transitively, including unchanged V5 telemetry.py.
25 integrity tests passed on development-only seeds 45880–45889. One initial test incorrectly required exactly five sparse acquisitions at every decision; corrected BEFORE calibration to four or five depending on window phase. Experimental source did not change. Development inspected runtime/shapes, not any calibration/holdout outcomes. Preserve the failed test log.

## Important scope change: readout-only faults, not feedback faults

A nominal healthy DC motor uses the original physical equations, exact ZOH discretization, +/-12 V PI arithmetic, noiseless speed feedback and randomized references (25–110 rad/s, every 5 seconds) / loads (.005–.035 Nm, every 3 seconds). State persists across the full 600 seconds; no resets at 18-second boundaries. This is an explicitly NEW background generator, not claimed bit-for-bit parity with the old full simulator. PI arithmetic is checked against the old implementation.

Three noisy speed channels observe that healthy trajectory. Bias injection is AFTER the feedback tap, into only the primary diagnostic readout before sample/holding. The controller never sees it. Thus this isolates diagnostic observation/horizon effects, NOT closed-loop responses to a failing control sensor. Do NOT compare new percentages to old feedback-fault percentages as an algorithm-only improvement.

The unchanged V5 detector receives only packet values, causal acquisition stamps and declared quality; never true speed, condition, onset, amplitude or future observations. Correct time matching removes the common speed waveform from pair differences. This algebraic fact is tested and limits the motor-specific interpretation. Auxiliary offsets independently uniform [-.03,.03], correctly bounded. Common-mode failure remains outside this audit and is tested algebraically, not claimed fixed.

## Profiles, scores and decision rules

Four fixed profiles: dense_iid, sparse_iid, dense_ar, sparse_ar. Dense primary reports at 100 Hz, sparse every .5 seconds; auxiliaries at 100 Hz. All timestamps/metadata are truthful, channels synchronized at acquisition. Base independent Gaussian noise SD .25 on each channel. AR profiles add stationary AR(1), rho=.9, to primary with variance .75^2-.25^2; declared primary marginal SD is .75. No dropout, quantization, lying metadata or asynchronous-phase remedy is attempted here.

Unchanged V5 quality-adjusted pair RMS: trailing 2-second window, distinct common acquisition stamps, minimum three, maximum age .6 seconds, decision every .2 seconds from t=2.0. Sparse windows have FOUR OR FIVE common acquisitions, not five independent repeated packets. Overlapping windows and temporally correlated samples are not independent experiments.

Five fixed rules, same received measurements:
1. v6_count: historical quality thresholds [2.0307216952958402,1.6532623640481576,1.275003768049613] for 3–5,6–25,>=26 matches.
2. v6_universal: historical conservative 2.0307216952958402 at every decision.
3. new_short_universal: new 18-second calibrated conservative threshold.
4. new_long_universal: PRIMARY finite-600-second candidate.
5. always_abstain: no alarm/isolation, never credited with detection.

New short/long rules have identical form and sample paths; only calibration horizon differs. No new classifier or additional sensors. All alarms use strict greater-than; three-channel isolation remains the old two-disagree/other-pair-agree rule.

## New calibration, frozen before any test

199 independent paths PER profile, 796 total. Ranges: dense_iid 47000–47198; sparse_iid 47300–47498; dense_ar 47600–47798; sparse_ar 47900–48098. For EACH path compute whole-episode maximum over all three pairs at decision times <18 seconds and <600 seconds. Each profile threshold uses rank ceil(200*.95)=190 of 199. Each universal rule takes the MAXIMUM of the four corresponding profile thresholds.

These new calibrations include correlated noise absent from V6's calibration and consume longer traces; comparisons to historical rules change the calibration information budget. Only short vs long NEW rules isolate the duration change on the same 796 paths. Freeze numerical thresholds and calibration hash publicly before any holdout. No fault data for calibration.

## Untouched test set and pairing

200 new base seeds 50000–50199, paired across four profiles and six nonzero amplitudes: .125,.25,.5,1,2,6 rad/s. Sign is randomized once per base seed and shared across profiles/amplitudes.
- Healthy: 600-second continuous trajectory, evaluated at prefix horizons 18,180,600 WITHOUT resetting alarms or state.
- short_fault: inject at exactly 10 seconds, assess through <18 seconds.
- late_fault: inject at separately sampled uniform [300,330] seconds; assess through <600 seconds. Fault onset is supplied only to the evaluator.
There are 4*200*(1+6+6)=10,400 distinct scenario trajectories, but only 200 independent base test seed groups. Calibration/test sets disjoint. Healthy-prefix summaries and amplitude/profile copies are paired, not extra independent runs. Five rules and three healthy prefixes yield 60,000 episode-method-horizon records / 300 aggregate cells.

## Metrics, no survivor filtering

For every method/profile/amplitude/mode: generic alarm by horizon; generic pre-fault alarm; any wrong unique channel anywhere; FIRST unique diagnosis correct; correct within 5 and 30 seconds; eventual correct after onset (explicitly weaker); availability; pre-fault unique alarms; conditional delay with denominator; capped 30-second delay assigning 30 seconds to failures; alarm bursts and flagged 18-second epochs as descriptive load, NOT independent samples. Every late-fault result includes ALL 200 seeds, including pre-fault failures, not only survivors.

Locked engineering screen for new_long_universal, 20 checks (5 per profile): 600-second healthy generic false <=10%, wrong any channel <=5%, availability >=95%; 6-rad/s late bias FIRST correct within5s >=90%; .5-rad/s late bias FIRST correct within5s >=80%. These are point-rate screens, not certification. Preserve failure; do not relax the small-fault criterion. Compare all dose-response curves rather than report only 6-rad/s successes.

Wilson95 per proportion. 5,000-resample seed-paired bootstrap, RNG44997, for long candidate minus each of historical count, historical universal and new short; metrics generic_false,wrong_any,within5s,first_correct. Same indices across contrasts within each cell. Intervals descriptive/exploratory, NOT multiplicity-adjusted. No independence or lifetime claim from distinct timestamps, zero observed errors, or a finite 600-second run.

## Verification and theoretical scope

Retain all source hashes, pre-evaluation tests, calibration maxima, all per-tick decisions in compact arrays, per-episode records, 12 complete representative packet/score traces, logs and results. Reconstruct every record/rate/interval in separately implemented postprocessing and check representative scores directly. Same-author verification is NOT third-party review. Cloud same-seed replay is not new independent scientific evidence.

Whole-path rank calibration can permit dependence WITHIN a path when calibration and future healthy paths are exchangeable within the specified fixed profile/horizon. Guarantees average over calibration/test randomness, not conditional on this specific calibration set. A 600-second calibrated threshold is not anytime-valid or safe for unlimited repetitions. No confidence-sequence/e-process implementation or guarantee is claimed.

Primary references checked: Angelopoulos & Bates, arXiv:2107.07511 (rank calibration and validity assumptions); Howard et al., arXiv:1810.08240 / Annals of Statistics 2021 (uniform-in-time inference differs from fixed-horizon monitoring). Established ideas, not original methodology. Hardware, calibration drift, repeated-reset policies and longer-than600s lifetime exposure remain unvalidated.
