---
title: "Limits of Load-Augmented Speed-Sensor Diagnosis Under Motor-Parameter Shift"
subtitle: "A reproducible simulation pilot"
author: "Independent research working draft - author review required"
date: "29 October 2026 | Version 0.1 | Not submitted or peer reviewed"
geometry: margin=0.85in
fontsize: 10pt
colorlinks: true
---

# Abstract

We evaluate speed-sensor fault alarms in a simulated PI-controlled DC motor with changing references, load torque and voltage saturation. Three causal residuals are compared: tracking error, a current-only two-state Kalman observer, and a current-only observer augmented with load torque. Thresholds are calibrated on maxima from 39 healthy episodes; 60 paired seeds are then evaluated under six conditions. The load-augmented observer produces 2/60 healthy false alarms and detects 17/60 additive-bias and 56/60 stuck-sensor episodes without earlier alarms. It does not outperform the no-load observer. Both observers falsely alarm in all 60 healthy parameter-shift episodes. An electrical-equation argument explains how parameter mismatch can resemble speed-sensor bias. This is a reproducible negative-result pilot, not a new estimator, a hardware validation or a publication claim.

# 1. Research question and prior work

The question is whether modeling unknown load torque is sufficient to make a current-based speed-sensor diagnostic robust to ordinary load changes and motor-parameter shift. The engineering deliverable is a transparent executable benchmark, not a claim that observer-based diagnostics are new.

Alkaya and Eker [1] previously demonstrated a Luenberger-observer sensor-diagnosis scheme on a permanent-magnet DC motor. A 2026 experimental study [2] also investigated DC-motor speed-sensor monitoring with a discrete Kalman observer and reported sensitivity to unmodeled load. These studies establish substantial prior art. Our implementation is not a reproduction of their hardware, software, thresholds or quantitative results. A broader literature review is still needed before asserting a publishable contribution.

We use standard electromechanical motor equations, consistent with the CTMS educational model [3], but choose our own illustrative parameters. Whole-episode calibration uses the standard finite-sample order-statistic idea underlying split conformal methods [4]. None of these building blocks is claimed as novel.

# 2. Plant, controller and diagnostic methods

## 2.1 Electromechanical model

With current $i$, angular speed $\omega$, applied voltage $u$ and opposing load torque $\tau$, the plant is

$$L\dot i=u-Ri-K\omega, \qquad J\dot\omega=Ki-b\omega-\tau.$$

The nominal values are $J=0.002$ kg m$^2$, $b=0.002$ N m s/rad, $K=0.05$ in the corresponding SI units, $R=2$ ohm and $L=0.02$ H. Equal numerical torque and back-EMF constants are assumed. These values describe no identified physical device.

The plant is discretized by an exact matrix exponential for piecewise-constant inputs. The sample interval is 0.01 s and each episode lasts 18 s. Observations are $y_\omega=\omega+f+\epsilon_\omega$ and $y_i=i+\epsilon_i$, with Gaussian noise standard deviations 0.25 rad/s and 0.015 A. The speed-sensor fault enters the feedback controller as well as the diagnostic residual. The current sensor is assumed healthy.

A PI controller has gains $K_p=0.20$ and $K_i=0.60$. Applied voltage is clipped to $[-12,12]$ V. The integral updates only when the command is unsaturated or the error drives it back toward the admissible range. This is a simulation controller; there is no safety certification, current limiter or fault-triggered reconfiguration.

## 2.2 Residuals and causal timing

The tracking baseline uses $r_{tr}=y_\omega-\omega_{ref}$. The two observer methods use $r=y_\omega-\hat\omega$, but assimilate only current and the previously applied voltage. The suspect speed sensor is never an observer measurement. True simulated speed, current and torque are retained for evaluation but are not used by the diagnostic algorithms.

The no-load observer has state $(i,\omega)$. The augmented observer has state $(i,\omega,\tau)$ with nominal $\dot\tau=0$ and a random-walk design covariance. Both use steady-state Kalman gains computed from the nominal discretized model. Per-sample design covariance is $Q=\operatorname{diag}(10^{-4},0.05)$, with an additional $10^{-6}$ torque entry in the augmented version. Current-measurement variance is $0.015^2$. These are fixed engineering design choices, not fitted physical noise estimates.

For the continuous augmented model and $C=[1,0,0]$, the observability matrix obeys

$$\det\begin{bmatrix}C\\CA\\CA^2\end{bmatrix}=-\frac{K^2}{L^2J}\ne0.$$

Thus the ideal known-parameter, constant-load model is observable from current. This calculation does not establish robustness to uncertain parameters, current-sensor faults, finite excitation or unmodeled dynamics.

# 3. Whole-episode threshold calibration

Every residual uses the same causal score,

$$s_k=a s_{k-1}+(1-a)|r_k|, \qquad a=\exp(-0.01/0.10), \quad s_{-1}=0.$$

For each healthy calibration episode, take the maximum score after the 2 s warm-up. With $n=39$ maxima and target $\alpha=0.05$, the threshold is the $k=\lceil(n+1)(1-\alpha)\rceil=38$th ordered maximum. An alarm requires a strict threshold exceedance. Each method gets its own threshold by this identical rule.

Conditional on a scoring rule fixed independently of calibration and evaluation, exchangeability of the 39 healthy calibration episodes and one future healthy episode implies

$$P(M_{new}>M_{(38)})\le\frac{40-38}{40}=0.05.$$

The argument is the rank symmetry of 40 exchangeable maxima; ties make strict exceedance conservative. Dependence within an episode is allowed because calibration units are whole episodes. This is a marginal, fixed-horizon result over the calibration sample and a new episode, not a guarantee conditional on a particular fitted threshold. It is not a lifetime alarm-rate guarantee. It also does not apply under parameter shift or to an OR-combination of all three alarms.

# 4. Fixed protocol and metrics

The protocol was recorded in Git commit `05cdb01f2b5284207229736cec39cc6a90cd6432` before the reported benchmark. Calibration seeds are 1000-1038; evaluation seeds are 2000-2059. The six conditions reuse the same 60 seeds, pairing noise and input schedules. There are 399 simulated trajectories, not 399 independent devices.

Ordinary variability is uniform: $J,b$ vary by +/-10%, $R,L$ by +/-5%, and the common torque/back-EMF constant by +/-3%. Reference steps at 0, 5, 10 and 14 s are uniform from 25 to 110 rad/s. Load steps at 3, 9 and 14 s are uniform from 0.005 to 0.035 N m. Some references are unreachable under the voltage limit.

Faults start at 10 s. Bias is a randomly signed 6 rad/s offset. Drift ramps to the same-signed 10 rad/s endpoint at 18 s. Stuck faults hold the last pre-fault noisy speed value. Parameter shift additionally multiplies resistance by 1.35 and friction by 1.30. The shift is present from episode start and lies outside the calibration distribution. Resistance and friction are changed together in this pilot, so their individual effects are not empirically isolated.

A valid detection requires the first alarm to occur at or after fault onset. Any pre-fault alarm invalidates that episode's detection, even if another exceedance would occur later. Healthy false alarms are measured per entire post-warm-up episode. Delays are reported only among valid detections. Wilson 95% intervals describe episode proportions conditional on the fixed calibration; paired conditions and repeated time samples are not treated as additional independent trials.

# 5. Results

Thresholds for tracking, no-load and load-augmented scores are respectively 54.73395, 9.46677 and 10.07690 rad/s. High tracking thresholds reflect legitimate reference transitions and saturation, not necessarily sensor defects.

| Condition and metric | Tracking | No-load | Load-augmented |
|:---|---:|---:|---:|
| Healthy false alarms | 2/60 | 1/60 | 2/60 |
| Shifted healthy false alarms | 5/60 | 60/60 | 60/60 |
| Bias valid detections | 1/60 | 17/60 | 17/60 |
| Drift valid detections | 1/60 | 29/60 | 28/60 |
| Stuck valid detections | 7/60 | 57/60 | 56/60 |
| Bias plus shift valid detections | 2/60 | 0/60 | 0/60 |

The load-augmented healthy false-alarm fraction is 3.33%, with interval 0.92%-11.36%. Its bias detection fraction is 28.33% (18.51%-40.77%), and stuck detection is 93.33% (84.07%-97.38%). The shifted healthy false-alarm fraction is 100% (93.98%-100%). These wide intervals and the small calibration sample preclude precise performance claims.

The augmented observer's median conditional delays are 0.17 s for bias, 5.095 s for drift and 0.32 s for stuck faults. Their denominators are only 17, 28 and 56 detected episodes. A small delay among successes must not obscure the missed faults. Both observers alarm before fault onset in all 60 shifted bias episodes; their zero valid-detection count is therefore diagnostic failure, not lack of alarm activity.

No advantage from load augmentation is supported in this experiment. The bias counts are identical and drift/stuck counts are slightly worse than the no-load observer. We have not established statistically significant inferiority, nor tested whether a different, independently selected design would work better. A post-onset alarm is an operational detection metric, not proof that the sensor fault alone caused the alarm.

# 6. Why load estimation does not remove parameter confounding

At steady state, the true electrical equation gives $u=R_\star i+K_\star\omega$, where stars denote true electrical parameters. An ideal nominal electrical reconstruction would use $\hat\omega=(u-R_0i)/K_0$. Its sensor-consistency residual is then

$$r=f-\frac{R_\star-R_0}{K_0}i-\frac{K_\star-K_0}{K_0}\omega.$$

Consequently, a nonzero residual can arise from sensor bias, resistance mismatch, back-EMF mismatch, or their combination. This expression is a steady-state explanatory relation, not an exact formula for our noisy finite-gain observer.

More generally, for known nominal $L_0,R_0,K_0$, the electrical consistency residual satisfies the noise-free identity

$$u-R_0i-L_0\dot i-K_0y_\omega
=\Delta R\,i+\Delta L\,\dot i+\Delta K\,\omega-K_0 f.$$

At one steady operating point with constant current and unknown load, changes in resistance and an offset fault can compensate: $\Delta f=i\Delta R/K_0$. Estimating load torque alone adds no independent electrical information to separate them. This limited non-identifiability argument does not cover all excitation-rich dynamic trajectories; varying current and independently justified calibration can help. The simultaneous resistance/friction stress test is consistent with confounding but does not isolate its sole cause.

# 7. Reproducibility, limitations and next experiment

The implementation uses Python 3.13.5, NumPy 2.3.5 and SciPy 1.17.0 in the reference environment. The archive contains all episode metrics, calibration maxima, six illustrative traces, summaries and SHA-256 manifests. Source code regenerates the raw outputs. Twenty-six local tests pass, including exact-discretization identities, physical signs, observer stability/observability, exclusion of true-state leakage, prefix causality and threshold ranks. A C PI implementation is actually compiled and agrees with Python on 3,000 randomized updates to 12 decimal places. This validates only the tested code paths, not a complete embedded diagnostic system.

Limits include one simple linear motor family, assumed healthy current sensing, ideal known applied voltage, Gaussian measurement noise, no ADC/PWM/communication effects, no thermal or friction nonlinearities, fixed gains and one calibration split. There is no measured motor dataset, hardware-in-the-loop experiment, independent replication or formal comparison against the full range of existing diagnostic algorithms. The present work is insufficient for a novelty or deployment claim.

A next experiment, not yet run, should separately vary resistance and friction; independently identify parameters on known-healthy data; freeze the resulting observer; and compare four designs: no identification/no load state, load state only, identification only, and both. New evaluation seeds and broader model families are required. It must test whether apparent adaptation simply absorbs a sensor fault. Hardware validation, if pursued, needs a separate reviewed low-voltage protocol with current limiting and mechanical protection; company equipment is outside this project's scope.

# 8. Integrity and authorship

This code, analysis and manuscript were developed with AI assistance. Human review, personal reproduction, understanding, literature verification and substantive research contributions are still required before submission or use as evidence of individual research competence. No university affiliation, employer deployment, publication acceptance, original invention or admissions benefit is asserted. This working draft is not submitted or peer reviewed.

# References

[1] A. Alkaya and I. Eker. "Luenberger observer-based sensor fault detection: online application to DC motor." Turkish Journal of Electrical Engineering and Computer Sciences 22(2), 363-370, 2014. DOI: [10.3906/elk-1203-84](https://doi.org/10.3906/elk-1203-84).

[2] R. Uscamaita-Quispetupa, E. J. Sacoto-Cabrera, R. J. Coaquira-Castillo, L. W. Utrilla Mego, J. C. Herrera-Levano, Y. Concha-Ramos and E. Moreno-Cardenas. "Low-Complexity Monitoring of DC Motor Speed Sensor Additive Faults Using a Discrete Kalman Filter Observer." Energies 19(6), 1485, 2026. DOI: [10.3390/en19061485](https://doi.org/10.3390/en19061485). The publisher's title, DOI and indexed abstract/full-text extracts were checked; this is not a code-level replication.

[3] Control Tutorials for MATLAB and Simulink. "DC Motor Speed: System Modeling" and "State-Space Methods for Controller Design." [CTMS, University of Michigan](https://ctms.engin.umich.edu/CTMS/?example=MotorSpeed&section=ControlStateSpace). Accessed 29 October 2026. Our numerical plant parameters differ from the tutorial example.

[4] A. N. Angelopoulos and S. Bates. "A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification." arXiv:2107.07511, 2021, version 6 revised 2022. DOI: [10.48550/arXiv.2107.07511](https://doi.org/10.48550/arXiv.2107.07511).
