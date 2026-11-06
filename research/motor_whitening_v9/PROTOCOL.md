# V9: independent healthy commissioning and matched prewhitening — locked protocol

2026-11-05 America/New_York. Simulation only, following V8/PR #12. This is established AR prediction, prewhitening and finite-window matched filtering, NOT a novel algorithm, Google proprietary system, peer-reviewed paper, hardware result, safety function or anytime guarantee. V1–V8 remain unchanged. Base commit d5c8a45b882739400e9901ffa52f2c80d2d13a2f.

## Status and immutable implementation

Recorded BEFORE any V9 healthy model fitting, calibration or holdout. Development used only numerical/integrity seeds 64880–64898; no performance search. 24 tests passed, including causal prefix/future perturbation checks, direct matched-filter sums, transformed-step identity, dense/sparse RMS and CUSUM parity to V8, distinct-packet handling and strict first-diagnosis metrics.

SHA-256 whitening.py = fa91377767f25aa848b0a4193c19c3d1973dd1eeab7488060975104a58f3b4d2.
Git blob whitening.py = 393e66f53071a99de4573683aa117b6d03ae0f45.
SHA-256 test_whitening.py = a5a6accc373832ef3d316f0a42cb99e603d1a46b05f3693af42f2d97bb833df0.
Parent cusum_study.py SHA-256 = 82df678ef7ab82db02580c5b6c058d97f9c727f16f8830814a2bd2934402268a. Earlier parent hashes are transitively checked.

## Questions and information fairness

H1: independently learned healthy temporal dependence improves small-fault timeliness at controlled 600-second false alarms.
H2: filtering observations without also transforming the candidate fault signal can suppress a real persistent shift; explicitly transform the step alternative and test against that ablation.
H3: a simpler raw signed-window scan or two-second mean may perform as well or better; retain them as strong controls.
H4: stronger unseen correlation can invalidate the fitted noise model, and common-mode faults remain non-identifiable from pairwise agreement.

IMPORTANT EXTRA INFORMATION: each of four instrument configurations has an independent matched HEALTHY commissioning batch. Its fitted model and calibration are supplied before monitoring. The detector does not infer the true regime from test labels, but we DO assume the correct commissioning batch is associated with the instrument. This is stronger prior information than V8's rate-only worst-regime pooling. Comparisons between NEW rules control this information/budget; comparison to historical V8 does not establish a pure algorithmic gain. No model is fitted or selected from the monitored trajectory, and no known-healthy prefix of that trajectory is required.

Scope remains V7/V8 downstream diagnostic READOUT faults. The healthy nominal motor/controller background runs continuously for 600 seconds and never sees those injected faults. All compared methods receive identical three-channel observations. No additional hardware, control changes or physical-model fusion. Synchronous common-acquisition timestamps only; no general delayed/asynchronous fusion claim.

## Independently learned noise model

Four configurations: dense_iid, sparse_iid, dense_ar, sparse_ar as in V8. Dense primary100Hz, sparse primary2Hz; auxiliary channels100Hz. In AR configurations primary adds stationary rho=.9 colored noise, truthful marginal SD .75. Only the generator sees rho; model fitting uses measurements.

32 separate healthy paths of60seconds PER configuration: seeds65000–65031,65100–65131,65200–65231,65300–65331 respectively.128 total commissioning paths. Fit each of the three pair differences using pooled within-path-centered autocovariances and Yule-Walker equations with ridge1e-6 times variance. AR order is fixed20 for dense,1 for sparse; never selected on evaluation. Reject unstable fits rather than silently tuning. Save parameters, covariance, spectral radius and residual lag1 diagnostics. The fit is an approximate AR representation of AR-plus-white noise, not an exact known likelihood model. Observations need not become perfectly independent after this fit.

The three pair models are not assumed independent. Maxima over every pair and every decision time are used in path-level calibration.

## Fixed score streams

Consume each distinct common acquisition once. Evaluate at2.0,2.2,...,599.8seconds, without resets at alarms/onsets. Each proposed scan starts only after enough past AR regressors exist. Available requires >=3 common acquisitions in the trailing2seconds and latest age<=.6seconds.

1. rms_matched: unchanged V8 quality RMS over endpoint-inclusive trailing2seconds; newly configuration-calibrated.
2. mean_2s: two-second signed mean, offset allowance removed, normalized by learned marginal SD. Simple strong baseline.
3. signed_scan: maximum standardized absolute signed sum over fixed durations(.2,.5,1,2,5,10,30)seconds, ending at latest available common acquisition. No prewhitening.
4. whiten_naive: same scan on AR innovations, treating the fault alternative as a constant after filtering (intentional ablation).
5. whiten_matched: PRIMARY. Transform the step alternative using the SAME AR polynomial as the observations, then scan its normalized matched inner product.
6. v8_cusum_frozen: historical dense/sparse thresholds170.26237709964514 /9.994218256126453, fixed slack.25 and prior offset allowances. Historical calibration budget differs and is labelled.
7. always_abstain: no flags/isolation; cannot pass fault criteria.

For AR coefficients phi, innovations e_t=d_t-sum phi_l*d_(t-l). A step beginning at k has response g_j=1-sum_(l<=j)phi_l, settling at g_inf=1-sum phi. For length w, the primary score is max(0,abs(sum g_j*e_(k+j))-B*abs(g_inf*sum g_j))/(innovation_SD*sqrt(sum g_j^2)); B is the same declared constant-offset allowance. This is a finite template statistic, NOT an exact generalized-likelihood-optimality or ARMA theorem. Raw scan removes w*B; naive whitened scan removes w*B*abs(g_inf). Window counts are ceil(duration/dt), at least the fixed AR order. Window-bank multiplicity is included in the calibrated maximum, not ignored.

Each pair's score is thresholded. Unique channel attribution uses unchanged triplex logic: it differs from both others while those two agree. Signed directions are discarded after the scan; no added causal-identification claim. The single-fault and independent-witness assumptions still apply.

## Calibration and untouched holdout

Calibration:199 healthy600second paths per configuration, seeds67000–67198,67300–67498,67600–67798,67900–68098. Same796 paths for ALL five new scores. For each configuration/score, rank ceil(200*.95)=190 of199 whole-path maxima across ALL windows, times and pairs. Separate configuration thresholds are a disclosed commissioning assumption. Freeze training/hash before calibration and calibration/hash before holdout.

Holdout:200 new base seeds70000–70199 paired across configurations and scenarios. Late onset drawn uniform300–330seconds and random sign using seed+14000001. Core scenarios per configuration: healthy; primary persistent offsets .25,.5,1,6rad/s; auxiliary1/2 offset .5; two auxiliaries common6; all-three common6. Additionally dense_iid/sparse_iid test alternating +/-.5 every.5seconds and a2second .5pulse. Stresses dense_ar99/sparse_ar99 reuse FROZEN corresponding .9 commissioning model/thresholds and test healthy,.5,6. Total46scenarios x200=9,200 trajectories, NOT independent devices; only200 independent base holdout seed groups. Healthy paths also report18/180/600second prefixes without resets.

## Metrics and locked screen

Preserve generic alarms, generic pre-fault alarms, ANY wrong unique accusation anywhere, FIRST unique diagnosis correct (no earlier wrong or premature accusation), within5/30seconds, eventual correct, pre-fault unique alarms, conditional median delay, restricted30second delay (failures=30), and availability. Two-second pulses cannot be credited after recovery. Multiple/common-fault cases without a unique target cannot receive correct-isolation credit. No survivor-only filtering.

PRIMARY20checks, same engineering goals as V8: each of four core configurations requires healthy600second generic false<=10%, wrong-any<=5%, availability>=95%, .5rad/s within5seconds FIRST correct>=80%, and6rad/s within5seconds FIRST correct>=90%. Point-rate screening, not statistical certification. Do NOT change criteria after outcomes. All auxiliary, transient and stress results remain visible regardless of screen.

Wilson95 per Bernoulli outcome. Seed-paired bootstrap3000resamples, RNG45009, for primary-minus(rms_matched,mean_2s,signed_scan,whiten_naive,v8_cusum_frozen) on generic_false,wrong_any,within_5s,first_correct. Exploratory, NOT multiplicity-adjusted. Same indices per scenario, no window/sample inflation.

## Validation and limitations

Save source, fit/calibration commitments, all threshold maxima, all per-time labels/flags, all records, seed ranges, environment and representative raw packet/full-score examples. Separate direct computation verifies matched numerator/normalization, thresholds, records and summaries. Clean full replay or CI checks unchanged sources. Same-author second implementation and same-seed cloud replay are NOT independent human peer review or additional statistical samples.

No promise that whitening restores small-fault information, no false claim that uncorrelated residuals prove independence, and no lifetime/anytime false-alarm guarantee. Correct instrument-batch association, metadata, finite horizon and stationary commissioning distribution are assumptions. A later study must use new seeds; do not tune on this holdout.

Established primary sources reviewed: NIST autocorrelation guidance https://itl.nist.gov/div898/handbook/eda/section3/eda35c.htm ; NIST Statistical Process Monitoring for Autocorrelated Data https://www.nist.gov/publications/statistical-process-monitoring-autocorrelated-data ; Sun and Zou, Quickest Change Detection in Autoregressive Models, IEEE TIT2024 / https://arxiv.org/abs/2310.08789 . These establish prior concepts, not guarantees for this particular implementation.
