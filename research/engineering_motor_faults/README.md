# Motor Fault Benchmark / 电机传感器故障诊断

**Status: working simulation pilot, not hardware validated, not a published paper.**

This independent engineering module compares three causal speed-sensor alarms in a voltage-limited PI-controlled DC motor: tracking error, a current-only no-load Kalman observer, and a current-only load-augmented observer. It is separate from the repository's language and geography experiments.

## Reproduce

Python 3.11+ and a C compiler are required; the reference run used Python 3.13.5 on Linux. On Windows, use WSL for the supplied C parity test.

```bash
cd research/engineering_motor_faults
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python run_experiment.py --out results/reproduced_v1
```

Use a new empty output directory for every run. Reference summaries and the manifest are under `results/run_v1`; the script regenerates the full episode CSV and six sample traces. The downloadable project archive also includes those raw outputs. Numerical hashes may differ across platforms; compare numerical values rather than requiring bitwise floating-point identity.

## What was actually verified

- 26 local tests passed, including exact-ZOH identities, torque sign, observer observability/stability, causality, no ground-truth leakage, and calibration ranks.
- The C PI controller was compiled with warnings treated as errors; 3,000 randomized steps matched Python to 12 decimal places.
- 39 calibration and 360 held-out simulation episodes were executed. Six conditions share paired seeds; these are not independent physical experiments.
- The protocol was committed before the benchmark results: `05cdb01f2b5284207229736cec39cc6a90cd6432`.

## Results, including failures

The load-augmented observer generated 2/60 healthy-episode false alarms, detected 17/60 bias faults and 56/60 stuck-sensor faults, but falsely alarmed on all 60 healthy parameter-shift episodes. It did not improve on the no-load observer in this pilot. See [results](results/run_v1/RESULTS.md) and [the working paper](PAPER.md). Passing software tests does not establish diagnostic robustness.

## 中文说明

这不是“已经发表的工程论文”，也不是工业现场验证。第一版完成了物理建模、带抗积分饱和的 PI 控制、两种状态观测器、整段实验校准、故障注入和可重复测试。最重要的负结果是：只增加负载估计，仍无法抵抗电机参数失配；不能把所有异常残差都当成传感器损坏。

`PAPER.md` 是包含真实仿真结果的英文工作稿，`PROTOCOL.md` 是预先固定的实验方案，`LEARNING.md` 是作者需要亲自掌握的推导与复现任务。AI 辅助生成的代码和文字必须经过作者复核，不能冒充已完成的个人研究训练、硬件经验或论文发表。

## Boundaries

No employer data, proprietary machinery details or claimed university affiliation is used. No novelty, admission probability, publication acceptance or hardware performance is asserted. This code must not be deployed on real machinery or used as a safety interlock. C parity covers the PI arithmetic only, not a complete embedded diagnostic implementation.
