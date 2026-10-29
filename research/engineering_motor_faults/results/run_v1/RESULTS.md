# Simulation results — protocol v1

Synthetic data only. Each cell is count/60; faults require no earlier alarm.

| Condition | Tracking | No-load observer | Load-augmented observer |
|---|---:|---:|---:|
| healthy | 2/60 | 1/60 | 2/60 |
| healthy_shift | 5/60 | 60/60 | 60/60 |
| bias | 1/60 | 17/60 | 17/60 |
| drift | 1/60 | 29/60 | 28/60 |
| stuck | 7/60 | 57/60 | 56/60 |
| bias_shift | 2/60 | 0/60 | 0/60 |

Healthy rows report false alarms (lower is better); fault rows report valid detections (higher is better).
Confidence intervals and conditional delays are in summary.json. Healthy_shift is outside the calibration distribution.
No hardware validation, fault-tolerant control, novelty, or publication claim is made.
