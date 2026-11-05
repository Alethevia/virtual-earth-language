# V8 signed evidence accumulation — pre-evaluation protocol

2026-11-05. Follow-on to V7 PR #11, base ef490cd7cb82a26c3531e873adb179cb08c0ef0c. Simulation only, downstream diagnostic readouts; no actual machine, paid LLM/GPU, novelty, safety or publication claim. Original V1–V7 sources/results unchanged.

## Immutable implementation and development

cusum_study.py SHA256: 82df678ef7ab82db02580c5b6c058d97f9c727f16f8830814a2bd2934402268a.
Parent horizon.py: 3e026b467693184d2b26a256e0f00a643ba5c9242eeb64678ae00bcaaa0ebdb1; all earlier parent hashes checked transitively. Published source will match these commitments. 24 integrity checks passed on development-only seeds 54880–54882 and deterministic constructions. No V8 performance search; no calibration/holdout observations have been run. Tests verify distinct-packet updates, causal prefixes, direct recurrence, old RMS parity, common-offset/sign invariance, no labels/truth as detector inputs and correct first-diagnosis accounting.

## Research questions

H1: Can standard signed CUSUM improve timely small-bias detection without unacceptable 600-second generic false alarms or wrong-channel accusations?
H2: Is it actually better than a simpler fixed two-second signed mean, given identical healthy calibration paths, observations, metadata and rate grouping?
H3: Does a single universal CUSUM threshold lose sensitivity compared with rate-specific thresholds? Rate is inferred causally from matched timestamps, not the true noise-profile label.
H4: Stronger temporal correlation, alternating/brief faults and common-mode faults may defeat accumulation or attribution; retain all such failures.

## Unchanged observations; fixed algorithms

Use V7's continuous healthy nominal PI motor and three diagnostic speed readouts. Faults NEVER enter the feedback controller. Primary reporting is 100 Hz (dense) or 2 Hz (sparse); auxiliary reports 100 Hz. Noise profiles are the original independent SD .25 and primary additional AR(1) rho=.9 with correctly declared marginal SD .75. Auxiliary fixed offsets lie within +/- .03 rad/s. True speed creates simulated sensor observations but is not passed to the detector. Metadata is truthful except no new metadata-lie test is added here; prior limitations persist.

Only distinct common acquisition times are consumed. Held retransmissions are not independent observations. Compare on the original .2-second grid from 2.0 to 599.8 seconds; availability uses at least 3 common timestamps in the trailing two seconds and latest age <=.6 seconds. No future readings, interpolation or truth labels.

For pair difference d=y_a-y_b and declared nuisance bound B=(quantum_a+quantum_b)/2+offset_a+offset_b:
- RMS: unchanged V5/V7 quality-adjusted RMS sqrt(mean(max(0,abs(d)-B)^2/(sigma_a^2+sigma_b^2))) over the trailing 2 seconds.
- Mean: max(0,abs(mean(d))-B) over the same distinct-time window, rad/s. This strong simpler baseline is NOT an independently optimized CUSUM.
- CUSUM: Splus=max(0,Splus+d-.25-B); Sminus=max(0,Sminus-d-.25-B), updated ONCE per new common acquisition. Score=max(Splus,Sminus). The fixed reference allowance .25 rad/s is half the target .5-rad/s shift. Zero initialization; ordinary max-with-zero recursion is intrinsic to CUSUM, but there is NO extra restart at alarms, faults, epochs or evaluation horizons. It is an unweighted observation-count statistic, not physical elapsed time; rate dependence is explicitly tested. The entire history is kept in the two states. At unavailable decision times, no diagnosis is credited.

Unique-channel rule is unchanged: a channel disagrees with both others while those two agree. This assumes a single bad channel. It does NOT solve two-common or all-common faults. Generic anomalies, unresolved cases, and unique diagnoses remain separate.

Seven rules: historical V7 600s RMS threshold 2.4746751835866267; newly calibrated universal RMS; rate-specific RMS; rate-specific signed mean; universal CUSUM; rate-specific CUSUM (PRIMARY candidate); always abstain.

Rate bins at a decision: >=26 matched timestamps means dense, otherwise sparse (only valid decisions count). No true rho/profile is available to the decision rule. This is not a claim that timestamps imply statistical independence.

## Calibration, committed before holdout

Four disjoint sets of 199 seeds: 57000–57198 dense_iid; 57300–57498 sparse_iid; 57600–57798 dense_ar; 57900–58098 sparse_ar. Total 796 healthy 600-second paths. For each stream/profile, take the maximum over ALL three pairs and ALL decision times per path, then order rank ceil(200*.95)=190 of 199. Each rate threshold is the maximum of its iid/AR profile thresholds. Universal is the maximum across rates. All new methods use EXACTLY these paths and the same horizon. Freeze numerical thresholds and their artifact hash before running any test observations. No threshold fit on faults.

The standard whole-path rank argument concerns exchangeable paths in the specified profile/horizon and averages over calibration/test randomness. It is NOT conditional-on-this-calibration, arbitrary-subgroup, arbitrary-dependence or anytime/lifetime coverage. This implementation does not inherit an optimality theorem for known iid likelihood ratios.

## Locked untouched test observations

Base seeds 61000–61199, paired across all scenarios. Main four profiles each include: healthy; primary persistent offsets .125,.25,.5,1,2,6 rad/s; aux1 and aux2 offsets of 6 separately; both auxiliaries common offset6; all three common offset6. Onset uniformly [300,330] seconds and sign +/- via separate RNG seed+12000001. Healthy paths report cumulative prefixes18,180,600 without detector restart. Aux faults have their actual target channel; multi-fault cases have no unique target and no unique-channel accusation is credited as correct.

Additional primary .5-rad/s scenarios on dense_iid and sparse_iid: sign alternates every .5s after onset, or one two-second pulse. Pulse first-correct diagnosis must occur before pulse end; accusations after recovery are counted as wrong and cannot rescue eventual detection.

Two stress profiles dense_ar99 and sparse_ar99: same truthful marginal SD .75, but primary AR rho=.99 (new stream seed+12000000); each healthy, primary .5, primary6. These are outside calibration correlation. No thresholds are re-tuned.

Total54 scenario families x200 seeds=10,800 trajectories, NOT independent devices. Healthy prefixes add12 horizon evaluations per seed. Seven rules yield92,400 records and462 cells. Only200 independent base test seed groups. Every scenario remains visible.

## Metrics and fixed screen

Per complete path: generic alarm, pre-fault generic alarm, ANY wrong unique-channel accusation, FIRST unique diagnosis correct, eventual correct, first generic valid, early unique diagnosis, 5s/30s first-correct deadline, conditional median delay, failure-penalized restricted delay30s, data availability. No survivor filtering. A generic unresolved alarm is not a correct unique diagnosis; silence is not success.

PRIMARY screen identical in shape to V7: for each of the four main profiles, 600s healthy generic false<=10%, healthy wrong ANY channel<=5%, availability>=95%, .5-rad/s primary FIRST correct within5s>=80%, 6-rad/s FIRST correct within5s>=90%. Twenty point-rate engineering checks, not certification. Do not change them after outcomes. Other methods may be compared descriptively, not retrospectively relabelled the preregistered candidate.

Wilson95 for each Bernoulli metric; paired bootstrap5000 resamples, RNG45008, candidate-minus(frozen RMS,rate RMS,rate mean,universal CUSUM), metrics generic_false/wrong_any/within5/first_correct. Paired intervals are exploratory, unadjusted for multiple comparisons. Every base seed remains in the denominator. Delay is reported with detection counts.

## Verification and references

Save source hashes, calibration maxima, all per-time label/flag sequences, all records/intervals and18 full representative raw/score trajectories. Separate implementation checks calibration ranks, records and selected full score trajectories including the cumulative recurrence. Clean-source/cloud replay reuses seeds, so it is reproducibility, not additional independent evidence or third-party human review.

Established methods: NIST CUSUM recursion and k choice, https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/cusum.htm . Polunchenko & Raghavan, autocorrelated change detection, https://arxiv.org/abs/1706.00824 . Huang & Veeravalli, finite/unknown-horizon false-alarm and latency objectives, https://arxiv.org/abs/2408.05817 . We use a fixed empirically calibrated finite-horizon rule, NOT their time-varying threshold or its guarantees.
