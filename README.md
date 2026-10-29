# Virtual Earth — communication experiments and geography research

This repository contains two distinct research directions. Neither is presented as a proven scientific breakthrough.

## 1. Structured communication sandbox

The minimal example uses a predefined slot vocabulary and deterministic encoder/decoder. High success on that example checks an engineered mapping; it does not demonstrate independently emergent human-readable language. Earlier benchmark percentages and “revolutionary results” tables have been withdrawn because no reproducible comparative evidence was provided.

```bash
python -m pip install -r requirements.txt
python experiments/minimal_run.py
python -m pytest tests -q
```

Larger neural experiments have additional dependencies in `requirements-research.txt` and remain separate, incompletely validated research paths. The minimal `Topo~` diagnostic is an equality check, not a standard topographic-similarity correlation.

## 2. Weather geography and electricity load

The new [quantitative geography project](research/quant_geo_phase1/README.md) asks whether weather station identity adds conditional predictive information beyond aggregate weather and nonlinear distribution features. It includes the original locked protocol, code and offline tests.

```bash
cd research/quant_geo_phase1
python -m pip install -r requirements.txt
python -m unittest -v
```

**The first real-data screen did not support the proposed high-load benefit.** On the 2024 test set, adding station identity increased HGB high-load MAE by 10.07%, despite improving overall MAE. All 13 model/control results and uncertainty intervals are retained in [RESULTS.md](research/quant_geo_phase1/RESULTS.md). Hour-label alignment was numerically cross-checked against official five-minute data; a direct written timing definition remains unverified. Same-day observed weather does not constitute a day-ahead forecast.

The [2024 error decomposition](research/quant_geo_phase1/DIAGNOSTICS_2024.md) is descriptive follow-up. The legacy-data [2025 attempt](research/quant_geo_phase1/replication_2025/STATUS.md) stopped for inadequate coverage. A separate [GHCNh data-version experiment](research/quant_geo_phase1/ghcnh_v1/RESULTS.md) now covers 338 test days: HGB high-load MAE improves 6.35%, but its primary 95% interval includes zero, so the full screen still fails. All 13 pipelines are reported; this is not a stable-advantage or novelty claim.

## Optional globe viewer

```bash
cd web
npm ci
npm run build
npm run dev
```

Cesium assets are generated from the locked npm dependency during installation/build. Generated third-party asset copies are no longer tracked. The viewer is a visualization shell with sample GeoJSON, not a validated geospatial analysis system. See [AUDIT.md](AUDIT.md).
