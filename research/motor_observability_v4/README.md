# V4: information-budget intervention, not an equal-input algorithm breakthrough

**Targeted single-fault screens PASS in passive and active modes. Broad robustness is NOT established.** Simulation-only. Established triplex voting, not a new algorithm, hardware result, safety certification or accepted paper. Parent active-triage V3 (PR #7) is unchanged.

## Provenance and completed local execution

Protocol/source hashes committed before calibration: `bfec323bd142b8e107cf5d0adf3890901641df09`. Calibration committed before holdout: `63b5c8e75808e06cec62762988c5162fe7c9a1b2`. Published code matches the committed hash.

398 calibration trajectories + 4,600 new holdout trajectories (23 conditions x 2 modes x 100 seed groups), seven rules, 32,200 episode-method records, 322 rate cells. ONLY 100 independent holdout base seed groups: conditions/modes are paired, not independent devices. 21 integrity tests passed. A separate postprocessor reconstructed all records, all rate cells, all six thresholds and direct RMS windows for 46 representative received traces; max RMS difference 1.251e-12. Same-author checks, not third-party certification. CI status must be checked separately.

## Intervention and assumptions

V3 reads voltage, current and primary speed. One/two added witnesses observe true speed with independent Gaussian SD .25 rad/s and small fixed offsets. True speed generates observations in the simulator but is never given to the detector. Witnesses do not control the motor. Triplex uniquely isolates a channel only if it disagrees with both others and those two agree. It assumes at most one bad, synchronized, appropriately calibrated speed channel. Added hardware/power/maintenance costs are not estimated.

`v3_forced_primary` intentionally interprets a conditional old score as unique attribution. V3 itself did NOT prove unique causality. An unlocalized version retains the same anomaly signal without declaring which channel failed. Likewise two disagreeing sensors cannot determine which is wrong unless one is trusted. Always-abstain and unlocalized controls are NOT credited with unique detection.

## Results on the same new seeds (each /100)

Fault rows are valid first PRIMARY isolations, excluding earlier primary false declarations. Healthy-primary rows are wrong PRIMARY attributions, not all generic anomaly flags.

| Condition | V3 passive | V3 active | Triplex passive | Triplex active |
|---|---:|---:|---:|---:|
| healthy | 0 | 0 | 0 | 0 |
| healthy_shift | 7 | 9 | 0 | 0 |
| bias | 61 | 91 | 100 | 100 |
| bias_shift | 47 | 77 | 100 | 100 |
| drift | 100 | 100 | 100 | 100 |
| stuck | 53 | 50 | 100 | 100 |
| healthy_late_shift | 6 | 6 | 0 | 0 |
| bias_late_shift | 29 | 75 | 100 | 100 |
| healthy_voltage_bias | 48 | 93 | 0 | 0 |
| healthy_current_bias | 46 | 93 | 0 | 0 |
| stuck_noisy_readout | 57 | 52 | 100 | 100 |

Triplex correctly isolates either single faulty witness in 100/100 cases without blaming the primary. Naively trusting witness1 wrongly blames the healthy primary in 100/100 when witness1 is biased. All 15 targeted requirements pass per mode. These are point-rate engineering screens. A 100/100 Wilson interval is approximately 96.3%–100%; 0/100 is approximately 0%–3.7%, NOT population risk guarantees.

Generic healthy anomaly flags still occur in 5/100 triplex cases, with no unique primary attribution. Some fault episodes have earlier generic (unlocalized) flags; first generic valid detection is often 96/100, distinct from 100/100 first unique primary isolation. Do not describe the method as producing no alarms.

## Serious failures, retained unchanged

| Stress | Triplex outcome in each mode |
|---|---|
| Two witnesses acquire the same bias | 100/100 wrongly blame healthy primary |
| All three speeds share a bias | 0/100 unique primary detections; five generic flags are background, not common-mode sensitivity |
| Healthy primary rounded to 2 rad/s | 100/100 wrong primary attributions |
| Healthy primary reports every .5 s | 100/100 wrong primary attributions |
| Both witnesses delayed .1 s | 100/100 wrong primary attributions |
| Existing nonlinear/noisier healthy condition | 100/100 wrong primary attributions |
| Bias with nonlinear/noisier plant | Only 8/100 valid primary detections survive early errors |
| All three channels have higher noise | No unique primary accusation, but 100/100 generic alarms and unresolved at EVERY decision |

Thus a targeted pass is not general robustness. Combined nonlinear/noise stress does not separately identify the two causes. Measurements must have known resolution, age and noise characteristics. Two common-mode witness faults break majority assumptions. The active V3 physical score flags 92/100 all-common offsets where pure pairwise agreement is blind; this motivates complementary evidence, but no hybrid solution is implemented or validated here.

Exact-flatline detects 100/100 ideal freezes but 0/100 after downstream readout jitter; it also flags healthy slow reporting 100/100. Perfect ideal-stuck scores are therefore insufficient. New readout stresses occur AFTER the controller sensor tap; no claim of a new noisy-feedback fault model is made.

## Control costs and restricted algebra

Passive and active triplex achieve the same targeted counts here. Added observations change the information budget. Across healthy, healthy_shift and healthy_late_shift, mean original-target tracking RMSE is 18.1727 rad/s passive vs 18.7148 active (+2.98%); model electrical input energy is 560.984 J vs 554.220 J (-1.21%). No energy-saving or free-intervention claim. Sensor cost/power is unmodeled.

For fixed R,K and constant biases away from transitions, residual offset d=bu-R*bi-K*bw has collinear columns [1,-R,-K], rank1. This electrical relation alone cannot uniquely attribute all three offsets. It is not a general impossibility claim about all dynamic models/control metadata.

Established prior work: NASA Joshi et al. (2014), https://ntrs.nasa.gov/citations/20140006008 ; NASA Software Engineering Handbook 8.09, https://swehb.nasa.gov/spaces/SWEHBVD/pages/102695725/8.09+-+Software+Safety+Analysis ; MathWorks stuck fault model, https://www.mathworks.com/help/fault-analyzer/ug/fault-properties.html . No novelty claim.

## Reproduce

```bash
cd research/motor_observability_v4
python -m pip install -r requirements.txt
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m unittest -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python run_all.py --out results/reproduced
python verify.py results/reproduced
```

Use a NEW output directory. Same-seed cloud replay is not additional independent scientific evidence. No paid LLM/GPU or actual machine is used. The conversation archive includes full local records/features, representative received traces, verification and logs. Future modifications require a new protocol and fresh seeds, not hidden tuning on this holdout.
