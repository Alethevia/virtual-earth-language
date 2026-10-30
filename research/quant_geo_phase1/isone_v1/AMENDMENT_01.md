# Pre-fit amendment 01: SMD daylight-saving format change

The original plan was committed as `0586cc0f25b5029fdce36b744ca6f838d14c513c`.
Its assumption that every SMD year contains 24 published rows per date was based
on the 2019 Notes and proved wrong. The parser stopped on `02X` while preparing
the complete archive. No ISO-NE model had been fitted and no prediction scores
had been inspected. Original plan/protocol/lock files remain unchanged.

The 2019-2023 Notes describe the normalized 24-hour convention. The 2024 and
2025 Notes remove that DST paragraph. Inspection of all eight zone sheets found
23 rows on March 10, 2024 and March 9, 2025, and 25 rows on November 3, 2024
and November 2, 2025. Those autumn dates contain both `02` and `02X`.
The real-time-demand definition removes historical-date wording but retains its
metering scope and inclusion of grossed-up demand response. This audit relies
on the annual files themselves; it does not claim a separately published
explanation of the exact UTC order of `02` versus `02X`.

Before fitting, harmonize the newer years to the already fixed older target
convention: for each zone, interpolate spring HE02 as the mean of HE01 and
HE03; average autumn HE02 and HE02X into HE02. Sum zones within each resulting
hour, then take the daily maximum. This preserves the intended consistent
24-hour-normalized demand target. It is not the unmodified physical-hour peak
on autumn transition dates. Weather remains based on true 23/24/25-hour days.

The parser now validates the exact annual date/hour set for each format,
rejecting missing rows, duplicate rows and an `02X` on the wrong date. Tests
exercise both formats and numerical harmonization. No station, model grid,
split, threshold, metric, coverage requirement or screening condition changes.

`amendment_01.json` records the original and corrected code hashes. The input
lock will include this amendment before model fitting. All subsequent reporting
must read the original plan together with this amendment.
