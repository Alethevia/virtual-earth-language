# V5: timestamp-aware and quality-aware sensor comparison

**29/29 targeted primary-attribution/availability checks PASS. General low false-alarm or robust diagnosis is NOT established.** Simulation only; established time alignment and uncertainty reasoning, not a new algorithm, hardware validation, safety certification or accepted paper. Original V1-V4 source and results are unchanged.

## Provenance and execution

Protocol/source commitment BEFORE calibration: `8383330da33dfeae661ca7d2e6714c9c84cbe63a`. Calibration commitment BEFORE holdout: `69d44070a79234cde121a16e9349ec78e0d77638`. Source hashes match the published implementation.

199 calibration trajectories, 3,800 held-out trajectories (38 conditions x 100 seed groups), six methods, 22,800 method records, 228 rate cells. Only 100 independent base evaluation seeds: cross-condition copies are paired, NOT independent physical devices. 25 integrity tests passed locally. Separately implemented verification rebuilt every record/rate, four threshold ranks, 114 paired bootstrap intervals and direct scores from 38 representative packet traces (max difference 7.106e-14). Same-author checks, not independent human peer review. CI status must be checked separately.

## Intervention

Same three simulated speed sensors and unchanged passive controller as V4. Add declared acquisition timestamps, noise SD, quantization step and offset bounds. This is extra instrument information, not equal-information superiority; real metadata accuracy must be established separately.

Only distinct common acquisition timestamps in a trailing two-second window are compared. Repeated held packets are NOT independent samples. Require at least three matches and latest match age <=.6 s. No interpolation/extrapolation or future data. Pair differences are optionally reduced by declared quantization/offset bounds and normalized by declared independent noise. Unique isolation still assumes a single faulty channel. No physical-model fusion is implemented in V5.

Rules: original V4 raw with historical threshold; same raw recalibrated; long-window-only raw; time alignment; time+quality candidate; always abstain. All new thresholds use the same mixed healthy calibration episodes. Historical fixed threshold is explicitly separate.

## Same-seed results, every entry /100

Healthy rows mean wrong PRIMARY-channel accusations; fault rows mean valid first PRIMARY accusations, excluding earlier primary false alarms. This is NOT the same as generic anomaly detection or first correct isolation of any channel.

| Condition | V4 frozen | Raw matched | Time only | Time + quality |
|---|---:|---:|---:|---:|
| healthy_quantized | 100 | 0 | 0 | 0 |
| bias_quantized | 0 | 0 | 100 | 100 |
| healthy_slow_reporting | 100 | 48 | 0 | 4 |
| bias_slow_reporting | 0 | 41 | 100 | 98 |
| healthy_witness_delay | 100 | 0 | 0 | 0 |
| bias_witness_delay | 2 | 0 | 100 | 100 |
| healthy_primary_noise | 100 | 0 | 0 | 0 |
| bias_primary_noise | 0 | 0 | 100 | 100 |
| healthy_high_noise | 0 | 0 | 2 | 0 |
| healthy_coarse_quantization | 100 | 0 | 100 | 0 |
| bias_coarse_quantization | 0 | 0 | 0 | 98 |

Ordinary bias/drift/stuck and declared single-witness faults are detected/isolated in 100/100 candidate cases. The time-only simpler ablation also satisfies the same point-rate requirements in a descriptive post-hoc application: the full candidate is NOT universally better. It adds four false-primary episodes in the slow-reporting family (paired difference +.04, exploratory interval [.01,.08]); it removes coarse-quantization false accusations and recovers 98/100 corresponding faults. Both gains and regressions remain reported.

## Crucial metric limitation

Healthy slow reporting has **45/100 generic anomaly episodes**, **6/100 episodes with any unique-channel accusation**, but only **4/100 ever accusing the primary**. The targeted screen addresses the last quantity, not all alarms. Thus passing it does NOT establish low overall false alarms. Slow-reporting bias has 98/100 valid first-primary detections but only 95/100 correct FIRST unique diagnoses; two early primary and other early wrong-channel outputs are not hidden. Some first-primary delays are zero because faults coincide with a sample/decision tick, not because arbitrary future faults are anticipated.

A mixture-level 5% calibration target does not guarantee 5% within every subgroup. Window duration, distinct sample count and declared-noise scaling change score distributions. Gaussian noise is unbounded and independence is assumed, not proven. Rate intervals and all paired intervals are saved; they are exploratory and not multiplicity-adjusted.

## Falsification cases

- Two witnesses share a bias: 100/100 wrongly blame healthy primary. Three-way shared bias: zero candidate detections and zero generic alarms.
- Delayed readings falsely stamped as current: 100/100 healthy-primary accusations; subsequent real faults have zero valid first-primary detections.
- Primary noise SD .75 reported as .25: 100/100 wrong healthy-primary accusations; later bias is lost after early alarms.
- Falsely claiming coarse resolution for a precise biased sensor: 0/100 candidate detections, while time-only detects 100/100.
- Nonmatching asynchronous sample phases: 0% comparable-data availability and 0/100 bias detections. This exact-match method is NOT general asynchronous fusion.
- Witness dropout after 3 s: only 11.25% overall availability and 0/100 subsequent bias detections. Silence is NOT success.

No source, threshold, seed or screening criterion was changed after holdout. The first independent-verifier attempt hit a 45-second execution limit because it repeatedly decompressed NPZ arrays; only postprocessor array caching was improved, not experimental outputs or code.

## Reproduce

```bash
cd research/motor_telemetry_v5
python -m pip install -r requirements.txt
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m unittest -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python run_all.py --out results/reproduced
python verify.py results/reproduced
```

Use a new output directory. Same-seed cloud replay is not additional independent evidence. No paid LLM/GPU, live machine or trading API is used. Supplied observations change no control signal; additional real timestamping, characterization, power and hardware costs remain unmodeled.

Prior work: NIST acquisition timestamps, https://www.nist.gov/el/intelligent-systems-division-73500/sensors-1588 ; NIST uncertainty propagation, https://physics.nist.gov/cuu/Uncertainty/combination.html ; NASA redundancy normalization and path independence, https://swehb.nasa.gov/spaces/SWEHBVD/pages/102695725/8.09+-+Software+Safety+Analysis . These sources motivate principles; they do not validate this implementation or its statistical guarantees.
