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

The [2024 error decomposition](research/quant_geo_phase1/DIAGNOSTICS_2024.md) is descriptive follow-up. A [locked 2025 replication attempt](research/quant_geo_phase1/replication_2025/STATUS.md) stopped before fitting: the legacy NOAA product ends in August 2025, leaving only 64.93% usable days against the unchanged 90% requirement. It supplies no additional model-performance evidence.

## Optional globe viewer

```bash
cd web
npm ci
npm run build
npm run dev
```

Cesium assets are generated from the locked npm dependency during installation/build. Generated third-party asset copies are no longer tracked. The viewer is a visualization shell with sample GeoJSON, not a validated geospatial analysis system. See [AUDIT.md](AUDIT.md).
