# Micron projection: November 2026 revision

November 7th, 2026. Follows [[20261001-MicronFQ4-26ResultsAndFY27Projection]] and is built on the November memory projection ([[20261107-MemoryMarketTrendsNovember]]). Model: `micronProjection`, frozen as `vintages/2026-11` (commit `39df9d5`). Report: `micronProjection/report/micron_model.html`.

## What changed since July

- **Memory vintage 2026-11.** Actual data now runs through 2026Q3. Upstream also restated its history: 2026Q2 tightness went from +0.20 to +0.31, and 2026Q3 is +0.37, the tightest quarter on record. Central tightness then stays around +0.30 to +0.37 instead of climbing to +0.50.
- **FQ4'26 is reported.** It came in at $54.2B against a $50B guide and a $51B model assumption. FY26 is now fully reported: $133.2B revenue, $74.24 GAAP EPS.
- **FQ1'27 is the one guided quarter.** Revenue ($61.5B, the guide midpoint), GAAP gross margin (85.95%), opex ($2.31B) and tax (15.5%) are pinned to the guide. Everything else is modelled. The model's EPS of $37.67 lands inside the $37.84 ± $1.00 guide, which checks the parts that aren't pinned.
- **New price engine.** After FQ1'27, Micron's price moves with upstream's new industry DRAM price path. That path is in real 2025 dollars, so it's converted to nominal at 2.5% a year. The floor is Micron's own lowest markup over cash cost, 1.17x in 2023Q1. The old price model was fitted to Micron's history; it was refit (n=35, R² 0.64) and is now only a cross-check.
- **FY27 inputs from Micron's outlook.** Opex rises $2.5B. Capex is about $55B net (FQ1 $11.5B, H1 $25B). D&A rises with capex (FY27 about $11.5B). Buybacks start after Dec 9.

## Results (GAAP)

| Scenario | FY27 revenue | FY27 GM | FY27 EPS | FY28 revenue | FY28 EPS | FY30 EPS |
|---|---|---|---|---|---|---|
| Tight | $288B | 86.9% | $180 | $346B | $221 | $309 |
| **Central** | **$260B** | **85.7%** | **$160** | **$304B** | **$189** | **$359** |
| Loose | $155B | 76.6% | $82 | $57B | $3 | −$21 |

- **Central FY27 is close to the earlier views.** It matches the October note's floor case ($264B / $164) and sits just above the Oct 1 consensus ($250.5B / $161). It's 9% above July's $239B. The October note was non-GAAP, which runs about $1.25 higher.
- **Loose is a glut, not a forecast.** Upstream's loose supply runs ahead of demand straight after the observed data, and nothing in either model cuts supply to end it. It bottoms at Micron's 2023 trough margin (about −32%).
- **Tight is below central in FY29–31.** Upstream caps the industry price at what cloud providers' budgets can pay, so in tight, scarcity stops raising price before it stops cutting Micron's bits.

## Where central disagrees with Micron

These are checks, not adjustments.

- **Revenue doesn't grow every quarter.** Central goes $61.5B → $68.2B → $65.1B → $65.6B, while Micron guided sequential growth each quarter. The dip comes from upstream's industry price falling about 5% in 2027Q2.
- **FQ1 isn't the margin floor.** Central's margin goes 85.95% → 86.7% → 85.4% → 84.8%, while Micron called FQ1 the FY27 floor. D&A rises about $0.45B over the year with the doubled capex, while price eases.

Both disagreements point the same way: if Micron is right, central FY27 is low. With its beat record (+24% in FQ3'26 and +8.5% in FQ4'26 against the guide midpoint), $260B looks like a floor rather than a midpoint.

## The big judgement call

The out-years depend mostly on which price engine is used, not on the bits.

- **Using the old fitted price model on the November bits *lowers* the projection.** FY30 comes out at $289B, against July's $320B. That's because tightness levels off, and the fitted model pulls Micron's markup down from the guided ~11x toward ~7–8x.
- **Upstream's price path raises FY30 to $520B.** The industry price keeps rising into 2029 while Micron's cost falls about 5% a year, so the markup holds at 11–14x.

Upstream says its price is a *path*, not a clearing price: at an elasticity of −0.1, the level can't be pinned down from the bit numbers. So FY29 and later are the weakest numbers in the model.

## Known gaps

- **NAND bits.** The model has NAND production up 5.4% in FQ4'26, against reported shipments up about 10%. The revenue split still matches: NAND is 26% in both.
- **D&A** is an assumed series, not built up from the capex schedule. That matters from FY28 on.
- **The SCA price bands** (floors and ceilings on about 15–25% of revenue) aren't modelled. They'd mainly trim the upside in the tight scenario.

## What to watch

- **FQ1'27 results, mid-December.** This is the first out-of-sample test. Watch for a beat against $61.5B, and whether the GAAP margin is above 85.95%.
- **FQ2'27 guide.** It tests the dip that central shows in FQ3'27.
- **The size of the buyback program announced after Dec 9.**
- **TrendForce's final Q3 DRAM numbers in December.** Upstream's 2026Q3 is estimated from company reports for now.
