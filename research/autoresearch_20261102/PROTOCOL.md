# AutoResearch independent validation — locked protocol (2026-11-02, US Eastern)

This is an **independent, bounded reproduction and falsification audit** inspired by the *ScientificTwo* research loop. It does **not** run Google's proprietary framework or Sakana AI's AI-Scientist-v2, use a paid LLM or establish peer-reviewed novelty. Automated GitHub Actions execute the predeclared tests and ablations; human/LLM review interprets their outcomes separately.

## Scope and immutable inputs

- Motor fault benchmark: `Alethevia/virtual-earth-language` commit `95a46ec42e0bdb66002325e6bae11c28f7690249`, PR #1.
- Diagnostic-memory V1: same repository commit `093e62d18c1b70dc80f671dc6066ff93b7a11723`, PR #4.
- Geography/weather/electricity manuscript: same repository commit `d77f7c57535bb8864db5abb9e6649f06c370abde` (main).
- Quantitative Alpha-Research: `Alethevia/Alpha-Research` commit `fcced69ac47ba26ad23174aac91bc50a1fbf0b72` (branch `claude/review-backtest-strategies-IqhK3`).

No existing project's protocol, calibration distribution, target, or published baseline is overwritten. New candidate experiments are **exploratory**. A baseline reproduced on the same data is not independent scientific discovery.

## Predeclared research questions and controls

**MOTOR-H1 — replication.** Rerun all existing unit tests and canonical 39 calibration + 360 test episodes, compare all 18 counts and three thresholds to locked `results/run_v1/summary.json`. Exact counts are expected on Linux with pinned inputs. A mismatch is an audit failure.

**MOTOR-H2 — distribution shift (exploratory).** Freeze canonical healthy-only thresholds, then separately calibrate 40 additional *new* healthy seeds (5100–5139) and 40 shifted-healthy seeds (5100–5139). A second proposed detector uses this mixed-healthy 80-episode calibration, with `alpha=0.05` order statistic. On untouched seeds 6000–6019 compare canonical vs shifted-aware thresholds for `healthy`, `healthy_shift`, `bias`, `bias_shift`, and `stuck`. Report false alarms, valid fault detections and pre-fault alarms for all methods. We predict fewer shifted-healthy false alarms but potentially reduced fault sensitivity; do not declare success if only one dimension improves. No threshold tuning on evaluation seeds.

**DIAG-H1 — replication.** Rerun 22 original tests, exhaustive design, and 40,000 observation-trajectory evaluations; match the reference table's 10 count/risk entries, zero batch/online decision disagreements, and chosen equal-energy probe. Report negative co-design outcome unchanged.

**DIAG-H2 — new Monte Carlo replication (exploratory).** Independently sample 5,000 traces per hypothesis with seed 2026110201 under the frozen optimal full-information probe and its 4-bit posterior classifier. Report both error counts, paired error difference and 95% descriptive interval. Numerical risk is computed independently by the original exact finite-state model, not fitted on those traces. In two additional noise-shift stress cases (1.5x and 2x), compare full-information oracle risk with the *frozen* 4-bit posterior rule using `frozen_design_risk`.

**GEO-H1 — reproducibility.** Run the existing offline suites, manuscript evidence assertions, and 65-model-fit replay against committed prepared daily data. Passing a software/data replay is not an external forecast-validity, raw-download, or 2026 holdout test.

**QUANT-H1 — code validity only.** Rerun the Alpha-Research offline unit-test suite, including anti-lookahead, determinism and risk-gate tests. There is no new market-price download, broker connectivity, backtest performance claim or live trade. A passing job does not validate investment returns.

## Falsification rules

- No automatic hypothesis-promotion or paper-acceptance state. Negative / null findings remain visible.
- Calibration/evaluation seed ranges must not overlap. Do not rerun with new parameters after viewing outcomes and call the rerun confirmatory.
- Do not count paired scenarios or timesteps as independent physical cases.
- Report denominators, weak or inconclusive results, dependency/runtime issues and all failed jobs.
- No arbitrary significance labels without paired uncertainty analysis.
- Simulated peer review must challenge confounding, data provenance, baseline parity, leakage and novelty; it is not independent human peer review.
- GitHub Actions source is read-only except for uploaded action artifacts; all study outputs are ephemeral action artifacts.
