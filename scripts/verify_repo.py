#!/usr/bin/env python3
"""
Repo verifier for virtual-earth-language (MWE v0.1.0)
Checks:
  1) Required files exist (README, LICENSE, CI, Makefile, minimal_run).
  2) C↔E 编解码回环一致 (roundtrip).
  3) 最小实验 100 次：Success、Topo~、AvgLen 合理。
  4) 子进程跑 minimal_run.py 正常。
  5) 本地 pytest 通过（可选：若本机未装 pytest 会跳过）。
Exit code 0 = PASS, 非 0 = FAIL with reason.
"""
import os, sys, re, subprocess, shutil, random, pathlib, textwrap

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC  = ROOT / "src"
sys.path.insert(0, str(SRC))

# --- 1) Files exist ---
required = [
    ROOT/"README.md",
    ROOT/"LICENSE",
    ROOT/"Makefile",
    ROOT/"experiments"/"minimal_run.py",
    ROOT/".github"/"workflows"/"ci.yml",
]
missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]

# --- 2) Import modules & roundtrip checks ---
errs = []
try:
    from ontology.slots import SLOTS, VOCAB
    from envs.referential import sample_semantics
    from agents.speaker import Speaker
    from agents.listener import Listener
    from explain.codec import (
        sem_from_code, code_from_sem,
        explain_from_sem, code_from_explain
    )
    from objectives.losses import success, topo_similarity, length_penalty
except Exception as e:
    errs.append(f"ImportError: {e}")
    SLOTS = VOCAB = None

roundtrip_ok = True
rt_examples = []
if not errs:
    random.seed(7)
    for _ in range(50):
        sem = {k: random.choice(VOCAB[k]) for k in SLOTS}
        e = explain_from_sem(sem)
        c1 = code_from_sem(sem)
        c2 = code_from_explain(e)
        if c1 != c2:
            roundtrip_ok = False
            rt_examples.append((sem, e, c1, c2))
            break

# --- 3) Minimal experiment sanity (100 trials) ---
avg_succ = topo = avg_len = None
if not errs:
    spk, lst = Speaker(), Listener()
    sems, codes, succs = [], [], []
    for _ in range(100):
        tgt = sample_semantics()
        distractor = sample_semantics()
        pred = lst.act(code_from_sem(tgt), [tgt, distractor])
        succs.append(success(pred, 0))
        sems.append(tgt)
        codes.append(code_from_sem(tgt))
    avg_succ = sum(succs)/len(succs)
    topo     = topo_similarity(sems, codes, sem_from_code)
    avg_len  = sum(length_penalty(c) for c in codes)/len(codes)

# --- 4) Run minimal_run.py as subprocess & parse metrics ---
sub_ok = True
sub_metrics = {}
try:
    out = subprocess.check_output(
        [sys.executable, str(ROOT/"experiments"/"minimal_run.py")],
        cwd=str(ROOT), env=dict(os.environ, PYTHONPATH=str(ROOT))
    ).decode("utf-8", errors="ignore")
    m = re.search(r"Success=([0-9.]+)\s+Topo~=([0-9.]+)\s+AvgLen=([0-9.]+)", out)
    if m:
        sub_metrics = {"Success": float(m.group(1)), "Topo~": float(m.group(2)), "AvgLen": float(m.group(3))}
    else:
        sub_ok = False
except subprocess.CalledProcessError as e:
    sub_ok = False

# --- 5) pytest (optional) ---
pytest_ok = None
if shutil.which("pytest"):
    try:
        subprocess.check_call([sys.executable, "-m", "pytest", "tests", "-q"], cwd=str(ROOT), env=dict(os.environ, PYTHONPATH=str(ROOT)))
        pytest_ok = True
    except subprocess.CalledProcessError:
        pytest_ok = False

# --- Assertions / thresholds ---
problems = []
if missing:
    problems.append(f"Missing files: {missing}")
if errs:
    problems.extend(errs)
if not roundtrip_ok:
    problems.append(f"C↔E roundtrip failed on example: {rt_examples[:1]}")
if avg_succ is not None and avg_succ < 0.95:
    problems.append(f"avg_succ too low: {avg_succ:.3f} (expected ≥0.95)")
if topo is not None and not (0.7 <= topo <= 1.01):
    problems.append(f"Topo~ out of range: {topo:.3f} (expected ~0.7–1.0 for MWE)")
if avg_len is not None and not (8 <= avg_len <= 64):
    problems.append(f"AvgLen out of range: {avg_len:.1f} (expected 8–64)")
if not sub_ok:
    problems.append("Subprocess run of minimal_run.py failed or metrics not parsed.")
if pytest_ok is False:
    problems.append("pytest reported failures.")

# --- Report ---
def banner(txt): return f"\n{'='*8} {txt} {'='*8}\n"

print(banner("Repo Check Summary"))
print(f"ROOT: {ROOT}")
print(f"Required files missing: {'None' if not missing else ', '.join(missing)}")
print(f"Imports: {'OK' if not errs else 'FAILED'}")
print(f"C↔E roundtrip: {'OK' if roundtrip_ok else 'FAILED'}")
if avg_succ is not None:
    print(f"Metrics (in-Python): Success={avg_succ:.3f}  Topo~={topo:.3f}  AvgLen={avg_len:.1f}")
print(f"Subprocess minimal_run: {'OK' if sub_ok else 'FAILED'}  {sub_metrics if sub_metrics else ''}")
if pytest_ok is not None:
    print(f"pytest: {'OK' if pytest_ok else 'FAILED'}")

if problems:
    print(banner("FAILURES"))
    for p in problems:
        print("- " + p)
    sys.exit(1)

print(banner("ALL CHECKS PASSED ✅"))
sys.exit(0)
