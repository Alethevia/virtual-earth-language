/* Simulation reference only: NOT a safety-certified or deployable motor driver. */
#include <math.h>

double pi_step(double error, double dt, double kp, double ki,
               double limit, double *integral) {
    if (!integral || !isfinite(error) || !isfinite(dt) || !isfinite(kp) ||
        !isfinite(ki) || !isfinite(limit) || !isfinite(*integral) ||
        dt <= 0 || limit <= 0 || kp < 0 || ki < 0) return NAN;
    double raw = kp*error + *integral;
    double u = fmin(limit, fmax(-limit, raw));
    if (raw == u || error*(raw-u) <= 0) *integral += ki*dt*error;
    return u;
}
