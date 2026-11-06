# V10: ideal-information detectability audit — locked protocol

2026-11-06. Follow-on to PR #13 / V9, base 633606287a17dbd313b834d47ea29a1978f75fd6. Simulation and analytic bounds only. Original V1–V9 remain unchanged. No new algorithm, real machinery, paid model/GPU, safety/anytime guarantee or publication claim.

## Purpose and pre-evaluation source commitment

Investigate whether the prior target (0.5 rad/s diagnostic readout bias, first correct diagnosis within 5 seconds with >=80% probability, <=10% cumulative healthy generic false alarms over 600s) is excluded by information limits in any specified configuration. An oracle passing a simpler task DOES NOT prove that a practical unknown-onset/unknown-channel monitor meets the original target. No automatic promotion to deployment.

Source SHA256 oracle.py = 3fa549660c813f0e9ec0b3d6c5ffc6e1dacd640747c1099d5c48f0d22bfe8178.
Integrity suite SHA256 test_oracle.py = 400fe0a6fccd5607b92c55a1264d4e10aec8af0d454a95b7ae4dd9ae2fba66fb.
24 integrity tests passed before calibration/test execution. Development seeds 79900–79920 only. Direct covariance solves agree with the Kalman factorization; original V7/V8 simulated observations agree with the algebraic noise reduction. No V10 calibration or holdout has been run at this commitment. Numerical oracle powers have not been evaluated yet.

Parent generator: primary white noise SD .25, auxiliary independent white noise SD .25 each, and for correlated profiles an extra stationary AR(1) primary component of variance .75^2-.25^2=.5 at .01-second ticks. Original rho .9; stress rho .99. Primary common sampling interval .01s (dense) or .5s (sparse). Auxiliary data between primary acquisitions cannot improve the most-generous oracle once the entire true speed waveform is revealed. Faults affect downstream diagnostic READOUTS only, never controller feedback.

## Three information tiers and exact power calculations

1. Contrast post-only: primary minus average of two auxiliary readings, true constant offsets removed. White contrast variance .09375; colored component .5; no pre-onset state information. This is an optimal fixed-look reference for that particular observation window, NOT an upper bound for algorithms using additional history.
2. Contrast latent genie: same contrast but exact AR latent state at the last PRE-FAULT PRIMARY ACQUISITION is supplied. This is strictly extra information relative to past observations. It is not future-innovation knowledge.
3. Truth-speed latent genie: entire real speed waveform and fixed offsets, true faulty primary channel, exact onset, bias direction and noise law are all supplied, plus that last pre-fault latent state. Only primary white variance .0625 remains beside the AR component. Auxiliary measurements are independent noise conditional on these revelations and contain no further fault signal. This deliberately overpowered binary detector upper-bounds the original observation-level task under the stated Gaussian model, truthful original sampling and independent continuously distributed onset. It is NOT a practical detector or a bound for other hardware/sampling/noise models.

At common sampling spacing m ticks, a=rho^m and Q=.5(1-a^2). For n post-fault readings, stationary covariance is C_ij=q*a^|i-j|+r*1(i=j). Revealing the previous latent state subtracts q*a^(i+1)*a^(j+1). For known signed mean shift delta*1 and common covariance, I=1' C^-1 1. Exact Neyman–Pearson power is Phi(delta*sqrt(I)-Phi^-1(1-alpha)). Compute by scalar Kalman innovation factorization and independently verify direct Cholesky solutions. This is established simple-hypothesis Gaussian testing, not a new theorem.

For each of six profiles (dense/sparse x iid/rho=.9/rho=.99), evaluate deadlines .5,1,2,5,10,30s, amplitudes .125,.25,.5,1,2,6rad/s, alpha=.05 and .10, and all three tiers. Record the minimum amplitude for 80% ideal power. For continuous random onset independent of the grid, exactly 10 primary acquisitions occur in the next5s at2Hz, almost surely; grid-aligned endpoint exceptions have probability zero. Original .2s decision ticks can only reduce usable data by the deadline.

The upper-bound implication is conditional: any rule with TRUE cumulative600s healthy false-alarm probability <=alpha induces a level<=alpha binary event for successful detection by the deadline. Giving it the genie information can only help; therefore its original timely-correct probability cannot exceed the most-powerful genie test. An empirical 0/200 false-alarm count does NOT establish the assumed population bound. High oracle power is only an absence of this obstruction, not achievability for unknown onset/sign/channel or model drift.

## Independent Monte Carlo validation

For all6profiles and both latent-genie tiers, generate20000 explicit colored Gaussian observation windows of5s each (240000 windows total). RNG root2026110601 with separate profile/tier substreams, batch500. Previous latent state known and centered tozero; generate actual state innovations and measurement noise, then calculate the exact innovation likelihood statistic. Save all null normalized statistics and two full representative observation windows per tier/profile. Evaluate alpha .05/.10 and paired delta=.5 shifts. Check against analytic Gaussian power; no fitting or threshold selection. These are stochastic observation windows, not real devices or240000 full motor trajectories.

## Unknown-onset reference, not an upper bound

To expose the cost of searching over time, separately run a fixed5s sliding matched Gaussian contrast statistic (GLS) and a simpler5s signed mean normalized with the exact covariance. Correct true noise model, fixed offsets and known primary target are provided. Bias sign and onset are NOT supplied to the scoring function; absolute scores scan every available common acquisition over600s. This is more favorable timing than the old .2s decision grid. No unique-channel attribution is attempted or credited. The single5s window is fixed before evaluation; no multiscale search or method selection.

Contrast simulation algebraically cancels shared physical speed. Source parity checks verify equality with V7/V8 readings after oracle removal of fixed auxiliary offsets. The reduction does NOT add a new motor simulation or a physical fault feedback claim.

Calibrate both rules using the SAME199 healthy600s paths per profile: starts81000,81300,81600,81900,82200,82500 (each start..start+198);1194paths total. Threshold per rule/profile is rank190 of199 whole-path absolute maxima (all times). Freeze calibration source/hash/numbers before holdout.

Holdout85000–85199,200 base seeds paired across all6profiles and healthy/.5/1/6rad/s cases:4800scenario paths, not4800independent devices. Sign/onset use independent seed+13000000, onset uniform[300,330]. No reset, no removal of early alarms, and no conditioning only on survivors. For rho=.99 paths also evaluate frozen rho=.9 model/thresholds as a misspecification negative control on the SAME data; these are additional evaluations, not new trajectories. Save all packed alarm sequences, records and representative raw contrast/score paths.

Metrics: whole-path healthy any alarm; pre-fault alarm; first alarm valid (after onset); within5/30s; conditional delay with failures separately. These are known-target binary alarms, NOT first correct unique diagnoses among three channels. Report Wilson95 descriptive intervals and all cases, including failures. Do not compare these numeric rates to V9 as equal-information superiority.

No new deployment screen or acceptance thresholds are invented after seeing results. The question is feasibility diagnosis. Prove exclusions only where the most-generous exact bound is below the target and list every assumption. Otherwise report unresolved algorithmic/design room.

## Reproducibility

Pinned numerical dependencies; new output directories; source locks; tests before evaluation; separate verifier for covariance/power/MonteCarlo/packed first-alarm records and representative direct convolutions. CI same-seed replay is software reproducibility, not added independent evidence or human peer review. No paid API, GPU or actual device.

Primary references: UC Berkeley Stat210A Neyman–Pearson lesson https://stat210a.berkeley.edu/fall-2024/reader/hypothesis-testing.html ; Penn State STAT41526.1 https://online.stat.psu.edu/stat415/lesson/26/26.1 ; Sun & Zou autoregressive change detection https://arxiv.org/abs/2310.08789 . These justify established testing principles, not certify our implementation. Original task and runtime scopes are in V9's protocol/report.