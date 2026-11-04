# V3: electrical-consistency triage and active excitation — pre-evaluation protocol

Recorded 2026-11-04. Simulation-only, bounded research following V2's failure under during-operation parameter change. This is NOT Google's proprietary framework, a new-algorithm claim, hardware validation, a safety function or an accepted paper. Original V1/V2 source and results remain unchanged; work stays on a separate draft branch.

## Development history and hypotheses

Development used seeds 17000–17011; numerical/integrity tests used 17888–17893. Calibration 19000–19158 and evaluation 21000–21099 have NOT been run when this protocol/hash commitment is recorded.

Three exploratory routes were tried and must remain documented: (1) electrical least-squares explanations with bounded parameters, (2) resetting V2's cumulative model scores after two large current innovations, and (3) the electrical triage plus deterministic reference excitation. Resetting scores with a two-second output pause did not remove late-change false alarms on the development seeds. Flexible healthy explanations reduced false alarms but also concealed sensor bias. Excitation improved some development detections. These are development observations, not held-out evidence. A slow solver-based development run was interrupted by its execution timeout; partial console results are not a completed experiment. No unseen-seed claim applies to development.

H1: permitting an explicit resistance-change explanation before declaring a sensor fault reduces V2's false sensor-fault attribution under late plant changes.
H2: active excitation improves bias detection relative to the EXACT same triage without excitation, with measured control costs.
H3: fewer false alarms may result only from non-diagnosis; all missed faults and an always-abstain control must be reported.
H4: voltage/current-channel corruption can mimic speed bias, limiting causal attribution when the trusted-channel assumption fails.

## Frozen implementation commitment

Git base: 8d126d9bac4ece8fa7b65f7cb574e2a0629e7448.
SHA-256:
- motorbench.py: caea2a328becfff82cf915511b157c76b7dd01ca43a2c884e1f2804c566a4834
- bank_study.py: e6aa4ccba89aa53c20f9586331344093301947c6c8e59edcde20ca3ab7bf6f1d
- study.py: 419240774aabbd96d84a60ad72d91567ab55c1ffa4dc33fed6128ff6b246b0ca
- box_solver.py: e0f4cf9863787a905e02a0c79f84d090f50d020f0d6cb116811416b84bf62b7d

The implementation will be published with these exact hashes. Reference runtime Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0, Numba 0.65.1. Before evaluation, 19 integrity tests passed, including 400 bounded-fit comparisons with SciPy, prefix causality, no truth-channel input, source-plant parity, probe bounds and an exact ambiguity construction. Three development score trajectories agreed with a separate SciPy implementation to <2e-15 in RMS scores.

## Measurements and competing explanations

Detector input is ONLY [voltage reading, current reading, speed reading]. No true states, load torque, true parameters, condition labels, onset times or future readings are supplied. Unlike V2's parameter-selection mechanism, V3 explicitly uses the suspect speed inside competing electrical explanations; it does not claim current-only identification.

The standard electrical relation is u = R*i + L*di/dt + K*w. Nonoverlapping 0.1-second blocks use mean applied voltage, trapezoidal mean current/speed and endpoint current change. A trailing 2-second window is assessed every 0.2 seconds, from t=2.0 to 17.8 seconds. All methods, including V2's bank, use this common decision grid; V2's original 100-Hz alarm counts are NOT copied as the comparator.

Healthy constant model: bounded R=[1.6,3.6] ohm, L=[.016,.024] H, K=[.048,.052].
Healthy switch model: additionally allow one R change at each interior block index 1–18, with both R values in the same interval; omit the one block potentially straddling the change. Minimum RMS includes the constant model.
Bias model: same constant R/L/K plus an additive voltage-equivalent offset d in [-.8,.8] V. The bias explanation is considered compatible when its fitted RMS <=.04 V, a development-fixed tolerance.

Triage declares a CONDITIONAL speed-bias-compatible anomaly only when the healthy/switch score exceeds its calibrated threshold and the bias model remains compatible. Other outcomes retain healthy-not-rejected, parameter-change-compatible or unresolved labels. Compatibility is NOT a proof of health or unique cause. This is bounded least squares inspired by established set-consistency reasoning, not rigorous set-membership containment: Gaussian noise is unbounded, regressors are noisy, integration is approximate, and the .04-V tolerance has no formal coverage guarantee.

The wider electrical parameter bounds are explicit prior information and differ from V2's R/L grid. This is not an architecture-only or equal-prior comparison; the within-V3 active/passive comparison controls those bounds. Compute costs are not equal either.

## Active/passive intervention

Passive uses the exact original V1/V2 plant and reference schedules. Active adds a fixed +/-8 rad/s square-wave reference perturbation, alternating every .4 seconds from t=2 seconds, with no dependence on fault onset or condition. The original +/-12-V saturated PI remains unchanged. This changes the control task; improvement is not free passive-diagnostic superiority. No actual machinery is controlled.

Report signed electrical input energy integral(u*true_current dt) in joules, voltage-squared input integral (NOT joules), saturation fraction, and tracking RMSE against BOTH the original target and the perturbed command. Ground truth appears only in evaluation, not detection. Voltage-corruption negatives are excluded from actual-energy claims because their logged voltage is corrupted.

## Calibration, methods and untouched evaluation

159 seed groups, 19000–19158. RNG 774412 assigns each to healthy or healthy_shift with probability .5; assignments shared between active/passive. Total 318 calibration trajectories. Each method and input mode has its own threshold using the SAME episodes: rank ceil(160*.95)=152 of 159 episode maxima. No sensor-fault calibration data. Strictly greater than threshold triggers alarm.

Six rules, reported without selecting a winner after testing:
1. V2 cumulative model bank, recalibrated on common data/decision grid.
2. Electrical constant model, unconditional anomaly.
3. Electrical switch model, unconditional anomaly.
4. Bias-compatible gate without the switch alternative.
5. Full triage (primary candidate).
6. Always abstain (zero scores, zero detections/false alarms).

Evaluation: seeds 21000–21099, paired across both modes and all 14 conditions. 2,800 scenario trajectories, but only 100 independent base seed groups; modes and conditions are not independent experiments/devices.

Original six conditions: healthy, healthy_shift, bias, bias_shift, drift, stuck.
Original six V2 stresses: startup_bias, healthy_late_shift, bias_late_shift, healthy_outside_bank, healthy_nonlinear, bias_nonlinear. Preserve definitions and random schedules exactly, with optional probe as above.
Two additional negative controls: healthy speed sensor but voltage reading receives signed .3-V bias, or current reading signed .15-A bias, at the separately drawn uniform [10,13]-second time. Signs/noise are paired; real plant/controller are unchanged. A speed-fault declaration is a wrong attribution in these controls, even if it correctly flags some anomaly.

## Metrics and locked screening criteria

First-declaration healthy false alarms; valid fault detections only if first declaration is at/after actual fault onset; early alarms; misses; conditional delay; fractions of decision ticks in the diagnostic states. Silence, healthy-not-rejected and unresolved do NOT count as correct fault detections. Report all denominators.

Targeted engineering screen for ACTIVE triage: <=10% false alarms separately in healthy, healthy_shift and healthy_late_shift, AND >=60% valid detection separately in bias, bias_shift and bias_late_shift.
Extended screen additionally requires >=90% stuck and >=60% drift detection. Both screens are point-rate engineering screens, not statistical certification. Do not loosen either after observing results. All other stress and channel-corruption results must remain visible even if a screen passes.

Wilson 95% intervals per rate; seed-paired bootstrap 10,000 resamples (RNG 44992) for active-minus-passive triage differences, exploratory and not multiplicity-adjusted. No claim of statistical significance by cherry-picking conditions. Report actual control costs and all ablations.

## Verification and identifiability check

Save calibration assignments/maxima, per-episode metrics, all 80 decision-time score arrays, source/calibration hashes, protocol, tests, execution logs and environment. Recompute every rate from records and verify threshold ranks. Separate outputs, no overwrite.

A predeclared illustrative static counterexample: both worlds measure u=6 V, i=2 A, speed=40 rad/s. Healthy world R=2 ohm, true speed=40, load=.020 Nm. Biased world R=2.15 ohm, true speed=34, speed bias=+6, load=.032 Nm. Other nominal parameters unchanged. Both satisfy electrical/mechanical equilibrium, so identical observations cannot uniquely distinguish these two worlds without extra information. This is an elementary example under specified assumptions, not a new general impossibility theorem or a proof that probing solves all ambiguity.

## Prior art checked

Joshi, Gonzalez and Upchurch (2014), Identifiability of Additive Actuator and Sensor Faults by State Augmentation, NASA record https://ntrs.nasa.gov/citations/20140006008 . Identifiability restrictions are established.
Tsolakis, Ferranti and Reppa (2024), Set-Membership Estimation for Fault Diagnosis of Nonlinear Systems, https://arxiv.org/abs/2411.03011 . Set-consistency and informative-data requirements are established; we do not implement or claim its guarantees.
University of Michigan Control Tutorials, DC Motor Speed system modeling, https://ctms.engin.umich.edu/CTMS/index.php?example=MotorSpeed&section=SystemModeling . Standard physical relation, not new physics.
