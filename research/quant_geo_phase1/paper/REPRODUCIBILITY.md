# Reproducibility audit

The completed experiment snapshot is commit
`5e9ffef948d8a7f43b65f3929d077cc594b23a4f`. This audit does not create new
holdout evidence or alter the original experimental results.

## What was checked

1. All 154 geography files in that GitHub tree were matched to their Git blob
   hashes before copying them into a clean snapshot. No raw archive, prepared
   cache or untracked local file was copied. All 58 offline tests passed there.
2. The reusable script below copied 23 computational inputs, each checked
   against a SHA-256 manifest, into a fresh temporary directory. The files
   include the published daily inputs, source, locks and expected outputs.
3. Python socket connections were blocked during both the modelling subprocess
   and the arithmetic verification subprocess. This is a Python-level guard,
   not an operating-system network sandbox.
4. All 13 model pipelines repeated their four-candidate validation selection
   and train-plus-validation refit: 65 additional fits for reproduction.
   All selected parameters and validation scores agreed.
5. All 9,022 model predictions over 694 held-out dates agreed exactly in this
   runtime. The complete prediction CSV was byte-identical. The independent
   verifier rechecked all 104 error metrics and 12 interval summaries.

Results: [reproduction_result.json](reproduction_result.json).
Commands and captured output: [reproduction_log.txt](reproduction_log.txt).
Clean-snapshot tests: [clean_snapshot_tests.txt](clean_snapshot_tests.txt).
Frozen file hashes: [reproduction_inputs.json](reproduction_inputs.json).
GitHub CI is configured to check the manuscript evidence and run the same model
replay after its offline geography tests. Its runtime is separate from the
recorded local audit, so consult the corresponding workflow run for its result.

## Run from the repository

Python 3.11 or newer is required by the experiment's pinned scientific stack.
The observed replay used Python 3.12.14. From `research/quant_geo_phase1`:

```bash
python -m venv .venv
# Activate the environment using your platform's standard command.
python -m pip install -r isone_v1/requirements.txt
python paper/reproduce_isone.py
```

The replay does not change original model outputs. It writes its report and
log under `paper/`. It raises an error for changed pinned input bytes or
prediction differences above 1e-7 MW. Floating-point reproducibility can differ
on another software stack; an error is not silently treated as agreement.

The manuscript table can be regenerated and checked without fitting models:

```bash
python paper/build_evidence.py
python paper/build_evidence.py --check
```

To regenerate the SVG figure, install the additional plotting dependency:

```bash
python -m pip install -r paper/requirements.txt
python paper/build_evidence.py --plot
```

The display uses supplementary NYISO full-calendar intervals together with
pre-specified ISO-NE full-calendar intervals. Original primary intervals remain
available in the experimental directories and are distinguished in the text.

## What this audit does not establish

The replay uses prepared daily inputs. It is not a new download or independent
reconstruction of all raw station observations, nor a third-party review.
Raw-archive recreation follows the original source manifests and may stop when
upstream files have changed. The prior NYISO bridge documented changed 2026
boundary archives while requiring byte-identical daily inputs; that exception
does not authorize silently accepting other raw revisions.

The same-runtime replay says nothing about scientific novelty, deployment,
causality or the statistical reliability of a small high-demand sample. It
confirms that the reported ISO-NE computations can be repeated without the
researcher's untracked data cache. The original empirical search had 65 fits;
these additional 65 verification fits are not additional independent trials.
