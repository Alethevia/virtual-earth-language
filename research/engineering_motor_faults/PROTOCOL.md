# Motor sensor-fault benchmark: protocol v1

Status: initial protocol recorded before running the reported benchmark. This is a simulation study, not a hardware experiment, not a new-algorithm claim, and not a submitted or accepted paper. AI-assisted implementation and writing require human review and understanding.

## Question and hypothesis

For a PI-controlled DC motor, does a current-only observer augmented with an unknown load-torque state detect speed-sensor faults better than a no-load observer and a tracking-error alarm, at thresholds calibrated on healthy whole episodes? We also test whether resistance/friction mismatch defeats the calibration. No favorable outcome is required; null and adverse results will be retained.

## Fixed engineering design

- Nominal physical parameters: J=0.002 kg m^2, b=0.002 N m s/rad, Kt=Ke=0.05 in SI units, R=2 ohm, L=0.02 H. These are illustrative assumptions, not measured device specifications.
- Sampling interval 0.01 s; duration 18 s; no evaluation before 2 s; sensor fault starts at 10 s.
- Voltage-limited PI control: Kp=0.20, Ki=0.60, voltage limit +/-12 V, conditional-integration anti-windup. No fault-driven controller reconfiguration.
- Healthy episode variability: J and b +/-10%, R and L +/-5%, common Kt/Ke factor +/-3%, all uniform and independent. Initial state is zero.
- Reference steps at 0, 5, 10, 14 s, drawn uniformly from 25 to 110 rad/s. Load torque steps at 3, 9, 14 s, independently uniform from 0.005 to 0.035 N m. Saturation is allowed.
- Gaussian measurement noise: speed SD 0.25 rad/s; current SD 0.015 A. No process noise is injected into the plant. Known applied voltage is an idealization.
- Methods: absolute tracking residual; current-only two-state fixed-gain Kalman observer without load; current-only three-state fixed-gain Kalman observer with a random-walk load-torque state. The observers never assimilate the suspect speed measurement.
- Observer design covariances per sample: Q=diag(0.0001,0.05[,0.000001]); current measurement R=0.015^2. Nominal plant parameters are used for observer design.
- Score: exponentially smoothed absolute residual, time constant 0.10 s, initialized at zero. All methods use identical scoring and calibration rules.

## Calibration and held-out evaluation

- Calibration: 39 healthy episodes, seeds 1000 through 1038.
- Per-method threshold: rank ceil((39+1)*0.95)=38 of the 39 episode-maximum scores after warm-up; alarm iff score strictly exceeds this threshold. Calibration is at episode level, not at time-sample level.
- Test: 60 seeds, 2000 through 2059, reused across conditions for paired simulation noise and input schedules.
- Conditions: healthy; healthy_shift; bias; drift; stuck; bias_shift.
- Bias: randomly signed 6 rad/s additive speed-sensor offset. Drift: same sign, linear from zero at 10 s to 10 rad/s at 18 s. Stuck: hold the last pre-fault noisy speed measurement.
- Shift: multiply true armature resistance by 1.35 and friction by 1.30 in addition to the ordinary episode variability. This is an out-of-distribution stress test; the 5% calibration target is not a guarantee there.
- Total reported trajectories: 39 calibration plus 360 evaluation episodes. These are not 399 physical experiments or independent devices. Paired conditions share seeds.

## Metrics and interpretation

Report healthy episode false-alarm fraction, pre-fault false-alarm fraction, and valid detection fraction (first alarm occurs at or after fault onset). A pre-fault alarm cannot count as a successful detection. Report median delay only among valid detections, with the detection denominator always visible. Give Wilson 95% intervals for episode-level binomial proportions; do not treat correlated time samples as independent observations. Each method is assessed separately; no 5% joint guarantee is claimed for OR-combining methods.

The order-statistic argument requires exchangeable healthy calibration and future episodes with identical horizon, score rule and operating distribution. It is a marginal finite-horizon statement, not a lifetime false-alarm guarantee or a guarantee conditional on a particular calibration set.

## Reproducibility and scope

Save all episode metrics, calibration maxima, thresholds, software versions, seed ranges and SHA-256 hashes. Include physical-model and controller unit tests, observer observability/stability tests, causality tests, and Python/C controller parity tests. Keep this project isolated from unrelated repository modules. Any protocol change must be documented before rerunning reported tests; exploratory tuning is not confirmatory evaluation.

No company data, proprietary machinery details, user personal data, or fabricated author affiliations may be used. Code is simulation-only, not a PLC safety function or deployment-ready motor controller. Future hardware work requires a separately reviewed low-voltage experimental protocol and measured motor parameters.
