# Diagnostic memory V1 — fixed protocol

Recorded before V1 simulation/evaluation. This is a model-based numerical study, not a new theorem, hardware validation, or validated online-adaptation controller. Preserve pilot 0 unchanged.

## Question
Does the apparent need to retain raw history survive a sufficient-statistic baseline? Under a genuine finite diagnostic-state alphabet, does joint probe/quantizer design improve finite-horizon diagnosis over information-maximizing input design?

## Model and confounding
Dimensionless scalar dynamics x[k+1] = 0.8*x[k] + b*(1+v[k]). H0: b=0.25, sensor offset=0, initial x=1.25. H1: b=0.20, sensor offset=0.25, initial x=1.0. These are equilibrium states under u=1; with no probe both yield mean measurement 1.25. The measurement after each transition is y[k]=x[k+1]+offset+Normal(0,0.08^2), independent across time. Hypotheses have equal prior and equal misclassification costs. No process noise. Parameters are assumed known within each of the two hypotheses.

## Probe class and safety
18 observations. Four nonzero probes in the first 12 steps, each either -0.5 or +0.5, followed by 6 zero-probe steps. Enumerate all C(12,4)*2^4=7,920 schedules. Every schedule has probe energy sum(v^2)=1.0. Keep schedules satisfying 0<=x<=1.5 under BOTH hypotheses, including initial states; actual input must satisfy 0.5<=u<=1.5. This is only finite-model, disturbance-free safety, not deployment safety. Include no-probe as a zero-energy reference, not as an equal-budget competitor.

## Strong baselines and memory accounting
1. Batch Gaussian likelihood-ratio test using all observations.
2. Exact recursive Gaussian log-likelihood ratio (LLR): one real-valued diagnostic statistic, no raw history. Numerical implementation uses float64. Verify equality with batch LLR.
3. Fixed-center finite-state quantized LLR accumulator.
4. Posterior-recentered finite-state quantized Bayes filter: at each step, reconstruct log(P(state|H1)/P(state|H0)), add the current observation LLR, then quantize. This is a standard Bayesian compression baseline, NOT claimed as an invention or globally optimal finite-state machine.
For methods 3/4 use 2,3,4,8 bits (4,8,16,256 states); symmetric uniformly spaced reconstruction levels on [-L,L], nearest-level quantization, and L in {0.25,0.5,1,2,4,8,16}. First observation starts with hardwired prior LLR=0; subsequent steps retain only a state index. Final decoding uses the exact state likelihoods with equal priors.
These bit counts cover ONLY the persistent data-dependent diagnostic state. Shared clock (at least 5 bits), read-only model/input/quantizer tables, arithmetic working precision and current measurement are explicitly excluded and must be disclosed. Posterior-recentering uses additional read-only time/state tables. No total-RAM or minimum-memory claim.

## Selection without test data
Compute mean observation trajectories, Gaussian Bayes error and finite-state transition probabilities analytically using normal CDFs. For the 2-bit posterior-recentered filter, enumerate all admissible schedules and the declared L grid; retain the minimum-risk pair. Separately select the full-information-optimal schedule by maximum squared normalized mean separation. Include one fixed random admissible schedule chosen with seed 27001. For each displayed schedule and bit budget, select L by exact modeled risk, not Monte Carlo outcomes. Ties use first enumerated index. Optimality is ONLY over the declared finite schedule/quantizer family; no globally optimal input or finite-state algorithm claim.

## Held-out evaluation
After design choices are frozen in design.json, simulate 40,000 trajectories per displayed schedule (20,000 per hypothesis). Seed 2026102907, using paired Gaussian noise across schedules/methods. Report balanced errors, per-hypothesis errors, counts, Wilson intervals as descriptive episode-level summaries, exact modeled risk, paired error differences and empirical safety extrema. Do not treat paired schedules or samples within an episode as independent replications. Also evaluate noise-scale misspecification at 0.75 and 1.25 times nominal for the fixed classifiers; these are stress tests, not model-valid optimality guarantees. No retuning after observing tests.

## Verification
Unit tests must cover equilibrium confounding, dynamic propagation, constraints, schedule count/energy, LLR batch/online identity, analytic Gaussian Bayes risk, stochastic transition rows, no-information case, finite-state risk >= full-information Bayes risk, finite-state simulation agreement, argument validation, causality, and absence of true-state/label inputs in inference. Save source/artifact SHA256 manifest, software versions, full candidate design scores, design choices and episode-level error vectors. Keep negative results.

## Interpretation gates
Reject a general claim that finite-dimensional memory necessarily destroys diagnostic evidence: a sufficient LLR can be lossless here. Reject a universal claim of co-design benefit if no improvement occurs. Dynamic simulation is not yet continual adaptation, unknown-fault inference, nonlinear control, or an original doctoral contribution. Literature review must include finite-memory testing and existing safe active diagnosis, not only recent AI papers.
