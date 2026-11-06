# Amendment 01 — numeric replay rather than byte identity

Recorded after first audit run [41575628500](https://github.com/Alethevia/virtual-earth-language/actions/runs/41575628500), on 2026-11-02 Eastern, before retry.

The geography job's predeclared extra assertion was too strict: it demanded exactly zero floating-point difference in a 65-fit model replay on a fresh GitHub Actions Python 3.12.15 environment. All existing geography offline tests, evidence assertions, and replay steps passed, but the replay output had a **maximum absolute prediction difference of 3.765308065339923e-09 MW**, and its prediction CSV was not byte-identical. This is a tiny numerical roundoff effect in the same committed prepared inputs, NOT a new raw-data-source verification and NOT a new evidence of forecasting accuracy.

We replace the auxiliary check with a numerical tolerance of **1e-7 MW** (0.0001 W) and continue requiring 9,022 compared predictions, 65 refits, no raw downloads, locked parameter selection and original evidence tests. Preserve original run and error. No model design, outcome definition, calibration or statistical criterion changes.

This correction improves portability while remaining much stricter than meaningful electricity-load forecast resolution. We make no claim that the original byte-level reproduction held across runtime versions.
