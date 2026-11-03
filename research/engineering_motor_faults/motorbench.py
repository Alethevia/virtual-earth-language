"""Causal, simulation-only DC motor sensor-fault benchmark. See PROTOCOL.md."""
from dataclasses import dataclass
from functools import lru_cache
import math
import numpy as np
from scipy.linalg import expm, solve_discrete_are

DT = 0.01
DURATION = 18.0
WARMUP = 2.0
FAULT_TIME = 10.0
METHODS = ("tracking", "no_load", "load_augmented")
CONDITIONS = ("healthy", "healthy_shift", "bias", "drift", "stuck", "bias_shift")
# Trace: t, reference, load, true_speed, true_current, voltage, speed_sensor, current_sensor.

@dataclass(frozen=True)
class Motor:
    J: float = 0.002
    b: float = 0.002
    K: float = 0.05
    R: float = 2.0
    L: float = 0.02

    def __post_init__(self):
        if any(not math.isfinite(v) or v <= 0 for v in vars(self).values()):
            raise ValueError("Motor parameters must be finite and positive")

    def continuous(self):
        A = np.array([[-self.R/self.L, -self.K/self.L],
                      [self.K/self.J, -self.b/self.J]])
        B = np.array([[1/self.L, 0], [0, -1/self.J]])
        return A, B


def discretize(A, B, dt=DT):
    """Exact zero-order-hold discretization; inputs are constant per sample."""
    if not math.isfinite(dt) or dt <= 0:
        raise ValueError("dt must be finite and positive")
    A, B = np.asarray(A, float), np.asarray(B, float)
    if A.ndim != 2 or A.shape[0] != A.shape[1] or B.ndim != 2 or B.shape[0] != A.shape[0]:
        raise ValueError("Incompatible state/input matrices")
    if not (np.isfinite(A).all() and np.isfinite(B).all()):
        raise ValueError("Nonfinite dynamics")
    n, m = B.shape
    block = np.zeros((n+m, n+m))
    block[:n, :n], block[:n, n:] = A, B
    e = expm(block*dt)
    return e[:n, :n], e[:n, n:]


@dataclass
class PI:
    kp: float = 0.20
    ki: float = 0.60
    limit: float = 12.0
    integral: float = 0.0

    def step(self, error, dt=DT):
        values = (error, dt, self.kp, self.ki, self.limit, self.integral)
        if not all(math.isfinite(x) for x in values) or dt <= 0 or self.limit <= 0 or self.kp < 0 or self.ki < 0:
            raise ValueError("Invalid PI input or configuration")
        raw = self.kp*error + self.integral
        u = min(self.limit, max(-self.limit, raw))
        if raw == u or error*(raw-u) <= 0:
            self.integral += self.ki*dt*error
        return u


@lru_cache(maxsize=8)
def observer_design(augmented, dt=DT):
    """Fixed-gain current-only Kalman filter; never assimilates speed."""
    p = Motor()
    A2, B2 = p.continuous()
    if augmented:
        A = np.zeros((3, 3))
        A[:2, :2] = A2
        A[1, 2] = -1/p.J
        B = np.array([[1/p.L], [0.0], [0.0]])
        Q = np.diag([0.0001, 0.05, 0.000001])
    else:
        A, B = A2, B2[:, :1]
        Q = np.diag([0.0001, 0.05])
    Ad, Bd = discretize(A, B, dt)
    C = np.zeros((1, len(A)))
    C[0, 0] = 1
    R = np.array([[0.015**2]])
    P = solve_discrete_are(Ad.T, C.T, Q, R)
    gain = P[:, 0]/(P[0, 0]+R[0, 0])
    for a in (Ad, Bd, gain):
        a.setflags(write=False)
    return Ad, Bd[:, 0], gain


def generate_episode(seed, condition="healthy"):
    """Synthetic closed-loop plant; true state is stored only for evaluation."""
    if condition not in CONDITIONS:
        raise ValueError(f"Unknown condition: {condition}")
    rng = np.random.default_rng(seed)
    p = Motor(J=0.002*rng.uniform(.9, 1.1), b=0.002*rng.uniform(.9, 1.1),
              K=0.05*rng.uniform(.97, 1.03), R=2*rng.uniform(.95, 1.05),
              L=0.02*rng.uniform(.95, 1.05))
    if condition.endswith("shift"):
        p = Motor(J=p.J, b=p.b*1.30, K=p.K, R=p.R*1.35, L=p.L)
    Ad, Bd = discretize(*p.continuous())
    references = rng.uniform(25, 110, 4)
    loads = np.r_[0, rng.uniform(.005, .035, 3)]
    sign = rng.choice([-1, 1])
    n = round(DURATION/DT)
    speed_noise = rng.normal(0, .25, n)
    current_noise = rng.normal(0, .015, n)
    trace = np.empty((n, 8))
    state = np.zeros(2)
    pi = PI()
    held = 0.0
    for k in range(n):
        t = k*DT
        ref = references[np.searchsorted([5, 10, 14], t, side="right")]
        load = loads[np.searchsorted([3, 9, 14], t, side="right")]
        yw = state[1]+speed_noise[k]
        yi = state[0]+current_noise[k]
        if t < FAULT_TIME:
            held = yw
        elif condition in ("bias", "bias_shift"):
            yw += sign*6.0
        elif condition == "drift":
            yw += sign*10*(t-FAULT_TIME)/(DURATION-FAULT_TIME)
        elif condition == "stuck":
            yw = held
        u = pi.step(ref-yw)
        trace[k] = t, ref, load, state[1], state[0], u, yw, yi
        state = Ad@state + Bd@np.array([u, load])
    if not np.isfinite(trace).all():
        raise FloatingPointError("Nonfinite simulated trajectory")
    return trace


def residuals(trace):
    """Only t, reference, applied voltage and measured sensors enter diagnosis."""
    trace = np.asarray(trace, float)
    if trace.ndim != 2 or trace.shape[1] != 8 or len(trace) < 2 or not np.isfinite(trace).all():
        raise ValueError("Expected a finite (N,8) trace")
    if not np.allclose(np.diff(trace[:, 0]), DT):
        raise ValueError("Trace sampling interval must equal DT")
    out = np.empty((len(trace), 3))
    out[:, 0] = trace[:, 6]-trace[:, 1]
    for column, augmented in ((1, False), (2, True)):
        Ad, Bd, gain = observer_design(augmented)
        estimate = np.zeros(len(gain))
        for k in range(len(trace)):
            u_prev = trace[k-1, 5] if k else 0.0
            prior = Ad@estimate + Bd*u_prev
            estimate = prior + gain*(trace[k, 7]-prior[0])
            out[k, column] = trace[k, 6]-estimate[1]
    return out


def scores(residual_array, time_constant=0.10):
    r = np.asarray(residual_array, float)
    if r.ndim != 2 or not np.isfinite(r).all() or not math.isfinite(time_constant) or time_constant <= 0:
        raise ValueError("Invalid residuals/time constant")
    a = math.exp(-DT/time_constant)
    result = np.empty_like(r)
    old = np.zeros(r.shape[1])
    for k, row in enumerate(r):
        old = a*old + (1-a)*np.abs(row)
        result[k] = old
    return result


def episode(seed, condition="healthy"):
    trace = generate_episode(seed, condition)
    return trace, scores(residuals(trace))


def calibration_threshold(maxima, alpha=0.05):
    """Split-conformal order statistic across whole healthy episodes."""
    m = np.asarray(maxima, float)
    if m.ndim != 1 or not len(m) or not np.isfinite(m).all() or not 0 < alpha < 1:
        raise ValueError("Invalid calibration scores/alpha")
    rank = math.ceil((len(m)+1)*(1-alpha))
    return math.inf if rank > len(m) else float(np.sort(m)[rank-1])


def first_alarm(score, threshold):
    v = np.asarray(score, float)
    if v.ndim != 1 or not np.isfinite(v).all() or math.isnan(threshold):
        raise ValueError("Invalid score or threshold")
    start = round(WARMUP/DT)
    indices = np.flatnonzero(v[start:] > threshold)
    return None if not len(indices) else int(indices[0]+start)


def wilson(successes, trials):
    if trials <= 0 or not 0 <= successes <= trials:
        raise ValueError("Invalid binomial counts")
    z = 1.959963984540054
    p = successes/trials
    d = 1+z*z/trials
    c = (p+z*z/(2*trials))/d
    r = z*math.sqrt(p*(1-p)/trials+z*z/(4*trials*trials))/d
    return max(0., c-r), min(1., c+r)
