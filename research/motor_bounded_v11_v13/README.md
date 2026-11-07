# V11–V13: bounded iteration, frozen confirmation, then objective assessment

**Matched-condition confirmation PASS; broad robustness FAIL.** Three predeclared rounds completed locally. Established mean/matched scans, not a new algorithm. Changed sampling/noise resources are NOT equal-input algorithm superiority. No hardware, faulty control feedback, safety certification, publication or independent human peer review. Parent V1–V10 are unchanged; this draft does not target main.

## Provenance

Protocol before any performance run: `4a7727421f3148aa6de2e0355b2879a7b53f9892`.
Source hash after 26 integrity tests, before calibration: `4834e44ee1ef89ab1a1f4d3ddab543cfb7e664e6`.
R11 thresholds before tests: `9949d893e273c8a3bcb8e23065d92f8f2f321622`.
R12 thresholds before comparison/selection: `5fa16ae8dfaedc9da20ff76a649e50cccad74764`.
R13 method and thresholds before fresh confirmation: `fa45c24290f47372939b726c408e3ad01140970a`.
Experimental SHA256: `0b244265f65d21dba760f1cfc5ba73a696ae6b77ccf453adcda24e25035a8eb7`; published blob `1bf3985f439761808ed226cebdde87ecc705d73a` matches exactly. No experimental source, threshold or criterion changed after outcomes.

## R11 — sampling and noise are different resources

Known-primary binary alarm, simple5s mean,600s monitoring. Base rho=.9 per .01s; downsampling preserves its physical time scale. Scaling noise reduces BOTH white and correlated noise amplitudes; hardware feasibility/cost is unmodeled. Same base innovations paired across configurations. Each count /300, .5rad/s bias, first valid alarm within5s; earlier alarms remain failures.

| Rate | Noise scale1 | Scale.7 | Scale.5 |
|---|---:|---:|---:|
|2Hz|13|47|160|
|10Hz|81|222|287|
|20Hz|110|249|290|
|100Hz|110|260|291|

At20Hz, scale.5 minus original timely rate +60percentage points (paired exploratory95% interval54.33–65.67). At original noise,100Hz minus20Hz is0points, interval[-3.67,3.67]; this is no observed gain, NOT proof of population equality. Increasing sampling alone did not solve this particular monitoring problem; better total noise characteristics did. This is a resource intervention, not an algorithmic breakthrough or proof every sensor can achieve the assumed noise reduction. Healthy counts at20Hz are18/300 in every scaled arm.

## R12 — unknown-channel localization and strong simple controls

Unlike R11, the detector must decide which of three channels failed. All compared methods get the SAME received readings, nominal covariance,199healthy calibration paths, and whole-path/all-pair error calibration. Three methods:5smean, raw multiscale signed scan, steady-state Kalman-innovation matched-step scan. Steady-state initialization is included in calibration, not claimed as exact quickest-detection optimality.

At20Hz/noise.5, each /200:

| Metric | Mean5 | Raw scan | Innovation scan |
|---|---:|---:|---:|
|Healthy generic alarms|14|3|7|
|Healthy wrong-any|3|0|0|
|.5 persistent first correct within5s|197|196|196|
|1rad/s first correct within5s|198|200|200|
|1rad/s median successful delay(s)|1.587|.587|.501|
|2s pulse first correct before recovery|21|61|73|
|Pulse post-recovery accusations|40|53|40|

The preset selection rule chooses mean5 for persistent-small-fault timely counts, but its one-case advantage is NOT statistically persuasive: mean-minus-raw +.5points, interval[-1.5,3]; mean-minus-innovation interval[-1.5,2.5]. Selection is a rule, not proof of superiority. Scans are faster on larger faults and detect more short pulses; no universal winner. Pulse improvement remains inadequate for reliable transient monitoring and clearance.

At original correlated noise, timely .5 counts at20Hz are46/14/14 and at100Hz60/21/22 (mean/raw/innovation). Thus new modeling alone still fails the80% timely target. Dense independent noise gives200/200 for all methods. R12 is a comparison/selection set, NOT the final independent confirmation set.

## R13 — frozen mean5, independent generator and genuinely fresh seeds

The20Hz/noise.5 resource arm was specified BEFORE R11 results. Method/threshold selected from R12 then publicly frozen before all400fresh test seeds. Independent explicit state recursion and PCG64DXSM generator, same-law Gaussian check plus changed-distribution stresses. This is NOT physical-world external validation. Regular synchronized timestamps, known nominal covariance/offsets and single identifiable fault are still assumptions.

Matched Gaussian confirmation:
- Healthy general false alarms20/400=5%, Wilson95[3.26%,7.60%]. Wrong-any2/400=.5%, interval[.137%,1.804%].
- .5rad/s persistent bias:397/400=99.25% first-correct within5s, interval[97.82%,99.74%]; eventual first-correct398/400; successful median delay3.121s.
- 1rad/s:398/400 timely, median1.569s.
- Single auxiliary faults:395/400 and396/400 timely first-correct.

All six matched-confirmation point checks pass. Individual confidence bounds also lie on the required side in these six cells; they are NOT simultaneous certificates, lifetime guarantees or hardware evidence.

Frozen stress results, each /400:

| Noise family | Healthy generic alarms | Healthy wrong-any | .5bias first-correct within5s |
|---|---:|---:|---:|
|Matched Gaussian|20|2|397|
|Student-t5 latent innovations, equal variance|35|11|397|
|Student-t3 white sensor noise, equal variance|76|4|397|
|Two time scales, equal total variance|400|400|1|
|True rho=.99, frozen rho=.9 model|400|400|0|
|Primary white noise +25% after180s|22|3|397|

Student-latent8.75% false alarms pass the point criterion but Wilson upper bound11.93% exceeds10%; do not claim a confidence-level pass. Heavy-white19% general false alarms fails even though unique mistakes are few. Two-scale/rho99 conditions defeat the frozen monitor. **Broad robustness fails.**

Two-second pulse: only20/400 diagnosed before recovery,62/400 have accusations after recovery. Two auxiliary common biases:400/400 blame the healthy primary. All-three shared bias: no uniquely correct detection;20generic/2unique outputs are the same background errors as healthy paths, not common-mode sensitivity.

## Accounting and verification

R11:199independent calibration base seeds paired over12configurations,300independent evaluation base seeds,14,400case records,48cells. R12:199different calibration base seeds paired over5configurations,200different evaluation base seeds,9,000scenario paths/27,000method records,135cells. R13:400fresh base seeds paired across18conditions,7,200paths/records,18cells. Across the three test stages there are900independent base seed groups, NOT30,600independent devices. Report48,600method records,201cells; do not count replay or paired conditions as new independent evidence.

26pre-evaluation tests. Separate postprocessor checks27calibration values, every aggregate over48,600records,1,809Wilson intervals and57complete representative input/score paths (87method outcomes); max score discrepancy4.4942e-12. It does NOT independently regenerate every raw path; complete raw representative signals are stored, others regenerable.26paired intervals are exploratory and unadjusted. Verification is same-author, not third-party peer review. Check actual CI status before claiming cloud completion.

## Objective assessment and stop rule

The new achievement is a simpler, explicitly resource-conditioned simulation solution that survives a genuinely fresh same-law confirmation set; it does NOT rescue the original-noise target, solve arbitrary shifts/common-mode faults, or establish a new algorithm. A research benchmark/technical report is justified; publication novelty and field utility still require literature positioning and independent/real-data evaluation. Stop after these three rounds. Package the result instead of automatically starting another variant.

## Replay

```bash
cd research/motor_bounded_v11_v13
python -m pip install -r requirements.txt
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m unittest -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python replay.py --out results/reproduced --workers 2
```

New output directory only. Full replay asserts all201integer cells,27thresholds,selected mean5,matched PASS and broad FAIL. No paid API/GPU or real device used. Protocol and all prior unsuccessful results stay intact.

Prior art: NIST autocorrelated monitoring https://www.nist.gov/publications/statistical-process-monitoring-autocorrelated-data ; Sun & Zou https://arxiv.org/abs/2310.08789 . Standard methods do not acquire new guarantees merely by reproducing this code.
