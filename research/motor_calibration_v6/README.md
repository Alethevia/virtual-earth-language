# V6: count-stratified calibration, full-alarm accounting and a simpler-baseline counterexample

**60/60 predeclared checks PASS, but count stratification is NOT uniformly better.** Simulation-only; established rank/group calibration, not a new algorithm, hardware validation, accepted paper or safety guarantee. Original V1–V5 source/results unchanged.

## Provenance and actual local execution

Protocol + source hash before calibration: `1b3dcecc8675a05ae0d5be2f67a718a412d12016`. Corrected calibration lock before holdout: `b0e8903350bd8cdfd14f4ba4674c34ca2ec71dd6`. An earlier lock commit contained a truncated hash transcription; it was corrected before ANY holdout and is preserved in history. Neither scientific code nor thresholds changed.

597 calibration episodes (199 per count bin), 9,600 held-out trajectories (48 conditions x 200 base seeds), six methods, 57,600 episode-method records, 288 result cells. Only 200 independent holdout base seed groups; conditions are paired, NOT independent physical devices. 29 integrity tests passed. A separately implemented verifier rebuilt every record/rate, eight threshold values (seven fitted, one derived maximum), 1,728 Wilson intervals, 576 paired bootstrap intervals and 48 raw-packet examples; max score difference 7.106e-14. Same-author verification, not independent human peer review. Check CI separately.

## Method and fairness

Keep V5's timestamp matching, raw measurements, quality normalization, isolation logic and controller unchanged. Group by distinct common acquisitions in a trailing two-second window: 3–5, 6–25, >=26. These are distinct timestamps, NOT a proven statistical effective sample size. Calibration score is the whole-episode maximum across ALL times and ALL three pairs; overlapping windows are not counted as independent calibration examples.

All new methods receive the same 597 calibration episodes. Compare pooled threshold, three count-specific thresholds (primary), maximum of group thresholds applied everywhere (simpler conservative baseline), grouped time-only scores, always abstain, and V5's historical threshold. The larger calibration budget vs old V5 is explicit.

Quality thresholds: historical 1.694664; same-budget pooled 1.883690; sparse/mid/dense 2.030722/1.653262/1.275004; conservative universal 2.030722. A lower dense threshold is more sensitive, not automatically more robust.

## New-sample results, every entry /200

Healthy rows: ANY generic alarm / ANY wrong-channel accusation. Fault rows: FIRST unique diagnosis correct (no earlier wrong channel).

| Condition / metric | V5 frozen | Pooled | Count-stratified | Conservative universal | Grouped time-only |
|---|---:|---:|---:|---:|---:|
| healthy slow updates: generic alarms | 80 | 21 | 6 | 6 | 0 |
| healthy slow updates: wrong any channel | 9 | 2 | 0 | 0 | 0 |
| bias + slow updates: first correct | 197 | 199 | 200 | 200 | 200 |
| stuck + slow updates: first correct | 197 | 199 | 200 | 200 | 200 |
| healthy intermediate updates: generic alarms | 5 | 0 | 8 | 0 | 0 |
| healthy temporally correlated noise: generic alarms | 0 | 0 | 52 | 0 | 0 |
| healthy temporally correlated noise: wrong channel | 0 | 0 | 38 | 0 | 0 |
| bias + correlated noise: first correct | 200 | 200 | 175 | 200 | 200 |
| healthy coarse quantization: wrong channel | 0 | 0 | 0 | 0 | 200 |
| bias + coarse quantization: first correct | 199 | 199 | 199 | 199 | 0 |

Sparse healthy generic alarms fall 40% ->3% vs old V5 (paired difference -37 percentage points, exploratory 95% interval -43.51 to -30.5). Against the SAME-budget pooled threshold the reduction is 10.5% ->3% (-7.5 points, interval -11.5 to -4). However conservative universal produces the SAME sparse result, and time-only is better there. Do not attribute everything to stratification or report universal superiority.

The locked 60 checks jointly require generic false <=10%, wrong ANY channel <=5% and availability >=90% in ten healthy families, plus first-correct >=90% and post-fault availability >=90% in fifteen fault families. Candidate passes all. Descriptive application of the same screen: conservative universal and grouped time-only also pass 60/60; historical V5 and pooled each pass 59/60; always-abstain passes 45/60. This descriptive comparison does not retrospectively select a new preregistered winner.

## New adverse result: counts are not independence

AR(1) noise rho=.9 is added with correctly declared marginal SD .75. The dense-bin threshold produces 52/200 generic healthy alarms and 38/200 wrong unique accusations; the simpler conservative threshold has zero in these particular samples. Subsequent bias first-correct falls to175/200, compared with200/200 for the simpler alternatives. Grouping by timestamp count fails to account for changed temporal dependence. No correlation-aware fix is implemented here.

The simpler universal threshold is a strong baseline for the NEXT study, not an established deployment solution. Its coarse-quantization fault median delay is .4 seconds vs .2 for the grouped rule (among the same199 detections), so equal detection counts need not mean identical timeliness. Only large declared fault sizes are studied; no superiority on smaller faults is asserted.

## Other failures remain visible

Wrong timestamps or underreported noise:200/200 wrong healthy-channel accusations for quality-based rules. Exaggerated uncertainty hides faults:0/200 first-correct. Two biased witnesses still wrongly blame healthy primary200/200; all-common bias remains invisible. Nonmatching asynchronous packets give0% availability and no detections. Dropout gives11.25% overall availability and no subsequent detections. Very sparse 1-second reports have20% availability:199/200 first-correct for the candidate does NOT establish continuously available diagnosis; healthy generic alarms22/200 remain. Changing reporting rates had low errors on this test, but no formal guarantee is claimed.

Statistical bounds require exchangeable healthy episode scores within a fixed bin and average over calibration/test randomness. They are NOT guarantees for this particular calibration set, every profile, changed temporal correlation, switching multiple bins or lifetime monitoring. Gaussian independence is not inferred merely from distinct timestamps. All576 paired intervals are exploratory and unadjusted.

## Execution notes and reproducibility

An initial serial local evaluation hit a tool timeout after four completed conditions. Unfinished example files were quarantined and that condition was restarted with unchanged code/seeds/thresholds. Remaining conditions ran in separate process outputs; no completed record was overwritten. No hidden tuning or parameter change followed holdout inspection.

```bash
cd research/motor_calibration_v6
python -m pip install -r requirements.txt
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m unittest -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python replay.py --out results/reproduced --workers 2
python verify.py results/reproduced
```

Use a NEW output directory. Cloud replay uses the same seeds, not more independent evidence. No paid LLM/GPU, live machinery or trading API. Added sensor/metadata cost remains unmodeled from prior stages.

Prior art: Angelopoulos & Bates, arXiv:2107.07511 (group-balanced calibration, rank correction, calibration variability); Vovk, arXiv:1209.2673 (conditional validity). These motivate standard methods; they do not certify our implementation.
