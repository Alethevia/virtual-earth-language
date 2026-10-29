# Diagnostic memory under lossy online adaptation — pilot 0

**Status: mathematical sanity check, not a new algorithm, safety proof, robotic experiment or publication.**

## Question and locked pilot

Can lossy model-state compression remove evidence that distinguishes two hypotheses? We deliberately construct a Gaussian example to illustrate the established data-processing principle, not to claim a new result.

Two equally likely hypotheses generate eight pairs of independent noisy probes. Under H0, probe A has mean +0.4 and B -0.4; under H1, signs reverse. Each sample has Gaussian SD 1. The compressed learner retains only the grand mean of 16 samples. This has the same distribution under both hypotheses, giving Bayes error 0.5. The evidence-preserving learner retains the signed A-minus-B contrast. Its theoretical Bayes error is Phi(-sqrt(2*m)*d/sigma), m=8.

Use 10,000 synthetic independent episodes, seed 20261029. No fitted parameters.

## Reproduce

```bash
cd research/diagnostic_memory_pilot
python -m pip install -r requirements.txt
python -m unittest -v
python pilot.py
```

## Results (first run)

- Three local tests passed.
- Compressed statistic: error **0.4966**.
- Evidence-preserving contrast: error **0.0584**; analytic error **0.0547993**.

This is a *deliberately weak compression baseline*. It is not a fair comparison against modern fault diagnosis, and no feedback plant, safety set, or online learning has yet been implemented. No originality is claimed.

## Next research gate

1. Review existing sufficient-statistic, controlled-sensing, finite-memory sequential-testing and safe-active-diagnosis results.
2. Specify a dynamic plant, bounded control set, fault model and precise memory budget.
3. Propose a falsifiable claim; first seek counterexamples and reductions to known theorems.
4. Compare with an optimal finite-memory estimator, likelihood-ratio test and relevant active diagnosis baselines at equal input and information budgets.
5. Freeze a new protocol before confirmatory tests; retain negative results.

## Prior work

- Ni et al. (2026), *Safe, Real-Time Active Model Discrimination and Fault Diagnosis for Nonlinear Systems via Differentiable Reachability*, IEEE RA-L, DOI 10.1109/LRA.2026.3747586.
- Chatzikiriakos et al. (2026), *High Effort, Low Gain: Fundamental Limits of Active Learning for Linear Dynamical Systems*, AISTATS / PMLR 300.
- Deshmukh et al. (2021), *Sequential controlled sensing for composite multihypothesis testing*, Sequential Analysis.
- Guo et al. (2023), *Active fault diagnosis for linear stochastic systems subject to chance constraints*, Automatica 156, 111194.

AI-assisted code and prose require human understanding, independent replication, and substantive development before being represented as individual research.
