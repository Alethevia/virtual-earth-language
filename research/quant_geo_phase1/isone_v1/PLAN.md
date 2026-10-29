# ISO-NE geographic replication, version 1

This plan follows the NYISO results and is informed by them. It is frozen before
any ISO-NE model fitting or performance comparisons. It is a repository timestamp,
not an independent preregistration. ISO-NE was selected for public annual zonal
archives and documented station mapping, without comparing model performance
across candidate regions. Feasibility inspection read the 2019 schema and Notes.

## Question and fixed design

Does retaining weather-station identity improve held-out high-demand prediction
beyond calendar/history, aggregated weather, and weather-distribution features?
The target is the maximum of the simultaneous sum of eight zonal `RT_Demand`
columns in each supplied SMD date, in MW. It is wholesale settlement demand,
not the separate `System_Load` series and not exactly the NYISO target definition.
The official SMD archive normalizes DST dates to 24 observations: March HE02 is
interpolated and the two November HE02 values are averaged. We retain that
published convention and never treat its synthetic hours as 24 physical hours.
Daily weather is computed from actual UTC observations in America/New_York with
the original 90% physical-hour coverage requirement (23/24/25 hours).

Seven unique stations follow the official SMD Notes: PWM-ME, CON-NH, BTV-VT,
BDL-CT, PVD-RI/SEMA, ORH-WCMA, BOS-NEMA. This changes the NYISO station count
from five to seven. The mapping is representative, not full spatial coverage.
GHCNh temperature and dew point use the previously audited parser and QC rules,
including exclusion of source 999. Other unknown finite-value sources halt.
2019-2026 weather files are needed; 2026 is used only before January 1 05:00 UTC.
All official downloads receive hashes. Historical archive revisions are possible.

- Train: 2019-2022. Select each pipeline on 2023 all-day MAE and refit 2019-2023.
- Primary held-out endpoint: 2025. Secondary endpoint: 2024, always reported.
- No 2024/2025 fitting, candidate selection, station selection, or threshold tuning.
- Original B0-B3 features, HGB/Ridge grids (four candidates each), and five HGB
  identity scrambles (17, 29, 43, 61, 79). Thirteen pipelines, 65 fits total.
- Threshold: 90th percentile of all available 2019-2022 target days, before
  weather exclusions. Exposure weights use only 2019-2022 zonal demand.
- Require at least 90% usable days in training, validation, and EACH test year.
  If this fails, publish the failure; do not remove stations or relax coverage.
- Primary comparison: HGB B3 minus B2 high-load MAE, reported as B2 minus B3
  paired improvement (positive is favorable) and relative improvement.
- Circular calendar-block bootstrap, 2,000 draws, seed 20261028. Full calendar
  January 1-December 31, 14 days primary, 7/28 days sensitivity. Missing and
  non-high-load dates remain NaN. No pooled two-year test or best-block selection.
- Original six screening conditions: at least 30 tail days, at least 5% relative
  gain, positive lower 95% primary interval, Ridge tail direction agrees,
  beats at least four of five scrambles, all-day MAE no more than 2% worse.
  Only the 2025 screen is primary. Failure or uncertainty remains reportable.

Code and protocol are hashed before downloading the full dataset. Prepared-input
hashes and coverage will be committed before fitting. Schema/parser defects, if
found, must be documented and corrected before fitting, without viewing model
performance. Publish all 13 predictions, selection parameters, both years'
metrics, intervals, excluded dates and an independent metric recomputation.

## Interpretation limits

This tests a method retrained in another region, not transfer of NYISO-trained
coefficients. Nearby regions share weather and economic shocks, so geographic
holdout does not imply statistical independence. Additional identity features
also increase dimension; scrambles are diagnostics, not causal randomization.
Same-day realized weather supports conditional prediction, not a deployable
day-ahead forecast. Archive revisions preclude point-in-time market claims.
No claim of causality, novelty, profitability, or publication readiness follows
from passing the analyst-defined screen.

## Sources

- [ISO-NE zonal reports](https://www.iso-ne.com/isoexpress/web/reports/load-and-demand/-/tree/zone-info)
- [2019 SMD workbook and Notes](https://www.iso-ne.com/static-assets/documents/2019/02/2019_smd_hourly.xlsx)
- [GHCNh documentation](https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh_DOCUMENTATION.pdf)
- Exact annual URLs, NOAA identifiers and coordinate records: `protocol.json`.
