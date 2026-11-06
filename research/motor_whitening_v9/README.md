# V9: prewhitening is not automatically faster fault detection

**Scientific screen FAILED:17/20.** Three of four .5-rad/s five-second requirements fail. Established AR prewhitening and matched finite-window scans, not a novel algorithm, Google proprietary engine, hardware validation or lifetime safety guarantee. Original V1–V8 unchanged.

## Provenance and scope

Pre-fit protocol/source commitment:676bca0f04c4be7d67b53b2230a59afb9313da3d.
Independent training frozen before calibration:289ff0cf290bdbd71f518a05a9abff4ca510fc46.
Numerical calibration frozen before holdout:dacd521fdf5f5e0265b3b3cfa24f49208fe0f60c.
Published whitening.py matches preregistered SHA256 fa91377767f25aa848b0a4193c19c3d1973dd1eeab7488060975104a58f3b4d2 and Git blob393e66f53071a99de4573683aa117b6d03ae0f45.

128 independent healthy commissioning paths(32x60s per configuration),796 separate healthy600s calibration paths,9,200 held-out scenario trajectories,seven rules,81,200 method/horizon records,406 aggregate cells. Only200 independent base evaluation seeds;46scenarios and healthy prefixes are paired, not independent devices.

IMPORTANT: the correct instrument-specific healthy commissioning batch/model is supplied before monitoring. This is EXTRA prior information relative to V8's rate-only pooling, not an automatic online correlation detector. All NEW methods receive the same commissioning/calibration budget. The historical V8 CUSUM is separately labelled, not an equal-information architecture comparison.

As in V7/V8, injected biases affect downstream diagnostic READOUTS only; the healthy controller never sees them. Three existing speed observations, truthful acquisition metadata, regular synchronous common samples. No new hardware or control intervention, no asynchronous/dropout remedy and no physical-model fusion.

## Fixed experiment

Fit each pair's AR predictor using independent healthy paths, order20 dense and1 sparse, fixed ridge1e-6. Freeze it; do not fit on monitored test paths. Compare configuration-calibrated RMS,two-second signed mean,raw multiscale signed scan,whitened scan with a constant alternative,whitened matched STEP alternative(primary),historical V8 CUSUM,and abstention.

Step filtering is explicit: innovations e_t=d_t-sum phi_l*d_(t-l); a new step has transient g_j=1-sum_(l<=j)phi_l, not just its steady attenuation. Primary matched score uses the same transformed template. Fixed durations .2,.5,1,2,5,10,30seconds. Calibration includes maxima across all pairs/windows/times for600seconds. This is a finite-window statistic with an approximate AR model, not an exact ARMA likelihood theorem or anytime guarantee.

## New-sample .5-rad/s persistent faults, every cell /200

Late onset uniform300–330s, random sign. FIRST unique diagnosis must be correct; earlier wrong/premature accusations remain failures.

| Profile | Simple2s mean within5s | Raw signed scan within5s | Naive whitened within5s | Matched whitening within5s | Historical V8 CUSUM within5s |
|---|---:|---:|---:|---:|---:|
| dense iid |200|200|200|200|0|
| sparse iid |10|40|39|40|0|
| dense rho=.9 |30|41|27|22|46|
| sparse rho=.9 |0|0|1|1|1|

Matched candidate30second counts[200,200,200,101],eventual FIRST correct[200,200,200,199];conditional median delays[.2591,7.3149,9.5253,29.9051]seconds. Eventual success is not timely success. All20screen requirements remain fixed; the candidate fails the sparse iid,dense AR,sparse AR five-second checks, not the other17.

The dense-iid gain over old CUSUM is NOT evidence that whitening was needed: the simple two-second mean also achieves200/200 with the same new commissioning. In sparse iid,raw signed scan matches40/200. In dense AR,the candidate is9.5percentage points WORSE than raw scan(paired exploratory95% interval[-14,-5])and12points worse than historical CUSUM([-16.5,-7.5]). Against naive whitening,the -2.5point difference interval[-6,.5]includes zero. These1160paired intervals are unadjusted; no universal superiority is claimed.

A representative held-out dense-AR healthy pair's lag1 correlation falls from.7242 to.0045 after filtering. This verifies the intended local transformation, but does NOT imply independent residuals, adequate model fit at all lags, or better detection. It is one representative trace, not a new aggregate performance metric.

## Healthy alarms, adverse stress and memory after recovery

Core600s candidate generic false counts[dense iid,sparse iid,dense AR,sparse AR]=[4,17,7,3]/200;wrong-any=[0,0,0,1]/200. Large6rad/s within5s=[200,200,200,199]/200. Zero observed errors are not zero population risk; all Wilson intervals remain saved.

Stronger unseen rho=.99 with the same marginal SD,using frozen .9 commissioning: dense200/200 generic false and200/200 wrong accusations,then0/200 first-correct even for6rad/s. Sparse195/200 generic and180/200 wrong accusations; later.5rad/s only64/200 eventual first-correct. Independent training does NOT protect against changed dependence.

Two bad witnesses sharing6rad/s still cause200/200 wrong-primary accusations in every core profile. All-three common offsets cannot receive a unique correct diagnosis from pairwise evidence; isolated background false alarms are not common-mode sensitivity.

Dense iid two-second .5pulses are first-correct before recovery in200/200 candidate paths,BUT all200 also have accusations after recovery. Thus the excellent onset count does not establish timely fault clearance. Sparse iid pulses are0/200 before recovery. Dense alternating-sign.5faults are200/200; sparse only5/200 eventually first-correct(0within5s). Multiple time scales do not solve every shape/rate problem.

## Verification and reproduction

24pre-evaluation integrity tests passed. Separate verifier checked12model equations,20threshold ranks,all81,200saved records,406cells,3,248Wilson intervals,1,160paired intervals,and18complete representative packet/score paths. Scan-score max discrepancy<4.5e-11;legacy CUSUM2.77e-8 from different summation. Representative discrete decisions agree exactly. Same-author second implementation,not independent human peer review. All raw observations are regenerable from code/seeds; only18complete representative raw traces are stored,not every full input trace.

```bash
cd research/motor_whitening_v9
python -m pip install -r requirements.txt
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m unittest -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python replay.py --out results/reproduced --workers 2
python verify.py results/reproduced
```

Use a NEW directory. Cloud replay checks all406integer cells and insists the scientific screen remains false17/20; verify actual workflow status separately. A source-copy HTTP request failed because local DNS was unavailable; connector-based commitments succeeded. Reference-builder import initially selected a parent helper with the same name; rebuilding the reference directly corrected only packaging,not experimental code/results. No fitted coefficient,threshold,window,seed or criterion was changed after holdout.

Primary sources:NIST autocorrelation guidance https://itl.nist.gov/div898/handbook/eda/section3/eda35c.htm ; NIST statistical monitoring under autocorrelation https://www.nist.gov/publications/statistical-process-monitoring-autocorrelated-data ; Sun&Zou,IEEE TIT2024/arXiv2310.08789 https://arxiv.org/abs/2310.08789 . These motivate established ideas,not validation of this implementation.
