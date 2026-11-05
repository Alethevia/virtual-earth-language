# V7: small readout faults and monitoring-horizon audit

**Scientific screen FAILED: 16/20 checks pass; all four small-fault sensitivity checks fail.** Software reproduction is not research acceptance. No new algorithm, hardware validation, lifetime guarantee or publication claim. V1–V6 sources/results are unchanged.

## Source and scope

Protocol/source hash before calibration: `99689fb386e21867d11f62cebad323d915f9d709`. Calibration lock before holdout: `67f8c67496b45c71aa133a0fa8b32c2f2ef44b92`. Published horizon.py matches its pre-evaluation SHA256; Git blob `80a3bcce52f2d89b1a75a816b3403419faf4d336`.

Important change from old feedback-fault studies: this is a downstream DIAGNOSTIC READOUT experiment. A new healthy nominal PI motor runs continuously for 600 seconds; telemetry biases never enter its controller. Exact acquisition-time alignment cancels the common speed waveform from pairwise differences. Consequently these are observation-level monitoring results, NOT closed-loop faulty-machine performance or simulation-to-real validation.

796 independent calibration paths (199 per profile), 10,400 test scenario trajectories, five rules, 60,000 episode-method-horizon records and 300 aggregate cells. Only 200 independent base test seed groups: profiles, amplitudes, early/late faults and healthy prefixes are paired. No alarm/state resets along the long trajectory.

25 integrity tests passed. Separate postprocessor checked all records/cells, 10 threshold values, 2,400 Wilson intervals, 720 paired intervals, and 12 COMPLETE raw-packet/score examples. Maximum independently calculated score discrepancy 1.2434497875801753e-14. Same-author cross-checking, not third-party certification. Check CI status separately.

## Fixed rules and equal-information comparison

Keep V5's exact timestamp/quality score and V6 isolation logic. Compare historical V6 count thresholds, historical V6 conservative universal threshold 2.0307216953, a NEW 18-second-calibrated universal threshold 2.0797311758, a NEW 600-second-calibrated universal threshold 2.4746751836, and always-abstain.

The two new rules use the SAME 796 paths, rank190/199 per profile and maximum profile threshold. Only calibration horizon changes between them. Relative to historical V6, the new calibration also includes correlated noise and more/longer calibration paths, so that comparison is not an isolated architecture gain.

Profiles: dense100Hz or sparse2Hz primary reporting; independent base noise or primary AR(1) rho=.9 with correctly declared marginal SD .75. Auxiliaries stay100Hz. Truthful timestamps/quality, three channels, one readout fault. No remedy for common-mode faults, dishonest metadata, dropout or unmatched asynchronous acquisitions is claimed.

## Healthy cumulative alarms: short-run reliability is not long-run reliability

Sparse independent-noise profile, each cell /200; SAME uninterrupted paths, no reset.

| Monitoring horizon | V6 conservative | New18s universal | New600s universal |
|---|---:|---:|---:|
| 18 seconds | 19 | 9 | 1 |
| 180 seconds | 98 | 72 | 5 |
| 600 seconds | 179 | 162 | 11 |

At600s the corresponding wrong-ANY-channel counts are20,12,0. New600s generic rate5.5% has Wilson95 interval3.10%–9.58%. Versus same-path new18s calibration, reduction is75.5 percentage points (paired exploratory interval69.5–81.5 points). All paired intervals are unadjusted.

Sparse correlated-noise600s alarms: historical conservative182/200, new18s163/200, new600s8/200. Dense correlated-noise count-stratified historical rule alarms and wrongly accuses a channel in200/200 over600s;197/200 already uniquely alarm before the late fault. The universal rules have0/200 healthy alarms in that dense profile. Zero observed errors is NOT zero population risk.

## Small faults reverse the simple-baseline ranking

Late faults begin uniformly between300 and330s; 200 cases per profile/amplitude. No survivor-only filtering. FIRST unique diagnosis must be correct with no earlier unique accusation.

| Dense independent noise; within5s | V6 count | V6 conservative | New600s |
|---|---:|---:|---:|
| .25 rad/s bias | 4 | 0 | 0 |
| .5 rad/s bias | 200 | 0 | 0 |
| 1 rad/s bias | 200 | 200 | 200 |
| 2 rad/s bias | 200 | 200 | 200 |
| 6 rad/s bias | 200 | 200 | 200 |

Thus the previous conservative-baseline advantage does NOT establish dominance for small faults. The count method wins on dense independent small-bias tests but fails badly under changed temporal dependence. The experiment identifies a trade-off, not a universally best method.

Dense .25-rad/s count rule eventually first-correct133/200 but only4/200 within5s; conditional median delay69.0s. Sparse independent .5-rad/s new600s rule eventually first-correct169/200 but only8/200 within5s and39/200 within30s; conditional median delay69.5s. Eventual detection counts can hide unacceptable delays. A correct-channel alarm after onset can partly reflect chance noise excursions; comparison to healthy controls and deadlines is essential, not unique causal proof.

The new600s candidate detects all6-rad/s late faults correctly within5s in every profile (200/200 each), and meets all healthy/availability checks. But .5-rad/s within5s is0,8,0,0 out of200 across dense_iid,sparse_iid,dense_ar,sparse_ar, far below the fixed80% criterion. **16/20, FAIL.** We did not remove the small-fault requirement.

## Limits and interpretation

600 seconds is a finite audit horizon, not lifetime/anytime validity. Whole-path calibration can accommodate within-path dependence under exchangeability of whole healthy paths in the specified profile/horizon; changed conditions and repeated lifetime use are different problems. A lower dense threshold is more sensitive, not automatically robust. Four/five sparse timestamps are not independent repeated held readings.

This round changes the background generator and moves faults downstream of feedback. Do not compare its numerical percentages to prior closed-loop-fault tables as a pure algorithm improvement. Known single-target assumptions, correct metadata and common-mode blindness remain. No new monitoring algorithm is claimed; next hypotheses require fresh seeds, not tuning this holdout.

An initial development-only unit assertion incorrectly assumed exactly five sparse observations; corrected to four OR five before calibration, without changing experimental source. A local HTTP copy of the protocol failed because the container had no DNS; this did not affect connector-based public commitments or experiments.

## Reproduce

```bash
cd research/motor_horizon_v7
python -m pip install -r requirements.txt
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m unittest -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python replay.py --out results/reproduced --workers 2
python verify.py results/reproduced
```

New output directory only. Replay checks all300 integer outcome cells by canonical digest and explicitly insists the scientific screen remains false. Same-seed cloud replay is not additional independent evidence. No paid model/GPU, live machinery or trade is used; CI consumes workflow resources.

Primary references: Angelopoulos & Bates, arXiv:2107.07511; Howard et al., arXiv:1810.08240 / Annals of Statistics2021. The latter develops time-uniform inference; we DO NOT implement it or inherit its guarantees.
