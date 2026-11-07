# Micron projection vintage 2026-11

| | |
|---|---|
| Source commit | `39df9d5` |
| Upstream memory vintage | `memoryProjection/vintages/2026-11` (sqlite sha256 `7ca3ee8d…`) |
| Observed data through | 2026Q3 (Micron FQ4 FY26, 10-K filed 2026-10-09) |
| Guided | 2026Q4 (FQ1 FY27: $61.5bn, GAAP gross margin 85.95%) |
| Price after the guide | upstream `market` path, indexed to the guided price (`asp.price_source: market`) |
| Built | 2026-11-07 |

The November 2026 Micron projection. Central FY27 $260bn revenue / $159.96 GAAP EPS,
FY28 $304bn / $189. `fy_summary.csv` holds every scenario by fiscal year;
`assumptions/` is a copy of the inputs.

What changed from 2026-07: the memory vintage (actuals through 2026Q3, restated
tightness, a price layer), FQ4'26 reported instead of guided, the price engine (upstream's
industry path instead of the fitted response, which is kept as a cross-check), and FY27
opex, capex, D&A, tax and capital return re-set from Micron's outlook.

Frozen output. Do not edit or re-run.
