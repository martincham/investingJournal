# Every variable in the supply projection, and why it sits where it sits

This is the supply half of the model in `memoryProjection/` — DRAM primarily, NAND in
brief — read as an argument rather than as a spreadsheet. Every number below lives in
`assumptions/*.yaml` as `{value, source, confidence, notes}`; this essay sequences those
notes into a story and adds nothing they don't already say. Demand, the six-bottleneck
`min()` logic itself, and the China-netting mechanics are documented elsewhere (`README.md`,
`AGENTS.md`); this file is about the *levels* — what each input is set to, why, and how it
moves from 2026 to 2032.

Two conventions worth knowing before the numbers start. First, an annual anchor like
`{2026: 2260}` is the value at the *middle* of 2026, not 1 January — `model/calendar.py`
interpolates on that basis because these are mostly flow quantities, and anchoring at
1-Jan would pull every series artificially early and damp its amplitude (this exact bug
once halved the 2023 glut in the backcast). Second, past the last anchor the model
extrapolates at the trailing CAGR rather than flat-lining, so a 2032 figure with no
explicit anchor is not a guess pulled from nowhere — it is the stated growth rate,
continued.

## 1. The one equation

Everything below is one term in this chain:

```
wafer_ceiling = min(C1 installed, C2 litho, C3 other WFE)
effective     = wafer_ceiling × utilisation × (1 − conversion_loss) × (1 − disruption)
wafers/qtr    = effective × 1000 × 3                    # kWSPM → wafers, 3 months/qtr
              → split ex-China / China by CXMT's share of installed capacity
hbm_desired   = ex_China_wafers × hbm_wafer_share
hbm_bits      = min(hbm_desired × gb_per_wafer / trade_ratio, C4, C5, C6)
              → wafers HBM did NOT get flow back to commodity (2.85× more bit-efficient)
dram_bits     = commodity_wafers × gb_per_wafer × (3D-DRAM uplift) × (cxmt_discount, China only)
              + hbm_bits
```

Six candidate ceilings, two families. C1–C3 cap total wafer starts; C4–C6 cap HBM bits
specifically, and — this is the asymmetry the model exists to track — when an HBM ceiling
binds, the wafers HBM didn't use flow back to commodity DRAM, which is ~2.85× more
bit-efficient per wafer. An HBM bottleneck therefore *raises* total DRAM bit output while
leaving AI demand unserved. "What binds" has no single answer because total-bit supply
and AI-usable-bit supply are different constraints.

## 2. Pinned vs projected

<!-- var: actuals.actuals_end 2026=2026Q3 -->
**`actuals.actuals_end` = 2026Q3** (2026Q2 in the July vintage). Everything up to and
including this quarter is observed, not modelled. Nov 2026 caveat: 2026Q3 is derived from
Samsung, SK hynix and Micron reports until TrendForce's ranking is out in December — the model still computes it (that's the backcast), but the
reported line is the measured one. Confidence: high, it's a date, not an estimate.

<!-- var: actuals.dram_supply_eb_per_quarter 2026Q1=10.0 2026Q2=10.5 2026Q3=11.1 -->
(Nov 2026: 2026Q2 revised 10.8 → 10.5 EB to match TrendForce's final revenue and its
"only modest" bit growth; 2026Q3 = 11.1 EB from company reports.)
**`actuals.dram_supply_eb_per_quarter`** — not published directly, so it's derived from
two things that are: quarterly DRAM industry revenue and the blended ASP's QoQ change
(`dram_blended_asp_qoq`), giving bits = revenue / ASP, level-anchored to ~39 EB for 2025.
That base year is corroborated three independent ways (wafer capacity × density; $122bn
revenue at ~$2.9/GB; Micron's ~22% bit share against its own disclosed output), so it's
probably right to within ~15%. The load-bearing data point in the series is **2026Q1: 9.0
→ 10.2 → 10.0 EB/qtr** — revenue rose 81% QoQ while bits *fell*, because supplier
inventory was "almost depleted" and nobody could ship more than they made. That is what a
supply wall looks like in the actual data, not in the model.

## 3. The wafer base: five producers, 2018–2032

<!-- var: supply_capacity.dram_wafer_capacity_kwspm.samsung 2026=780 2032=1150 -->
**Samsung**, 720 → 780 → 1,150 kWSPM (1,080 in July; raised for P5, which reaches 600k
wpm of 300mm at full operation in 2029). Confidence: medium — Samsung can shift P-line
capacity between foundry and DRAM, which makes its out-years the widest error bars of the
big three; 2027–28 is P4/P5 Pyeongtaek, and beyond that is the model's assumption, not
guidance.

<!-- var: supply_capacity.dram_wafer_capacity_kwspm.sk_hynix 2026=620 2032=1000 -->
**SK Hynix**, 595 → 620 → 1,000 kWSPM (900 in July; 920 by 2030 haircuts its stated
~1M wpm target, with Yongin Fab 1 tool-in moved up to Feb 2027). Confidence: medium, sourced to a guided ~600k/month
figure for 2H2026. Highest HBM mix of any producer — M15X Cheongju is the near-term add,
the Yongin cluster's first fab is 2027–28.

<!-- var: supply_capacity.dram_wafer_capacity_kwspm.micron 2026=420 2032=800 -->
**Micron**, 385 → 420 → 800 kWSPM (720 in July; FY27 capex ~$55bn, double FY26, mostly
cleanrooms online from late CY28). This is the shape that matters most in the whole wafer
base: Micron adds almost nothing in 2026 (waiting on ID1) and its step-up is a 2027/28
event — Boise ID1 then ID2, Hiroshima, with Clay NY not until 2030+. **The supply line
cannot bend before late 2027 no matter what capex does, because this fab isn't ready
yet.** Confidence: medium.

<!-- var: supply_capacity.dram_wafer_capacity_kwspm.cxmt 2026=350 2032=700 -->
**CXMT**, 265 → 350 → 700 kWSPM. Confidence: medium. Treated as fully captive to Chinese
domestic demand (§9) — it raises global supply and global demand by the same amount and
so cannot close the global gap on its own. No EUV access under export controls forces DUV
multipatterning, hence the density discount in §6.

<!-- var: supply_capacity.dram_wafer_capacity_kwspm.other 2026=72 2032=58 -->
**Other** (Nanya, Winbond, PSMC) — 75 → 72 → 58 kWSPM, slowly shrinking legacy capacity.
Confidence: low, but small enough not to matter much.

Total installed DRAM capacity: **2,245 kWSPM (2026Q3) → 3,459 kWSPM (2032Q3)**, ~7.5%/yr.
CXMT's share of that total rises from 15.8% (2026) to 20.3% (2032), which is why the
ex-China share used in §7 falls from 84.2% to 79.7% over the same period.

## 4. The three haircuts between installed capacity and usable wafers

<!-- var: supply_capacity.utilisation.dram 2026=0.97 2032=0.96 -->
**`utilisation.dram`** — pinned at **0.97 through 2026+**, easing only slightly to 0.96
by 2032. Confidence: medium. This is the single most consequential haircut in the model,
and it comes with a limitation stated plainly: the 2023 trough (0.76) is the deliberate
industry-wide cut that ended the 2022–23 glut, and it is switched off for the entire
projection. **Pinning utilisation at max in the out-years is one of the two reasons the
model cannot produce a glut after 2027** (the other is the inventory swing held at zero
from 2028 — a demand-side mechanism, not documented here). That's a property of the
model's shape, not a forecast that producers will never cut again.

<!-- var: supply_capacity.node_conversion_loss.dram 2026=0.06 2032=0.09 -->
**`node_conversion_loss.dram`** — the shrink tax, 0.06 → 0.09. Migrating a line to a
smaller node costs wafer *starts*: more process steps and litho passes mean longer cycle
time, so the same toolset yields fewer wafer-outs per month. Rises over time because each
successive node adds more steps for less density gained. Confidence: low, calibrated so
2026 net bit growth lands inside TrendForce's guided 10–15% band. This term is routinely
left out of naive supply models, which is exactly why bit growth is always less than
density growth.

<!-- var: supply_capacity.disruption_haircut 2018=0.0 2032=0.0 -->
**`disruption_haircut`** — held at **zero throughout the base case**, deliberately.
Historically the industry loses a few percent of a year's output to a fire, earthquake or
power outage roughly once every 3–4 years (Hsinchu 2021, Xi'an 2021, Kioxia Yokkaichi
2019). Left at zero so the central case isn't quietly assuming an accident; it's a
scenario lever, raised only in Tight (§12).

## 5. The three wafer ceilings — and the handover from C1 to C2

<!-- var: constraints.other_wfe.dram_supportable_kwspm 2026=2750 2032=4500 -->
**C3, `other_wfe.dram_supportable_kwspm`** (2,750 → 4,500 kWSPM) stays slack throughout —
it's set above installed capacity on the assumption that non-litho tools (Lam, TEL, AMAT)
have generally been orderable ahead of cleanroom availability. Confidence: low; if wrong,
it's wrong in the direction of the model being too optimistic on supply.

**C1** (installed capacity, §3) and **C2** (litho, below) are the two that actually
compete. Querying the model's own output rather than guessing: C1 binds every quarter from
2018 through 2029; **C2 takes over at 2030Q4**, and the margin between them — how much
slack sits behind whichever one binds — collapses from **22.3% (2028Q4) to 12.7% (2029Q4)
to 1.0% at the exact handover (2030Q4)**, before recovering to 7.8% (2031Q4) and 15.0%
(2032Q4) as the EUV fleet catches up. A margin that thin means relieving C1 in 2030 would
have exposed C2 almost immediately — the two ceilings are converging, not one dominating.

The four litho sub-variables that decide whether "ASML is the bottleneck" is actually
true, rather than assumed:

<!-- var: constraints.litho.euv_scanners_available_to_memory 2026=70 2032=255 -->
**`euv_scanners_available_to_memory`** — cumulative EUV fleet in memory's hands, 70 → 255
scanners (58 → 152 in July). Confidence: low. Nov 2026: memory was ~46% of ASML's 3Q26
system sales and ~65 low-NA tools shipped in 2026, so memory's adds are ~25–33/yr, not
~14.

<!-- var: constraints.litho.wafer_layers_per_scanner_month 2026=104000 2032=104000 -->
**`wafer_layers_per_scanner_month`** — a scalar, 104,000, derived from ~160 wafers/hour ×
24h × 30d × 90% uptime. Confidence: medium.

<!-- var: constraints.litho.euv_layers_per_dram_wafer 2026=4 2032=8 -->
**`euv_layers_per_dram_wafer`** — 4 → 8 layers (2 → 6 in July; 1b runs ~4 EUV layers and
1c 5–6, so July was low by about the same factor as the scanner count, and the two were
raised together). This is the term that decides whether C2
ever binds at all: the scanner fleet grows roughly linearly while layers-per-wafer also
grows, so the ceiling can flatten even as scanners keep arriving. Confidence: low.

<!-- var: constraints.litho.euv_dependent_share_of_dram_wafers 2026=0.50 2032=0.87 -->
**`euv_dependent_share_of_dram_wafers`** — 0.50 → 0.87, and this is the correction that
makes C2 arithmetic honest rather than alarmist: **most DRAM wafers never touch an EUV
scanner at all.** DRAM only started using EUV around 2020, and legacy nodes, DDR4, niche
DRAM and every CXMT wafer are still pure DUV multipatterning. Only this fraction of wafers
is exposed to the EUV ceiling; the rest is capped by cleanroom and etch, not by ASML. Set
to exactly 0 before 2020, which is why the backcast must not show litho binding in
2018–19. Confidence: low, but it's the parameter that turns "is ASML the limiting factor"
from an assumed narrative into an arithmetic answer — and the answer is: not yet, but
increasingly so, and not until 2030.

## 6. Density: the trend that is the whole supply story

<!-- var: tech_roadmap.dram_gb_per_wafer 2026=2260 2032=3960 -->
**November 2026 revision — this paragraph's July thesis was reversed.** The path is now
2,260 (2026) → 2,620 (2027, +16%) → 3,960 (2032), about +8–11%/yr after 2027, against
July's ~5%/yr. Three independent statements only fit together at ~+16% density in 2027:
Micron's industry bit shipments "low-20s %" in CY27 and CY28, the SK hynix CEO's 2027
wafers +12% with ex-HBM bits +15%, and supplier HBM volumes summing to ~7 EB in 2027.
With the HBM wafer share rising 0.261 → 0.339, July's +5.5% gave total bits +14% and
ex-HBM bits roughly flat. The 1b → 1c migration (SK hynix 1c ~35% of output by 1Q27),
1d in 2027–28 and Samsung's 4F² from 2028 carry it. The July reasoning follows, kept as
the earlier view.

**July view: `dram_gb_per_wafer`** — 2,140 (2025) → 2,260 (2026) → 3,135 (2032), blended across the
whole industry mix (DDR5, DDR4, LPDDR, GDDR, CXMT's older nodes), not leading-edge-only.
The implied annual growth rate is the real story: **~11%/yr (2018–22) → ~10%/yr (2022–25)
→ ~5%/yr (2025–29) → ~6%/yr (2029–32)**. Planar DRAM's capacitor aspect ratio is running
out of room, which is why growth roughly halves mid-decade; the partial recovery after
2029 is 3D DRAM (below) starting to add back. Confidence: medium — derived, not quoted,
calibrated to reproduce ~42 EB of 2025 output and cross-checked against a 16Gb DDR5 die
density estimate. **This is the highest-ranked sensitivity in the tornado (#1 of 14
sliders)**: moving it ±(15–20)% swings the 2029 gap from 15.2% to 91.9%, wider than any
other lever in the model. The thesis sentence: DRAM planar scaling is close to dead, so
supply growth now depends on pouring concrete rather than on shrinking — and concrete
takes 3–4 years.

<!-- var: tech_roadmap.three_d_dram.first_volume_year 2026=2030 2032=2030 -->
<!-- var: tech_roadmap.three_d_dram.density_uplift 2026=0.35 2032=0.35 -->
**`three_d_dram.first_volume_year` (2030) and `.density_uplift` (0.35)** — the regime
break. 3D DRAM (4F2 + vertical channel transistor) would restore the density scaling
planar DRAM has run out of; consensus puts meaningful volume at 2030+, with 0.35 cumulative
extra bits/wafer once ramped over ~4 years (`s_curve`, §11). Confidence: speculative on
both — this is a genuine switch, not a tweak: pulled to 2028 the out-years change
character, pushed to 2032 they don't. Exposed as a slider precisely because nobody knows.

<!-- var: tech_roadmap.cxmt_density_discount 2026=0.66 2032=0.82 -->
**`cxmt_density_discount`** — 0.66 → 0.82, i.e. CXMT wafers yield 66–82% of the industry
average bits/wafer. DUV multipatterning without EUV costs steps, yield and die area, so
CXMT's ~16–20% of global wafer capacity translates into materially fewer bits than that
share implies. Confidence: low.

## 7. The HBM tax: allocation share and wafer cost, multiplying together

<!-- var: tech_roadmap.hbm_wafer_share 2026=0.261 2032=0.528 -->
**`hbm_wafer_share`** — **0.261 (2026) → 0.528 (2032)**, i.e. by 2032 the big three put
*more than half* their wafers into HBM. Note the denominator: this is a share of
**ex-China** wafer starts specifically, because CXMT makes no meaningful HBM (no EUV, no
advanced packaging, no customers) — applying the sourced global figures to the total pool
would make a CXMT ramp appear to make Samsung/SK/Micron "produce more HBM," which a test
in this repo exists to catch. The sourced figures are global (~19% of all wafers in 2025 →
~22–23% in 2026) and converted here by dividing by the ex-China capacity share (0.22 /
0.844 = 0.261 for 2026). Confidence: medium; beyond 2026 the trajectory is the model's
assumption, and it's the **#2 tornado sensitivity**. This is a producer *allocation
decision*, not a physical constraint — HBM has been the most profitable use of a wafer, so
it can reverse in a quarter if that stops being true.

<!-- var: tech_roadmap.hbm_trade_ratio 2026=2.85 2032=3.15 -->
**`hbm_trade_ratio`** — **2.85 (2026) → 2.9 (2027) → 3.15 (2032)** (July: 3.05 in 2027,
3.3 by 2032; TrendForce's own 2027 wafer and bit shares solve to ~2.87, 8-Hi stacks
improve yield, and hybrid bonding slipped to HBM4E/HBM5): the wafer capacity one HBM bit costs
versus one commodity DDR5 bit. This is the single highest-leverage number in the model,
derived from two independent sourced ratios rather than guessed — HBM takes ~22% of wafer
input but yields only ~9% of bits in 2026; solving that pair gives k=2.85, and a separate
source independently states one HBM wafer displaces ~three conventional wafers. Two
methods agreeing is the reason confidence is medium rather than low. It rises after 2026
because HBM4's 16-hi stacks and logic base die compound known-good-die losses and add
area — a worse deal in wafer terms than HBM3E. **If this ratio keeps climbing, the squeeze
is self-reinforcing: every incremental unit of AI demand destroys more commodity supply
than the last one did.** At a 26% wafer allocation and this trade ratio, those wafers cost
roughly *half* the commodity bits they'd otherwise have made.

Together, `hbm_wafer_share` and `hbm_trade_ratio` are the entire transmission belt from AI
demand to consumer DRAM shortage: one decides how many wafers go to HBM, the other decides
how many commodity bits each of those wafers didn't make.

## 8. The three HBM ceilings — real, but never the thing that binds

<!-- var: constraints.hbm_backend.max_hbm_bits_eb_per_year 2026=5.2 2032=27.0 -->
**C4, `hbm_backend.max_hbm_bits_eb_per_year`** — 5.2 → 27.0 EB/yr (TSV, thinning,
bonding, known-good-die screening). Confidence: low, set slightly above the
wafer-implied HBM output on purpose — back-end tooling has shorter lead times than a fab
shell, so producers have been able to chase it. The cheapest bottleneck to relieve, which
cuts against any thesis that treats the HBM shortage as structural on the back-end side.

<!-- var: constraints.test.max_hbm_bits_eb_per_year 2026=5.0 2032=25.0 -->
**C5, `test.max_hbm_bits_eb_per_year`** — 5.0 → 25.0 EB/yr. HBM test time runs 3–5× a
commodity DRAM bit, and 16-hi HBM4 makes it worse. Confidence: low, but flagged as an
underrated gate — tester capacity (Advantest/Teradyne) is a real, purchasable thing the
industry has repeatedly under-ordered.

<!-- var: constraints.advanced_packaging.cowos_wafers_kwpm 2026=110 2032=360 -->
<!-- var: constraints.advanced_packaging.accelerators_per_cowos_wafer 2026=24 2032=15 -->
**C6, `advanced_packaging.cowos_wafers_kwpm`** (110 → 360 kwpm of TSMC CoWoS; 330 in July,
raised from 2028 as TSMC reportedly doubles CoWoS to ~260k by end-2028) and
**`.accelerators_per_cowos_wafer`** (24 → 15, falling because packages keep getting
physically bigger). Gates how much HBM can be *consumed* — a stack with no interposer to
sit on is inventory, not supply. Combined with the seam variable below, this converts
into a bits ceiling. Confidence: low on both; CoWoS is the most-watched number in the AI
supply chain.

<!-- var: demand_ai.hbm_gb_per_accelerator 2026=280 2032=760 -->
**The seam: `demand_ai.hbm_gb_per_accelerator`** (280 → 760 GB/accelerator; 880 in July,
flattened after Rubin Ultra moved from the 1TB four-die design to ~384GB) belongs to the
demand model but enters supply arithmetic directly — it's what converts CoWoS wafer
throughput into an HBM *bits* ceiling (accelerators/wafer × GB/accelerator). Confidence:
medium.

Nov 2026: C5 (test) now binds in 2032Q2–Q4 of the central case, the first HBM ceiling to
bind anywhere, because the faster node cadence lifts desired HBM output into it. July
view: none of C4, C5 or C6 ever actually binds: **`hbm_is_capped` is false in every
quarter checked (2026, 2029, 2032) across every scenario.** In 2026, desired HBM output is ~1.12
EB/quarter against ceilings of 1.31–2.35 EB/quarter (test is tightest, still ~17% of
headroom above); by 2032 desired output of ~4.0 EB/quarter sits comfortably under a
6.4–13.4 EB/quarter range. The model keeps these three ceilings in even though they never
bind, because HBM supply is genuinely allocation-constrained (§7), not back-end-constrained
— and the only way to know that is to check, not assume.

## 9. China as a captive region

<!-- var: china.captive_share 2026=1.0 2032=1.0 -->
**`captive_share` = 1.0**, held constant. Confidence: medium. The model's structural
claim: because CXMT and YMTC output is (by assumption) fully absorbed by Chinese domestic
demand, exporting west would be *reallocation* — the Chinese buyer who lost the bit
imports a replacement from Samsung/SK/Micron, so supply and demand in the merchant pool
move by the same amount and the global deficit is unchanged. Formally, for captive
fraction c: global deficit = D−S regardless of c; only the *ratio* (a scope artefact, not a
physical effect) moves. What this does **not** mean: a CXMT ramp can't close the global
gap — it can, because more capacity means more bits physically exist. What it can't do is
add bits to what non-Chinese producers ship.

<!-- var: china.policy_risk.export_control_tightening 2026=0.0 2032=0.0 -->
**`policy_risk.export_control_tightening` = 0.0**, left at zero rather than guessed.
Confidence: speculative. Cuts both ways: tighter controls on DUV/parts would impair
CXMT's ramp (raising the ex-China gap indirectly, via higher Chinese import demand);
looser controls would accelerate it. A scenario lever, not a base-case assumption.

## 10. NAND, briefly — a different physics, so a different story

NAND gets one section because it doesn't have DRAM's bottleneck story. Five producers
scale wafer capacity 1,560 → 2,245 kWSPM (2026→2032):

<!-- var: supply_capacity.nand_wafer_capacity_kwspm.samsung 2026=480 2032=650 -->
<!-- var: supply_capacity.nand_wafer_capacity_kwspm.sk_hynix_solidigm 2026=345 2032=490 -->
<!-- var: supply_capacity.nand_wafer_capacity_kwspm.kioxia_sandisk 2026=405 2032=560 -->
<!-- var: supply_capacity.nand_wafer_capacity_kwspm.micron 2026=195 2032=275 -->
<!-- var: supply_capacity.nand_wafer_capacity_kwspm.ymtc 2026=200 2032=450 -->
Samsung (480→650), SK Hynix/Solidigm (345→490), Kioxia/SanDisk (405→560, Kitakami K2 the
main add), Micron (195→275), YMTC (200→450, also treated as captive-China; 155→270 in July, raised because YMTC already
runs ~200k wpm with ~13–14% of NAND bits). All
confidence: low — this granularity isn't separately reported the way DRAM's is.

<!-- var: supply_capacity.utilisation.nand 2026=0.96 2032=0.95 -->
<!-- var: supply_capacity.node_conversion_loss.nand 2025=0.03 2032=0.05 -->
`utilisation.nand` (0.96→0.95) and `node_conversion_loss.nand` (0.03 [2025] → 0.05 [2032])
mirror DRAM's haircuts, both confidence low.

<!-- var: constraints.other_wfe.nand_supportable_kwspm 2026=1800 2032=2400 -->
`other_wfe.nand_supportable_kwspm` (1,800→2,400) is NAND's one real WFE constraint —
unlike DRAM, where non-litho tooling is generally slack, 1,000-layer stacking is
genuinely an etch problem, not a litho one. Confidence: low.

<!-- var: tech_roadmap.nand_tb_per_wafer 2026=93 2032=183 -->
**`nand_tb_per_wafer`** — 93 → 183 TB/wafer, ~12%/yr sustained via layer count (2xx → 3xx
→ 4xx → 1000) plus string stacking plus QLC/PLC. Confidence: low, calibrated to ~1,450 EB
of 2025 output. **The asymmetry that matters: unlike DRAM's density growth, this rate is
NOT decaying** — vertical scaling still works where planar scaling has stalled. That's
why NAND supply has no analogue to DRAM's C1→C2 squeeze, and why the two lines must never
be summed: NAND ships ~25× more bytes, and would drown the DRAM story in any aggregate.

## 11. Conventions that behave like variables

Four modelling choices aren't YAML leaves but move the answer as much as some of the
sourced numbers above:

- **Mid-year anchoring** (`interpolate_annual`) — an annual anchor is the value at the
  year's midpoint, not 1 January. Getting this wrong once quietly halved the amplitude of
  the inventory swings that drive the memory cycle and made the backcast show 2019 and
  2023 as shortages instead of the historic gluts they were.
- **Trailing-CAGR extrapolation** — past the last explicit anchor (e.g. `hbm_trade_ratio`
  has no anchor after 2032, but several series stop earlier), the model continues the
  most recent compound growth rate rather than flat-lining, which would understate
  out-year supply.
- **S-curve fab ramps** (`s_curve`, 16-quarter default) — a fab goes shell → tool-in →
  qualification → volume over ~12–16 quarters on a logistic curve, not a step function.
  This is what spreads Micron's 2027/28 step-up (§3) and the 3D DRAM uplift (§6) across
  several years of output rather than a single quarter's cliff.
- **The ex-China HBM denominator** (§7) — `hbm_wafer_share` is defined over ex-China
  wafers specifically. Applying it to the global pool instead is the single most
  seductive-looking bug in this model, because it produces a plausible-looking number
  that is wrong in a specific, testable direction.

## 12. How wrong could this be

The supply-side entries in the Monte Carlo (`uncertainty.sigma_2027`, 1-year-horizon
1-sigma spread, widened by √horizon):

<!-- var: uncertainty.sigma_2027.tech_roadmap.dram_gb_per_wafer 2027=0.04 -->
`dram_gb_per_wafer`: **0.04** — tight near-term (roadmaps are public, nodes already in
qualification) but compounding to ~10% at a 6-year horizon, which is why it dominates the
band despite the small starting sigma and is the model's #1 sensitivity (§6).

`hbm_trade_ratio`: 0.06 — anchored by two sourced ratios for 2026, but the HBM4 trajectory
beyond that isn't. `hbm_wafer_share`: 0.08 — a producer allocation decision, genuinely
uncertain. Samsung/SK Hynix/Micron wafer capacity: 0.05 each — medium confidence, these
are announced years ahead. **CXMT wafer capacity: 0.15** — the widest supply-side sigma,
because nobody outside CXMT knows its real yield.

<!-- var: uncertainty.correlation.supply_cluster 2027=0.45 -->
**`correlation.supply_cluster` = 0.45** — the big three invest and shrink in lockstep, and
that correlated behaviour *is* the memory cycle; drawing wafer capacity and density
independently across 400 Monte Carlo draws would understate the tails badly.

The tornado ranks all 14 sliders by their swing in the 2029 gap; the top four are all
supply-side: **#1 DRAM density** (gap swings 15.2%↔91.9%), **#2 HBM wafer share**
(32.0%↔58.3%), **#3 CXMT capacity** (52.0%↔36.8%), **#4 HBM trade-ratio** (36.5%↔48.8%),
against a 43.9% baseline. Every one of the top four supply levers is documented above.

Scenario overrides that touch supply specifically — Tight tightens `hbm_trade_ratio`
(×1.12), `dram_gb_per_wafer` (×0.95), pushes `three_d_dram.first_volume_year` to 2033, and
turns on `disruption_haircut` (0→0.03 from 2028); Loose does the reverse plus a +10%
capacity bump across Samsung/SK/Micron. Both are read from the same YAML paths documented
in the sections above — nothing scenario-specific is a new variable.

## 13. Where it lands, and what the model structurally cannot show

DRAM supply: **39.0 EB (2025) → 43.6 EB (2026) → 82.97 EB (2032)**, ~11–12%/yr compound.
HBM's share of that output: **3.03 EB (2025, 7.8% of DRAM) → 15.81 EB (2032, 19.0% of
DRAM)**. NAND: **1,462 EB (2025) → 4,455 EB (2032)**, ~17%/yr, no bottleneck story to tell.
The binding wafer constraint is C1 (installed capacity) for the entire backcast and out to
2029, handing off to C2 (lithography) from 2030 with the margin between them falling to
~1% at the moment of handover (§5) — the closest this model's supply side comes to a
cliff.

Three things worth restating from `README.md`'s limitations, because they are properties
of *this file's* variables specifically: utilisation is pinned near-max from 2026 (§4),
the disruption haircut is zero by default (§4), and there is no endogenous mechanism by
which a 40% demand gap causes any wafer-capacity number in §3 to move — the out-year
capacity path is the model's assumption, not a response to the shortage the model itself
projects. Change the roadmap, and you're disagreeing with a number in this file; the
model has no mechanism that would do it for you.
