# Memory model: code review, accuracy audit, and what it leaves out

Companion to [[20260712-MemoryBitSupplyDemandModel]]. Three parts: what was changed,
what the review found, and the variables the model does not account for — ranked by
how much each one could move the answer.

## 1. Changes made

- **`report/export.py` (new)** — every model output now lands in
  `report/memory_model.sqlite`: 12 tables covering balances, demand segments, supply
  composition + binding constraints, the GPU fleet, the datacentre pipeline, Monte
  Carlo bands, the tornado, vintage viability, the capex cross-check, annual rollups,
  and the full flattened assumption set with sources and confidence tags. SQLite was
  chosen over CSV/parquet because the output is relational (scenario × quarter ×
  product × segment), needs no dependencies (stdlib `sqlite3`), and is directly
  queryable from pandas/DuckDB/Datasette. Verified: exported supply matches the
  actuals series exactly, segment sums reconcile to the balance line to 1e-9, and the
  deficit-invariance property holds in the exported data.
- **Fixed a failing test** — `test_hbm_content_is_consistent_across_the_two_files`
  raised `KeyError: 'hbm_gb'`: the refactor that made `demand_ai.yaml` the single
  source of truth for memory content removed `hbm_gb` from the vintage table but left
  the consistency test reading it. Rewritten as a guard that the duplication never
  returns. 50/50 tests now pass.
- **Fixed a latent Monte Carlo crash** — a tail draw on the efficiency deflator
  (σ=0.35, widened by √horizon) could push the annual rate past 1.0, making
  `(1 - rate) ** 0.25` a **complex number**. Confirmed real: 4 of 100 seeds crash
  pre-fix; the default seed 7 happened not to. Clamped the drawn rate at ≤ 0.95,
  parallel to the existing `realisation_rate` clamp. Same failure class as the
  "negative gigawatts" bug already documented in the README. Default-seed output is
  bit-identical (0 of 400 draws touch the clamp).

## 2. Accuracy review — what holds up

The core machinery is sound. Specifically verified: unit discipline (bits internally,
converters at the boundary, global-scale asserts); quarter arithmetic and the
rescaled S-curve; mid-year anchoring of annual flows; backlog conservation in the
datacentre pipeline (slip ≠ cancellation, excess over the grid ceiling deferred not
destroyed); the linear cohort bleed-out in retirement; the HBM wafer give-back
asymmetry (an HBM ceiling *raising* commodity bits); the ex-China denominator on
`hbm_wafer_share`; the captive-China invariance (holds in the exported data);
assumption deep-copy hygiene; lognormal mean-1 MC multipliers; and the band-collapse
rules over observed quarters. The backcast reproduces the documented 8-of-9 phases,
2025 DRAM lands at 39 EB against the three-way corroborated ~39–42, and 2026 bit
growth (+11.8%) sits inside TrendForce's guided 10–15% (IDC's number is
[16%](https://www.idc.com/resource-center/blog/global-memory-shortage-crisis-market-analysis-and-the-potential-impact-on-the-smartphone-and-pc-markets-in-2026/),
slightly above the model).

## 3. Accuracy review — issues found (reported, not changed)

Ordered by importance. None were silently "fixed" because several are entangled with
calibration — correcting one in isolation would break the tests that were calibrated
around it.

1. **The efficiency deflator erodes demand inside its own base year.**
   `_efficiency_multiplier` compounds from 2025.0, so the multiplier is already 0.97
   in 2025Q1 and **0.88 by 2025Q4** — but 2025 content-per-unit values are supposed to
   BE the 2025 baseline. AI DRAM demand therefore carries a systematic extra ~6–12%
   haircut from the first projected quarter. This was partially absorbed when
   `hbm_gb_per_accelerator` was calibrated up (250→280) against sold-out HBM — i.e.
   the calibration bakes the bug in. If fixed (start compounding at mid-2025),
   recalibrate the HBM content series at the same time or 2026 will double-count.
2. **The NAND picture contradicts observed 2026 reality, and the tests don't catch it
   because the backcast gate is DRAM-only.** The model shows NAND essentially balanced
   in 2026 (−0.8%) and in mild surplus through 2032, while in reality all 2026 NAND
   production is [sold out](https://www.tomshardware.com/pc-components/ssds/phison-ceo-confirms-nand-prices-have-more-than-doubled-and-will-continue-to-rise-all-2026-production-already-sold-out-ssds-facing-pricing-apocalypse-throughout-2027),
   prices have more than doubled, and QLC is booked through the year. The missing
   driver is the nearline-HDD→QLC-eSSD substitution wave (§4). The NAND demand line is
   materially understated; treat the model's NAND output as unreliable until that
   segment exists.
3. **The capex cross-check is now partially circular.** Since the fleet refactor,
   `desired_units = capex/ASP` is one of the three shipment ceilings *and* the
   "independent top-down" comparison. Whenever capex binds (e.g. 2026: bottom-up
   19.9M vs top-down 19.9M — identical by construction), the cross-check verifies
   nothing. It only carries information in power/packaging-bound quarters (2028+,
   divergence 5–11%). The test file half-acknowledges this; worth stating in the
   README before the "reconciled" language gets trusted too much.
4. **CXMT density is arguably double-discounted.** `dram_gb_per_wafer` is documented
   as the *industry blend including CXMT's legacy nodes*, yet CXMT wafers are then
   multiplied by a further 0.62–0.66 discount. The total is right (it's calibrated to
   the 39–42 EB anchor) but the ROW/China *split* is distorted — ROW bits understated,
   which slightly misallocates the captive netting. Cleanest fix: redefine
   `dram_gb_per_wafer` as the ex-China blend.
5. **The fleet's internal state ignores actuals.** Observed accelerator units override
   the demand bits through 2026Q2, but the vintage stock evolves on *modelled*
   shipments (currently ~10% above observed). The retirement/replacement stream —
   the module's whole point — inherits that drift into the out-years.
6. Minor: `build.py` annualises Q4×4 in the capex table rather than summing the year;
   scalar MC inputs are perturbed at a fixed 2029 horizon regardless of quarter;
   README said "53 tests" (there are 50 — fixed).

## 4. Variables the model does not account for

### Tier 1 — could change the headline answer

- **No endogenous supply response (the cobweb).** Out-year wafer capacity is a fixed
  path; a 40% gap in 2029 triggers no extra capex, and a glut would trigger no
  utilisation cut (forward utilisation is pinned at 0.95–0.97, so the 2023-style
  discipline that the backcast *needed* is unavailable to the projection). Memory is
  the textbook cobweb industry: today's 2× price rise is financing capacity for
  2028–29 (the industry is holding [cautious capex in 2026](https://www.trendforce.com/presscenter/news/20251113-12780.html),
  but SK +17%, Samsung +11%, Micron +23% YoY is already a response). The 2029–2032
  gap of 34–43% is therefore best read as "what current roadmaps imply", not "what
  will happen" — the roadmaps themselves will move because the gap exists.
- **No price/elasticity feedback (known, by design).** The `market.py` stub. The
  consequence compounds with the point above: demand never self-corrects, supply never
  responds, so the out-year gap is a pure pressure index. Fine for the stated purpose;
  fatal if ever read as a physical shortfall forecast.
- **The HDD→SSD substitution wave (NAND).** Nearline HDD lead times have blown out to
  [52+ weeks / two years of backorder](https://www.tomshardware.com/pc-components/hdds/ai-triggers-hard-drive-shortage-amidst-dram-squeeze-enterprise-hard-drives-on-backorder-by-2-years-as-hyperscalers-switch-to-qlc-ssds)
  because HDD makers never expanded capacity, forcing CSPs into
  [QLC eSSD substitution at breakout scale](https://www.trendforce.com/presscenter/news/20250915-12714.html).
  This is a *distinct* demand stream from `nand_tb_per_accelerator` (it replaces bulk
  HDD exabytes, not per-accelerator attach) and it is the main reason the model's NAND
  line is wrong. Needs its own segment: HDD exabyte demand × substitution share.
- **Macro / financing cycle.** There is no recession, credit, or rates channel at all.
  The AI buildout is increasingly debt-financed (neocloud leverage, vendor financing
  circularity); a credit event would simultaneously cut capex, the realisation rate,
  and compute prices — the MC correlation cluster gestures at this but a 2008-style
  discontinuity is outside a lognormal band. The model's own capex reconciliation
  (~$1.9tn/yr by 2032) is the flag: if that's unfinanceable, the demand line is the
  thing that breaks.
- **Jevons rebound on the efficiency deflator.** The deflator treats efficiency purely
  as demand destruction, but cheaper intelligence historically *raises* total
  consumption (the KV sub-model's own token growth partly assumes this). Efficiency
  and demand growth are modelled as independent inputs when they are causally coupled
  — the correlation structure has them in the same cluster, which helps, but the sign
  of the coupling (efficiency ↑ → usage ↑) is the opposite of what the deflator alone
  implies.

### Tier 2 — real, partially proxied, worth levers

- **Producers convert capacity between NAND and DRAM.** The model treats the two
  capacity pools as independent, but line conversions (and Samsung's foundry↔DRAM
  flexibility, which is noted) are the industry's fastest supply response and they
  respond to *relative* prices. A DRAM squeeze pulls NAND capacity across, tightening
  NAND — another reason the NAND line runs too loose.
- **Chinese HBM.** The model hard-codes "CXMT makes no HBM" through 2032. CXMT is
  [allocating ~20% of wafers to HBM3 in 2026 and sampling Huawei](https://www.tomshardware.com/pc-components/dram/chinese-semiconductor-industry-gears-up-for-domestic-hbm3-production-by-the-end-of-2026-cxmt-to-produce-chips-while-naura-maxwell-and-u-preseason-design-tools-for-assembly)
  (~7M dies ≈ 600k H100-class chips). Captive to China, so the *global* gap barely
  moves — but it breaks the assumption behind the ex-China HBM share conversion, and
  by 2028+ "no Chinese HBM" is a bet, not a fact. Reports also have CXMT's
  [bonded 3D DRAM closing the gap "far faster than expected"](https://www.zerohedge.com/technology/china-cxmt-testing-production-line-next-gen-bonded-dram-closing-tech-gap-korea-far),
  which argues the density discount should close faster than the assumed path.
- **Sub-tier supply-chain inputs.** Six constraints are modelled; the historical
  shortage triggers were often one tier down: silicon wafer supply (Shin-Etsu/SUMCO
  poly), photoresist, noble gases (neon, 2022), ABF substrate (2021), CMP slurry —
  and for HBM specifically the **HBM4 base logic die** (foundry capacity at TSMC, a
  constraint separate from CoWoS) and **TC bonder capacity** (Hanmi/ASMPT lead
  times). Any of these can bind before C1–C6 do. The `disruption_haircut` lever
  exists but is a blunt instrument.
- **Packaging substitution.** C6 treats TSMC CoWoS as the sole gate on HBM
  consumption; Samsung I-Cube, Amkor, Intel EMIB and panel-level packaging are all
  ramping precisely because CoWoS is scarce. The ceiling is real but softer than
  modelled.
- **Concentration / geopolitical shock.** ~70% of DRAM and ~100% of HBM
  packaging-adjacent capacity sits in two earthquake-prone, geopolitically exposed
  countries (Korea, Taiwan). Export-control escalation exists only as a zeroed stub
  (`china.policy_risk`); tariffs (Section 232), Taiwan-strait risk, and Chinese
  retaliation (gallium/rare earths) have no lever at all. These are fat-tail *supply*
  events in a model whose MC is all lognormal wiggle.
- **The secondary GPU market.** Retired GPUs don't vanish — they cascade to
  neoclouds, inference tiers, and overseas buyers, and their HBM stays in service.
  The model retires bits fully, which flatters replacement demand (its own
  highlighted mechanism). A resale/cascade share on retirements would discipline
  this.
- **Inventory endogeneity.** The swing series is hand-drawn and zeroed from 2028.
  Front-loading is *currently* happening (IDC attributes 1Q26 PC growth to
  pull-forward), and the 2026–27 hoarding will unwind into 2028 exactly the way 2021
  unwound into 2023 — a destock the model cannot produce, which biases the out-year
  gap upward.
- **New demand segments with no line item:** robotics / physical AI, edge-inference
  appliances, smart glasses; sovereign AI programs beyond what's inside the capex
  series; a crypto cycle (historically material for GDDR); high-bandwidth flash (HBF)
  as an HBM-adjacent NAND tier that could shift the offload shares.
- **DDR4 end-of-life dynamics.** The big three exiting DDR4 while embedded/industrial
  buyers still qualify against it creates acute niche shortages and price spikes that
  a blended model can't see (visible only as the shrinking "other" capacity bucket).

### What I'd add first, in order

1. A **NAND HDD-substitution segment** (fixes the one output that contradicts
   observed reality).
2. A crude **supply-response rule**: out-year capacity anchors drift up/down with the
   trailing gap (even a one-parameter elasticity would turn the 2030+ gap from a
   straight line into a cycle, which is what the industry actually produces).
3. A **capacity-conversion coupling** between the DRAM and NAND pools.
4. A **resale share on GPU retirements**.
5. Fix the **deflator base-year erosion** together with an HBM-content recalibration.

## Sources

- [IDC — Global memory shortage crisis, 2026 smartphone/PC impact](https://www.idc.com/resource-center/blog/global-memory-shortage-crisis-market-analysis-and-the-potential-impact-on-the-smartphone-and-pc-markets-in-2026/)
- [TrendForce — Nearline HDD shortages, QLC SSD breakout in 2026](https://www.trendforce.com/presscenter/news/20250915-12714.html)
- [Tom's Hardware — HDD backorders force QLC transition](https://www.tomshardware.com/pc-components/hdds/ai-triggers-hard-drive-shortage-amidst-dram-squeeze-enterprise-hard-drives-on-backorder-by-2-years-as-hyperscalers-switch-to-qlc-ssds)
- [Tom's Hardware — Phison: NAND sold out through 2026, prices doubled](https://www.tomshardware.com/pc-components/ssds/phison-ceo-confirms-nand-prices-have-more-than-doubled-and-will-continue-to-rise-all-2026-production-already-sold-out-ssds-facing-pricing-apocalypse-throughout-2027)
- [TrendForce — Cautious memory capex in 2026, limited bit-supply impact](https://www.trendforce.com/presscenter/news/20251113-12780.html)
- [Tom's Hardware — CXMT HBM3 by end-2026, Huawei sampling](https://www.tomshardware.com/pc-components/dram/chinese-semiconductor-industry-gears-up-for-domestic-hbm3-production-by-the-end-of-2026-cxmt-to-produce-chips-while-naura-maxwell-and-u-preseason-design-tools-for-assembly)
- [ZeroHedge — CXMT bonded 3D DRAM progress](https://www.zerohedge.com/technology/china-cxmt-testing-production-line-next-gen-bonded-dram-closing-tech-gap-korea-far)
- [AI Frontiers — HBM export-control gaps](https://ai-frontiers.org/articles/high-bandwidth-memory-critical-gaps-us-export-controls)
- [Tom's Hardware — Memory price surge cooling at the consumer limit, AI keeps prices climbing](https://www.tomshardware.com/pc-components/ram/memory-price-surge-begins-to-cool-as-consumers-hit-affordability-limit-ai-demand-still-keeps-dram-and-nand-prices-climbing-through-q3-2026)
