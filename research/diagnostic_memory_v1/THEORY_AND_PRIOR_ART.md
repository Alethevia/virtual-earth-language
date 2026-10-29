# Theory audit and prior-art boundary

## 1. The strong baseline that removes the pilot-0 advantage
For two known deterministic mean trajectories mu_0(t), mu_1(t), independent additive Gaussian measurement noise of variance sigma^2, equal priors and equal costs, define

    d_t = mu_1(t) - mu_0(t)
    ell_t = d_t * (y_t - [mu_1(t)+mu_0(t)]/2) / sigma^2
    Z_t = Z_(t-1) + ell_t, Z_0 = 0.

Expanding the two Gaussian squared residuals shows that Z_T is exactly the full-data log likelihood ratio. The Bayes decision is H1 iff Z_T>0. For I=sum(d_t^2/sigma^2), Z_T has law N(-I/2,I) under H0 and N(I/2,I) under H1. Thus Pe=Phi(-sqrt(I)/2). This derivation is standard Gaussian testing, not an original theorem. A floating-point implementation is not a claim of infinite-precision finite-bit sufficiency.

Consequences: (i) saving fewer raw samples need not damage diagnosis; (ii) two scalar statistics with different semantics are not equally good summaries; (iii) a dynamic plant alone does not create an information-loss research contribution. The chosen open-loop plant has deterministic states conditional on each hypothesis; it reduces to non-identically distributed independent Gaussian observations. It does NOT yet reproduce the hidden-state stochastic filtering or unknown-model problem.

## 2. Exact analysis of a specified finite-state filter
A B-bit diagnostic register has K=2^B values. Conditional on hypothesis h, each observation increment is Gaussian with mean (2h-1)*kappa_t/2 and variance kappa_t, where kappa_t=d_t^2/sigma^2. Given reconstruction r_t(i) and bin boundaries c_j, its transition probability is

    P_h,t(i,j) = Phi((c_(j+1)-r_t(i)-(2h-1)*kappa_t/2)/sqrt(kappa_t))
                 -Phi((c_j-r_t(i)-(2h-1)*kappa_t/2)/sqrt(kappa_t)).

Endpoints are infinite. Propagate p_h,t+1=p_h,t P_h,t. At final time, Bayes readout for that compressed state has risk (1/2)*sum_j min(p_0,T(j),p_1,T(j)). The fixed-center method uses the chosen reconstruction levels. The posterior method uses r_t(i)=log(p_1,t(i)/p_0,t(i)), computed offline for the nominal experiment. This is a standard finite-state Bayesian method, not a new estimator or proof of optimality over all state machines.

A deterministic sample with kappa=0 contains no hypothesis information: implementation retains the register unchanged. The first informative step begins with prior zero, selected by the preknown schedule/clock. Unreachable states have no contribution. Read-only time/state tables are excluded from the B-bit diagnostic-register count but disclosed below. They cannot be omitted from any total-memory claim.

## 3. Memory accounting
- Batch reference: 18 float64 observations = 1,152 observation-storage bits.
- Recursive reference: one float64 diagnostic accumulator = 64 diagnostic bits; exact mathematical result uses one real statistic.
- Quantized filters: B=2,3,4,8 data-dependent state bits, only.
- Shared finite-horizon clock needs at least 5 bits; two 18-step float64 mean tables use 288 bytes; a float64 input schedule uses 144 bytes; current measurement and arithmetic scratch space are additional.
- The posterior table alone uses 18*2^B*8 bytes in this straightforward implementation (576, 1,152, 2,304, 36,864 bytes respectively). Quantizer thresholds/readout require additional ROM. No claim of smallest total implementation or actual B-bit hardware execution is made.

## 4. What the safety check does and does not establish
Every allowed schedule is checked against both known, disturbance-free model trajectories for all 18 sampled transitions, including initial states, and against input bounds. This is an exact finite-model/sampled-time check within this simulator. It is not safety under unknown parameters, process disturbance, actuator uncertainty, continuous-time intersample behavior or feedback adaptation. Measurement noise cannot change the plant because schedules are open loop; zero plant violations under measurement-noise stress is therefore not evidence of robust closed-loop control.

## 5. Sources actually checked in this research turn (29 Oct 2026)
1. Berg, Ordentlich and Shayevitz. Binary Hypothesis Testing With Deterministic Finite-Memory Decision Rules. ISIT 2020. Official IEEE IT Society abstract: https://www.itsoc.org/honors/wolf-award/binary-hypothesis-testing-with-deterministic-finite-memory-decision-rules ; author paper https://arxiv.org/abs/2005.07445 . Bernoulli, time-invariant finite-state bounds are not directly the same as this finite-horizon Gaussian experiment.
2. INRIA MEXICO 2014 annual report, Active Diagnosis for Probabilistic Systems: https://radar.inria.fr/report/2014/mexico/uid71.html . Explicitly studies safe active diagnosis and finite-memory controllers. Its discrete-event safety specification is different from continuous state bounds; nonetheless the phrase 'finite memory + safe active diagnosis' is NOT a previously untouched combination.
3. Chatzikiriakos, Jamieson and Iannelli. High Effort, Low Gain: Fundamental Limits of Active Learning for Linear Dynamical Systems. AISTATS 2026, PMLR 300:3115-3123. https://proceedings.mlr.press/v300/chatzikiriakos26a.html . Finite model classes, excitation-dependent sample complexity, active learning. Abstract verified; no claim of code-level reproduction.
4. Ni, Ornik, Chou and Coogan. Safe, real-time active model discrimination and fault diagnosis for nonlinear systems via differentiable reachability. IEEE RA-L 2026. Author publication page https://coogan.ece.gatech.edu/papers/ni2026safe.html ; DOI 10.1109/LRA.2026.3747586. This page describes finite candidate models, reachability and soundness; our script does not reproduce that method.
5. Additional leads, NOT used as reproduced methods: Flower and Hellman (1972), Hypothesis Testing With Finite Memory in Finite Time, and optimal finite-sample Gaussian finite-state testing (1976). Their primary-source listings were located, but a full technical comparison remains outstanding.

## 6. Research decision
The broad 'loss of diagnostic evidence under limited memory' novelty claim is unsupported. The present experiment establishes a reproducible benchmark and eliminates weak baseline comparisons. Even co-design within the declared 2-bit posterior-filter family selected the same input as full-information design, so it offers no improvement here.

A narrower candidate, NOT a demonstrated gap, is finite-horizon robust probing and diagnostic-state design when gain and offset belong to continuous uncertainty sets and there is a shared ROM/RAM/computation budget. First compare with existing composite testing, set-membership diagnosis, finite-state filtering and active diagnosis. Do not merely add constraints to manufacture a novelty claim. A later protocol must change hypotheses explicitly and use new evaluation seeds. Unknown time of change and closed-loop adaptation are separate extensions, not capabilities already implemented.
