# V10: oracle detectability separates information limits from algorithm failures

**Feasibility audit, not a new diagnostic algorithm or a deployment pass.** V1–V9 unchanged. Analytic result is conditional on the explicitly specified Gaussian readout model. Read THEORY.md before using the upper bound.

## Commitments and actual execution

Protocol/source locked before numeric evaluation:6fc23e904b4fa79019c48ca098fc4a6ca4edf0ff. Continuous-reference calibration locked before holdout:4ae60cc7e551303f843d0387a8cd739c77b25eb9. Source SHA2563fa549660c813f0e9ec0b3d6c5ffc6e1dacd640747c1099d5c48f0d22bfe8178.

24integrity tests;1296analytic power cells;240000explicit five-second Gaussian observation windows for Monte Carlo validation;1194independent healthy600sreference-calibration paths;4800test scenarios with200base seeds paired across profiles/amplitudes;12800method records and64scan cells. Monte Carlo windows are NOT240000motor simulations or real devices. Same-author independent verification checks AR-precision/Woodbury calculations, Cholesky likelihood scores,all packed alarm records and16complete direct-convolution examples. Maximum power discrepancy1.02e-12; convolution-score discrepancy4.27e-14. Actual cloud status must be checked separately.

## Ideal result: a narrow but genuine population limit

Give an ideal detector the true speed, offsets, exact noise model, fault channel,onset,sign,and latent AR state at the last pre-fault acquisition (NOT future noise). Neyman–Pearson testing then gives the greatest possible power in this easier problem. It therefore upper-bounds the original causal diagnostic task when its TRUE whole600shealthy false-alarm probability is <=alpha.

For0.5rad/sbias and5sdeadline:

| Profile | Ideal power at alpha=.10 | Ideal power at alpha=.05 |
|---|---:|---:|
| dense iid | approximately100% | approximately100% |
| sparse iid |99.999977%|99.999860%|
| dense rho=.9 |99.512639%|98.683700%|
| sparse rho=.9 |**79.331037%**|**67.532278%**|
| dense rho=.99 |96.616258%|92.838440%|
| sparse rho=.99 |**51.958170%**|**37.668522%**|

At2Hz there are only10post-fault primary acquisitions in5s almost surely under continuous onset. Under the original sparse correlated model, the population80%timely-detection target is excluded even in this very favorable experiment atalpha=.10. The gap is narrow and model-specific, not a universal impossibility claim. More samples, smaller noise,more time or a larger fault change the bound. A finite sample can by chance exceed80%; a passing sample screen is not a population theorem.

Conversely, high bounds in dense/independent regimes DO NOT prove an unknown-onset deployable detector can attain them. They merely do not exclude the target. This prevents blaming all prior failures on information shortage.

## Unknown-onset reference: not the same task or an upper bound

A fixed5smean and exact-covariance matched filter continuously scan600s. Both receive the correct primary target, true fixed offsets and correct noise covariance. Onset/sign are unknown. They scan all common acquisitions,more frequently than the original .2sdecision grid. This is additional prior information; no claim of equal-information superiority over V9, unique fault localization,or hardware readiness.

Each profile uses the SAME199healthy calibration paths for both rules; separate thresholds are rank190whole-path absolute maxima. Holdout85000–85199; all earlier alarms remain failures,no survivor filtering.

| Profile | Healthy any alarms,GLS /200 |0.5bias first alarm within5s,GLS /200 |Simple mean within5s /200|
|---|---:|---:|---:|
| dense iid |11|193|193|
| sparse iid |7|174|174|
| dense rho=.9 |8|75|80|
| sparse rho=.9 |9|7|7|
| dense rho=.99,correct model |18|1|see full outputs|
| sparse rho=.99,correct model |11|0|see full outputs|

These are known-target binary detections, NOT first correct unique channel diagnoses. Simple mean again matches or beats selected GLS timely counts,despite GLS fixed-window optimality. Scanning thresholds,unknown onset and contaminated windows differ from a known-onset fixed test; single-window optimality does not guarantee the best first-alarm latency.

Freezing the oldrho=.9model when truerho=.99 causes200/200dense and199/200sparse healthy GLS false alarms. Correctly suppliedrho=.99model reduces those counts to18and11, but small-fault timely power remains1and0. Knowing the noise model does not remove all sensitivity/false-alarm trade-offs. No robust online regime adaptation is implemented.

## Reproduce and limitations

```bash
cd research/motor_oracle_v10
python -m pip install -r requirements.txt
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m unittest -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python replay.py --out results/reproduced
```

New output directory required. Independent verifier is included in replay. It reconstructs all12800records,64cells,12calibration thresholds,24MonteCarlo cells and1296analytic rows;raw contrasts/full scores saved for16representative cases,all packed alarm decisions saved. Other signals are regenerated from seeds. Original motor speed cancels algebraically from differences; parity tests check this against the original generator. No new faulty-feedback or physical-motor result is implied.

Gaussian assumptions,truthful original sampling,known primary/noise/offset assumptions and finite600s horizons are explicit. No common-mode,metadata corruption,asynchronous or real-world safety solution. Same-seed cloud replay is reproducibility,not more independent evidence or human peer review. No paid API/GPU or machinery used.

Next direction should alter a clearly specified resource/goal (sampling,noise,deadline) or reduce the gap to the ideal reference in configurations not ruled out. Do not tune on this holdout,replace original criteria after seeing results,or report oracle privileges as deployed capability.
