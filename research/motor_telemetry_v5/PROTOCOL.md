# V5: acquisition-time and declared-uncertainty audit

Pre-evaluation protocol, 2026-11-04 America/New_York. Simulation only. No novelty, hardware, safety-certification, publication, or universally robust diagnosis claim. Parent V4 commit `5e5e5d54fbc8b0495848a71e2284abfae1b031d3` remains unchanged. Work is on a separate draft branch.

## Question and evidence separation

Can acquisition-time matching and declared noise/resolution information remove V4's false PRIMARY-channel accusations under delayed, quantized, slow, or heteroscedastic observations while retaining detection of corresponding real primary faults? Raw sensor values and the three-speed measurement budget are shared across rules; quality/timestamp metadata is additional prior information, not a free equal-information improvement. No new sensor, active probe, or physical-score fusion is added in V5.

H1: matching acquisition times, not reception times, reduces temporal mismatch false attributions.
H2: subtracting known quantization/offset bounds and scaling by declared independent noise reduces heterogeneous-channel false attributions.
H3: low false-attribution rates are not success if diagnostic availability or true-fault detection collapses; measure both, with an always-abstain control.
H4: wrong metadata, missing exact time matches, dropout, coarse resolution and common-mode errors remain explicit falsification conditions. No metadata-only rule can repair an arbitrary shared bias using pair differences alone.

## Development and source commitment

Only seed 30001 for feature-scale inspection and seeds 30990-30991 in integrity tests were executed before this protocol. No parameter search or completed development benchmark is claimed. 25 integrity tests passed, including parent parity, no truth-channel detector input, causal prefixes, packet consistency, distinct sample counting and common-offset invariance. Calibration/test ranges below have not run yet.

SHA-256 source commitment:
- motorbench.py: caea2a328becfff82cf915511b157c76b7dd01ca43a2c884e1f2804c566a4834
- bank_study.py: e6aa4ccba89aa53c20f9586331344093301947c6c8e59edcde20ca3ab7bf6f1d
- study.py: 419240774aabbd96d84a60ad72d91567ab55c1ffa4dc33fed6128ff6b246b0ca
- box_solver.py: e0f4cf9863787a905e02a0c79f84d090f50d020f0d6cb116811416b84bf62b7d
- experiment.py: 15eddca6510854e8f791d14aab6b7b13e3566909c078314dff6e6c09947a9e3d
- telemetry.py: e26f86c34c18cc57436efc2980134cf8a59c869375068b52acc7181c9ca6b956

Reference environment Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0, Numba 0.65.1. Published experimental source must match these hashes; postprocessors and reports may be added separately. Any experimental changes require a disclosed amendment and new evaluation, not silent tuning.

## Fixed algorithm and interpretation

Original V4/V3 passive closed-loop plant, PI controller, faults and witness generation are reused. New telemetry transforms occur AFTER the controller tap. Detectors receive only three received speed values, acquisition timestamp indices, declared sigma, quantization step and offset bound. They do NOT receive true speed, fault/condition labels, onset or seed. Fault truth is separately used for scoring.

Each reception row holds the latest arrived packet. A packet preserves its value and acquisition stamp during holding; prior to first arrival it is invalid. Stamps must be causal and nondecreasing. Declarations are fixed per instrument/episode, NOT estimated by observing its fault label. Accurate declarations are an assumption; lying-declaration cases explicitly break it.

Decision times: t=2.0,2.2,...,17.8 s. Original raw RMS uses 41 received rows spanning .4 s; a window-only ablation uses 201 received rows spanning 2 s. Timestamp-aware rules retain only distinct common acquisition stamps within the trailing 2 s, without interpolation, extrapolation or future data. Require >=3 common samples and latest common acquisition age <=.6 s; otherwise output insufficient-data and no unique accusation. This deliberately limited exact-match policy is not a general asynchronous fusion algorithm.

Quality-adjusted pair score is RMS of max(abs(x_i-x_j)-(q_i+q_j)/2-b_i-b_j,0)/sqrt(sigma_i^2+sigma_j^2). q is a declared rounding step, b a fixed offset bound (primary 0, witnesses .03 rad/s). Quantization/offset are treated as bounds rather than independent random errors. Noise scaling assumes independent declared standard deviations; it is NOT a calibrated posterior probability or proof of set containment. Gaussian noise is unbounded.

For every rule, uniquely isolate channel j only when it disagrees with both others and those others agree, using one calibrated pair-score threshold. Any disagreement is separately a generic anomaly. Six rules: V4 raw with historical threshold .49060564088478326; same raw with matched new calibration; long-window raw; time-aligned raw; time+quality (primary candidate); always abstain. Baselines share received values; all new thresholds share calibration episodes. The historical fixed threshold is labelled separately.

## Calibration and held-out design

Calibration: 199 seed groups 33000-33198. RNG 774414 independently selects one of eight declared healthy families: healthy, healthy_shift, healthy_quantized, healthy_slow_reporting, healthy_witness_delay, healthy_primary_noise, healthy_high_noise, healthy_nonlinear. Each stream's threshold is rank ceil(200*.95)=190 of its 199 episode maxima over all decision times and three pairs. No fault calibration. This targets a mixture-level marginal error under exchangeability, NOT conditional guarantees for each family. Thresholds and calibration hash are frozen before holdout.

Holdout: 100 new seeds 35000-35099, paired across 38 conditions, passive mode only: 3,800 trajectories, 22,800 method records, 228 rate cells. Only 100 independent base seed groups, not 3,800 independent devices. Existing V4 conditions retained: healthy, healthy_shift, bias, bias_shift, drift, stuck, stuck_noisy_readout, healthy_late_shift, bias_late_shift, healthy_nonlinear, bias_nonlinear, healthy_voltage_bias, healthy_current_bias, aux1_bias, aux2_bias, two_aux_common_bias, all_common_bias, healthy_high_noise.

Additional paired telemetry families use original healthy/bias/stuck physical traces as named:
- healthy_quantized / bias_quantized: primary rounded to 2 rad/s, accurately declared.
- healthy_slow_reporting / bias_slow_reporting / stuck_slow_reporting: primary acquisition every .5 s, held between packets.
- healthy_witness_delay / bias_witness_delay: both witnesses delayed .1 s, correct acquisition stamps.
- healthy_primary_noise / bias_primary_noise: primary noise SD .75 instead of .25, accurately declared. Existing nonlinear primary SD .375 and all-high-noise SD .75 are also declared accurately.
- healthy_asynchronous / bias_asynchronous: periods .05,.07,.11 s with phases 0,.01,.03 s. Missing exact common stamps is expected to reduce availability, not counted as robustness.
- healthy_timestamp_lie / bias_timestamp_lie: same .1-s witness delay but acquisition stamps falsely equal reception times.
- healthy_noise_underreported / bias_noise_underreported: actual primary SD .75, declared .25.
- bias_quality_overreported: normal precision and a real bias but declared primary quantization step 20 rad/s.
- healthy_dropout / bias_dropout: both witnesses stop providing new packets after 3 s.
- healthy_coarse_quantization / bias_coarse_quantization: primary rounded to 16 rad/s, correctly declared; true bias may become unresolvable.

Primary bias remains signed 6 rad/s beginning at 10 s in new profiles; existing V4 fault definitions unchanged. No threshold retuning on these holdouts.

## Predeclared screen and complete outcomes

Candidate time+quality must satisfy all 29 point-rate engineering requirements: <=10% wrong primary attributions AND >=90% decision-time availability separately in the eight calibration-family healthy conditions (16 checks); >=90% valid primary isolation in bias, bias_shift, bias_late_shift, drift, stuck, stuck_noisy_readout, bias_quantized, bias_slow_reporting, stuck_slow_reporting, bias_witness_delay and bias_primary_noise (11 checks); >=90% correct first unique isolation for aux1_bias and aux2_bias (2 checks).

Always report generic false alarms, unresolved fractions, insufficient-data fraction/availability, early primary accusations, valid first primary isolations, first unique channel correctness, conditional delay and denominators. Pre-fault primary accusations cannot count as detections. Zero unique accusations with no availability is NOT success. Report every negative control even if the targeted screen passes. No broader certification follows from passing these point-rate screens.

Wilson 95% intervals for rates. Seed-paired bootstrap, 10,000 resamples RNG 44994, for candidate minus historical raw, matched raw, and time-only rules. Intervals are exploratory and not multiplicity-adjusted. Save all scores, availability, distinct matched counts, acquisition ages, per-episode records, metadata and one packet-level representative per condition. Independently reconstruct outputs and direct matched-packet scores. Reproduction with the same seeds is not additional independent evidence or third-party review.

## Prior work and boundaries

NIST Sensors 1588 explains acquisition-time timestamps and synchronization uncertainty: https://www.nist.gov/el/intelligent-systems-division-73500/sensors-1588 . NIST uncertainty propagation describes uncorrelated variance addition and covariance qualifications: https://physics.nist.gov/cuu/Uncertainty/combination.html . NASA Software Safety Analysis discusses normalization and redundancy-path independence: https://swehb.nasa.gov/spaces/SWEHBVD/pages/102695725/8.09+-+Software+Safety+Analysis . These are established principles, not original inventions. Real instrument specifications, clocks, non-Gaussian/correlated errors, shared failures, control feedback and costs remain to be independently validated. No live machinery, paid LLM/GPU or broker access is authorized or used by this study.
