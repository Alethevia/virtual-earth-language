"""Dynamic diagnostic-memory benchmark. All quantities are dimensionless.

No deployment or novelty claim. Only the data-dependent diagnostic register is
bit-limited; model tables, clock, scratch arithmetic and inputs are separate.
"""
from dataclasses import dataclass
from itertools import combinations, product
import math
import numpy as np
from scipy.special import ndtr


@dataclass(frozen=True)
class Model:
    a: float = 0.8
    b0: float = 0.25
    b1: float = 0.20
    baseline: float = 1.0
    sigma: float = 0.08
    horizon: int = 18
    probe_steps: int = 12
    pulses: int = 4
    amplitude: float = 0.5
    xmin: float = 0.0
    xmax: float = 1.5

    def __post_init__(self):
        vals = (self.a, self.b0, self.b1, self.baseline, self.sigma,
                self.amplitude, self.xmin, self.xmax)
        if not all(math.isfinite(v) for v in vals):
            raise ValueError('Nonfinite model parameter')
        if not (0 < self.a < 1 and self.b0 > self.b1 > 0 and
                self.baseline > 0 and self.sigma > 0 and self.amplitude > 0 and
                self.xmin < self.xmax):
            raise ValueError('Invalid model parameter')
        for n in (self.horizon, self.probe_steps, self.pulses):
            if isinstance(n, bool) or not isinstance(n, int) or n <= 0:
                raise ValueError('Time and pulse counts must be positive integers')
        if not self.pulses <= self.probe_steps <= self.horizon:
            raise ValueError('Invalid time/pulse ordering')

    @property
    def initial(self):
        return np.array([self.b0, self.b1]) * self.baseline / (1-self.a)

    @property
    def offset(self):
        return float(self.initial[0] - self.initial[1])


def trajectories(probes, model=Model()):
    """Return means (C,2,T) and true states (C,2,T+1) for BOTH hypotheses."""
    v = np.asarray(probes, dtype=float)
    if v.ndim == 1:
        v = v[None, :]
    if v.ndim != 2 or v.shape[1] != model.horizon or not np.isfinite(v).all():
        raise ValueError('Expected finite (C,horizon) probes')
    x = np.empty((len(v), 2, model.horizon+1))
    x[:, :, 0] = model.initial
    b = np.array([model.b0, model.b1])
    for t in range(model.horizon):
        x[:, :, t+1] = model.a*x[:, :, t] + b*(model.baseline+v[:, t, None])
    mu = x[:, :, 1:].copy()
    mu[:, 1, :] += model.offset
    return mu, x


def candidate_probes(model=Model()):
    rows = []
    for positions in combinations(range(model.probe_steps), model.pulses):
        for signs in product((-1., 1.), repeat=model.pulses):
            row = np.zeros(model.horizon)
            row[list(positions)] = model.amplitude*np.array(signs)
            rows.append(row)
    return np.asarray(rows)


def admissible(probes, model=Model()):
    v = np.atleast_2d(np.asarray(probes, float))
    _, x = trajectories(v, model)
    return ((x >= model.xmin-1e-12).all(axis=(1, 2)) &
            (x <= model.xmax+1e-12).all(axis=(1, 2)) &
            (np.abs(v) <= model.amplitude+1e-12).all(axis=1))


def separation(means, sigma):
    mu = np.asarray(means, float)
    if mu.ndim != 3 or mu.shape[1] != 2 or not np.isfinite(mu).all():
        raise ValueError('Expected finite (C,2,T) means')
    if not math.isfinite(sigma) or sigma <= 0:
        raise ValueError('sigma must be positive')
    return ((mu[:, 1, :]-mu[:, 0, :])/sigma)**2


def bayes_risk(info, noise_scale=1.0):
    q = np.asarray(info, float)
    if np.any(q < 0) or not np.isfinite(q).all() or not math.isfinite(noise_scale) or noise_scale <= 0:
        raise ValueError('Invalid information/noise scale')
    return ndtr(-np.sqrt(q)/(2*noise_scale))


def llr_increments(y, means, sigma):
    """Inference uses measurements and the two candidate means, never true labels."""
    y, mu = np.asarray(y, float), np.asarray(means, float)
    if mu.ndim != 2 or mu.shape[0] != 2 or y.ndim != 2 or y.shape[1] != mu.shape[1]:
        raise ValueError('Expected y=(N,T), means=(2,T)')
    if not np.isfinite(y).all() or not np.isfinite(mu).all() or sigma <= 0 or not math.isfinite(sigma):
        raise ValueError('Invalid observation/model')
    return (mu[1]-mu[0])*(y-(mu[1]+mu[0])/2)/sigma**2


def batch_llr(y, means, sigma):
    y, mu = np.asarray(y, float), np.asarray(means, float)
    # Algebraically independent reference; subtraction may round slightly.
    return (((y-mu[0])**2-(y-mu[1])**2)/(2*sigma**2)).sum(axis=1)


def online_llr(y, means, sigma):
    increments = llr_increments(y, means, sigma)
    z = np.zeros(len(increments))
    for inc in increments.T:
        z += inc
    return z


def grid(bits, span):
    if isinstance(bits, bool) or not isinstance(bits, int) or not 1 <= bits <= 10:
        raise ValueError('bits must be an integer in [1,10]')
    if not math.isfinite(span) or span <= 0:
        raise ValueError('span must be positive')
    levels = np.linspace(-span, span, 2**bits)
    boundaries = (levels[1:]+levels[:-1])/2
    return levels, boundaries


def transition(reconstruct, kappa, boundaries, hypothesis, noise_scale=1.0):
    """P(next state | old state,H). Batched across schedules; kappa>0 only."""
    r = np.asarray(reconstruct, float)
    q = np.asarray(kappa, float)
    if r.ndim != 2 or q.shape != (len(r),) or np.any(q <= 0):
        raise ValueError('Expected reconstruct=(C,K), positive kappa=(C,)')
    if hypothesis not in (0, 1) or noise_scale <= 0 or not math.isfinite(noise_scale):
        raise ValueError('Invalid hypothesis/noise scale')
    z = (boundaries[None, None, :] - r[:, :, None] -
         (2*hypothesis-1)*q[:, None, None]/2) / (np.sqrt(q[:, None, None])*noise_scale)
    cdf = ndtr(z)
    cdf = np.concatenate([np.zeros((*r.shape, 1)), cdf, np.ones((*r.shape, 1))], axis=2)
    return np.maximum(np.diff(cdf, axis=2), 0.)


def state_filter(kappas, bits, span, method, retain=False):
    """Exact finite-state Bayes error for a declared quantizer, not optimal FSM.

    Read-only reconstructions are computed under the nominal model, independently
    of evaluation data. Zero-information samples leave the register unchanged.
    The first informative step uses the fixed prior 0 (clock/schedule in ROM).
    """
    q = np.atleast_2d(np.asarray(kappas, float))
    if not np.isfinite(q).all() or (q < 0).any() or q.shape[1] == 0:
        raise ValueError('Invalid kappas')
    if method not in ('fixed_center', 'posterior'):
        raise ValueError('Unknown finite-state method')
    levels, boundaries = grid(bits, span)
    c, tmax = q.shape
    k = len(levels)
    p = np.zeros((c, 2, k))
    p[:, :, 0] = 1.
    seen = np.zeros(c, bool)
    tables = np.zeros((c, tmax, k)) if retain else None
    active = q > 1e-24
    for t in range(tmax):
        ix = np.flatnonzero(active[:, t])
        if not len(ix):
            continue
        if method == 'fixed_center':
            r = np.broadcast_to(levels, (len(ix), k)).copy()
        else:
            r = np.log(np.maximum(p[ix, 1], 1e-300)) - np.log(np.maximum(p[ix, 0], 1e-300))
        r[~seen[ix]] = 0.
        if retain:
            tables[ix, t] = r
        for h in (0, 1):
            tr = transition(r, q[ix, t], boundaries, h)
            p[ix, h] = np.einsum('ci,cij->cj', p[ix, h], tr)
        seen[ix] = True
    risks = 0.5*np.minimum(p[:, 0], p[:, 1]).sum(axis=1)
    result = dict(risk=risks, state_prob=p, decisions=(p[:, 1] > p[:, 0]),
                  bits=bits, span=span, method=method, boundaries=boundaries,
                  active=active, kappa=q)
    if retain:
        result['reconstruct'] = tables
    return result


def finite_predict(y, means, sigma, design):
    """Causal quantized filter for ONE schedule with fixed read-only tables."""
    inc = llr_increments(y, means, sigma)
    r = design['reconstruct']
    if r.shape[0] != 1 or r.shape[1] != inc.shape[1]:
        raise ValueError('Prediction requires single-schedule matching design')
    state = np.zeros(len(inc), dtype=np.int64)
    for t in range(inc.shape[1]):
        if design['active'][0, t]:
            state = np.searchsorted(design['boundaries'], r[0, t, state]+inc[:, t], side='right')
    return design['decisions'][0, state].astype(np.int8)


def frozen_design_risk(design, noise_scale=1.):
    """Evaluate fixed nominal tables, even under changed noise; do NOT retune."""
    if noise_scale <= 0 or not math.isfinite(noise_scale):
        raise ValueError('noise_scale must be positive')
    q = design['kappa']
    r = design['reconstruct']
    c, tmax, k = r.shape
    p = np.zeros((c, 2, k))
    p[:, :, 0] = 1
    for t in range(tmax):
        ix = np.flatnonzero(design['active'][:, t])
        if not len(ix):
            continue
        for h in (0, 1):
            tr = transition(r[ix, t], q[ix, t], design['boundaries'], h, noise_scale)
            p[ix, h] = np.einsum('ci,cij->cj', p[ix, h], tr)
    decision = design['decisions']
    return 0.5*((p[:, 0]*decision).sum(axis=1)+(p[:, 1]*(~decision)).sum(axis=1))


def wilson(count, n):
    if not isinstance(count, (int, np.integer)) or not isinstance(n, (int, np.integer)) or n <= 0 or not 0 <= count <= n:
        raise ValueError('Invalid counts')
    z = 1.959963984540054
    p, d = count/n, 1+z*z/n
    center = (p+z*z/(2*n))/d
    radius = z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0., float(center-radius)), min(1., float(center+radius))]
