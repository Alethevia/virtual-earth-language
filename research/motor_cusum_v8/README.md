# V8: signed accumulation helps selected persistent faults, but fails timely detection

**Scientific screen FAILED: 16/20 checks pass; all four .5-rad/s within-five-second requirements fail.** Established CUSUM and signed-mean baselines, not a new algorithm. Downstream diagnostic readouts only; no faulty feedback, hardware, safety or anytime guarantee. Original V1–V7 unchanged.

## Commitments and execution

Protocol/source SHA before calibration: `1e7f67e68632c249e841964c2c68bee7e32db05e`. Numerical calibration/hash before holdout: `216464bdaabea3407205e21f31de0983a41d7346`. Published source matches SHA256 `82df678ef7ab82db02580c5b6c058d97f9c727f16f8830814a2bd2934402268a`.

796 healthy calibration paths;10,800 held-out600s scenario trajectories;seven rules;92,400 method/horizon records;462 cells. Only200 independent base test seeds, paired across54 scenario families and healthy prefixes. Same-seed replay is not more independent evidence.

24 integrity tests passed locally. Separate verifier rebuilt every record/cell,21 calibration values,4,158 Wilson intervals,1,056 paired intervals and18 complete raw-packet score paths. RMS/mean differences<6.3e-14; CUSUM difference2.879e-8 from algebraically different summation. All representative decisions agree exactly. Same-author checking, not independent human peer review. Check cloud CI status separately.

## Fixed methods and fairness

Each distinct common acquisition is consumed once. For signed pair difference d and declared offset/quantization allowance B, Splus=max(0,Splus+d-.25-B), Sminus=max(0,Sminus-d-.25-B). Score=max(Splus,Sminus); no added reset at alarms/faults/epochs. The intrinsic max-with-zero is standard CUSUM. Unchanged V7 quality RMS and two-second signed mean are strong controls.

All new rules use the SAME796 healthy paths,600s horizon and rank190/199 per profile. Rate thresholds take maxima of iid/rho=.9 profile thresholds; rate is inferred from matched timestamps, not true rho. Universal takes maximum across rates. Historical V7 is separately labelled. No code/threshold/criterion changed after holdout.

Thresholds[dense,sparse]: RMS[1.6062664471,2.5202761625], mean[.8545401260,1.6345234856], CUSUM[170.2623770996,9.9942182561]. CUSUM uses observation-count units, not elapsed time. Universal CUSUM can therefore be unnecessarily slow for sparse reporting. No architecture-only win over the old universal RMS is claimed.

## Late .5-rad/s persistent faults, every cell /200

Onset uniformly300–330s; all earlier mistakes retained, no survivor filtering.

| Profile | Matched rate RMS within5s | Signed mean within5s | Rate CUSUM within5s | CUSUM within30s | CUSUM eventually first-correct | Conditional median delay |
|---|---:|---:|---:|---:|---:|---:|
| dense iid |187|0|0|200|200|8.21s|
| sparse iid |6|0|0|172|200|24.60s|
| dense rho=.9 |8|38|54|198|198|6.41s|
| sparse rho=.9 |0|1|0|168|199|19.15s|

All four five-second CUSUM cells fail the predeclared80% requirement. Sparse correlated-noise matched RMS eventually first-correct16/200 vs CUSUM199/200, but CUSUM remains0/200 within5s. Dense iid reverses the ranking: RMS187/200 within5s vs CUSUM0. Mean is also faster on some1rad/s cases. No universal winner.

Dense rho=.9 CUSUM-minus-matched-RMS five-second difference23 percentage points (paired exploratory interval17–29.5125), but absolute sensitivity only27%. Intervals are unadjusted for multiple comparisons. Against the simple mean, five-second improvement is8 points, interval2–14.5; eventual correct counts both198/200. Conditional delays exclude failures and must be read with counts.

## Healthy alarms and preserved failures

Core600s rate-CUSUM generic alarms[dense iid,sparse iid,dense AR,sparse AR]=[0,0,9,11]/200; wrong-any=[0,0,4,3]/200. Large6rad/s within5s=[200,200,198,199]/200. These meet the other16 checks; zero observations do not prove zero population risk.

Held-out rho=.99 with SAME truthful marginal SD: dense200/200 generic alarms and200/200 wrong accusations; sparse200/200 generic and199/200 wrong accusations. Dense paths all wrongly alarm before either later fault, so first-correct0/200 even for6rad/s. This is changed dependence, not hidden noise-SD misreporting.

Alternating +/- .5rad/s every.5s: CUSUM0/200 first-correct in both iid sampling profiles; matched RMS200/200 dense and154/200 sparse. Two-second .5 pulses: CUSUM0/200 before recovery. Matched dense RMS first-correct95/200, but98/200 paths also have accusations after recovery. Pulse scoring never credits post-recovery detections. Neither memory nor eventual detection is universally safe.

Two auxiliary sensors share6rad/s: CUSUM200/200 wrongly blame healthy primary in every main profile. All-three common bias yields no first-correct unique diagnosis. Pairwise evidence cannot uniquely identify shared offsets. Single-auxiliary controls and generic/unresolved outcomes remain saved.

## Limits and execution notes

A fixed CUSUM designed for .5rad/s need not detect smaller/sign-alternating shifts. Correlations included in calibration drive a high dense threshold; changing them again destroys reliability. Finite600s empirical calibration is not an anytime/lifetime theorem. Correct metadata, independent witnesses and a single identifiable fault remain assumptions. V7 healthy nominal background and diagnostic-only faults are NOT closed-loop faulty-machine or real-world validation.

The first verifier attempt timed out due to pure-Python per-time loops; only verification vectorization changed, never experimental source/results. An unsupported interactive-terminal call did not execute an experiment. Full local raw outputs and logs are supplied in the conversation archive.

## Reproduce

```bash
cd research/motor_cusum_v8
python -m pip install -r requirements.txt
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m unittest -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python replay.py --out results/reproduced --workers 2
python verify.py results/reproduced
```

New output directory only. Replay checks all462 integer cells and insists the scientific screen remains false. No paid model/GPU, trade or actual machine is used; CI uses workflow resources.

Primary sources: NIST CUSUM recursion/slack, https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/cusum.htm ; Polunchenko & Raghavan, https://arxiv.org/abs/1706.00824 ; Huang & Veeravalli, https://arxiv.org/abs/2408.05817 . Established ideas/limitations, not certification of this implementation.
