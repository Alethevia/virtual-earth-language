# Gaussian oracle bound and its exact scope

This is an application of the established Neyman–Pearson lemma, not a new general impossibility theorem.

## Data and strictly favorable information

Original V7–V9 diagnostic readouts: primary y0(t)=w(t)+u(t)+e0(t)+bias(t); auxiliaries yi(t)=w(t)+ei(t)+ci. Independent e channels have variance .0625. Correlated profiles add stationary primary latent u with variance q=.5 and rho=.9 or .99 per .01-second tick. Auxiliaries do not measure this latent noise. Diagnostic faults do not affect the healthy controller or w(t).

Reveal to a genie the entire true speed waveform, fixed offsets, true covariance, the actual fault onset, primary target, sign and the latent u at the last pre-fault primary acquisition. These are strictly MORE favorable than the monitored data. Do NOT reveal subsequent latent innovations. Conditioned on this information, other channels contain only independent signal-free noise. Prior observations add nothing once that last latent state is known by the Markov property. The unknown future Gaussian innovations remain.

With sampling interval m ticks, a=rho^m. After subtracting the known conditional mean, n post-change primary observations have covariance C_ij=q*a^|i-j| - q*a^(i+1)*a^(j+1) + r*1(i=j), indices0..n-1, r=.0625. Thus the entire favorable experiment is N(0,C) versus N(delta*1,C), with sign known. For iid q=0. A contrast-only tier instead has r=.09375; a stationary post-only tier omits the subtracted rank-one term and is NOT an upper bound for procedures with extra history.

## Derivation

The log likelihood ratio equals delta*1' C^-1 X - .5*delta^2*I, with I=1' C^-1 1. The statistic Z=(1' C^-1 X)/sqrt(I) is N(0,1) under health and N(delta*sqrt(I),1) under the signed alternative. The most powerful size-alpha test rejects above z_(1-alpha); exact power is Phi(delta*sqrt(I)-z_(1-alpha)). Minimal ideal amplitude for80% power is (z_(1-alpha)+z_.8)/sqrt(I).

The experiment computes I by exact Kalman innovation factorization. A separate verifier uses AR tridiagonal precision and Woodbury, with direct Cholesky checks. Monte Carlo generates explicit colored observations, not merely an assumed scalar Z.

## Why this can bound an original causal monitor

Suppose the original monitor's TRUE probability of any false alarm during600s is <=alpha under the specified healthy model. For each fixed onset/sign, the event that its first correct diagnosis occurs by onset+5s is measurable from observations up to that deadline and has null probability <=alpha. Giving the rule the genie information cannot reduce the maximum attainable power. Hence the original timely-correct probability is no larger than the genie NP power.

Onset is continuously distributed independently of sampling. A2Hz primary supplies exactly10post-fault samples over5s almost surely; exact-grid endpoint cases have probabilityzero. The original .2-second decision grid cannot create additional samples. Averaging over the given onset/sign distribution preserves the bound, because after centering the genie experiment is identical across those values.

The bound requires the model and population false-alarm assumption. A particular empirical sample reaching160/200does not contradict a79.33%population upper bound. Likewise an observed0/200false count does not establish a10%population constraint. Extra sensing, higher rates, different noise, closed-loop effects or different goals change the experiment and may change the bound. This is NOT an injunction against pursuing the project.

## Numerically evaluated implications

For delta=.5,deadline5s,the most favorable primary/latent genie at alpha=.10 has power: dense iid~1; sparse iid.9999997709; dense rho=.9 .9951263876; sparse rho=.9 .7933103738; dense rho=.99 .9661625806; sparse rho=.99 .5195817032.

At sparse rho=.9 and alpha=.05 the power is.6753228; the ideal amplitude for80%power is.592155rad/s. At alpha=.10 the necessary ideal amplitude is.505635rad/s. These are necessary ideal limits, not sufficient operational settings. The79.33versus80difference is narrow and model-specific; do not round it into a broad engineering law.

High oracle power does NOT prove achievability when the onset, sign and channel are unknown. V10's separately calibrated600sreference scans are deliberately labeled known-target binary alarms, not unique sensor diagnosis. Their outcomes cannot be compared to the oracle upper bound as equal-information algorithm performance.

Sources: https://stat210a.berkeley.edu/fall-2024/reader/hypothesis-testing.html ; https://online.stat.psu.edu/stat415/lesson/26/26.1 . Prior sequential context: https://arxiv.org/abs/2310.08789 . None certifies this implementation.
