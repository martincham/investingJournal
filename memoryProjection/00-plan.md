# Global Memory Bit Supply & Demand Model — 2026Q1 to 2032Q4

## Context

`memoryProjection/` is empty. This builds a quantitative model of two lines — **global memory bit demand** and **global memory bit supply** — at **quarterly** resolution from 2026Q1 through 2032Q4.

Per your decisions: **DRAM and NAND both modeled** (separate line pairs — never summed), base year built **bottom-up from public sources only**, delivered as a **Python core + interactive HTML**, and **no price/ASP or financials layer** — the two physical lines and the gap between them, nothing more.

This is a model, not an argument. It takes no position and makes no case; it produces the lines and reports what the inputs imply.

**Step 1 of execution is writing this plan to `memoryProjection/00-plan.md`** so it lives in the repo alongside the model.

---

## 0. Defining the demand line

**Realized bits shipped always equal bits produced.** Every bit made gets sold; supply and demand reconcile through price. Plotted naively, the two lines would be the same line twice.

Since pricing is out of scope, the demand line is defined as:

> **Demand = bits the world would consume at constant 2025 real $/GB.**

Price is frozen as a *reference*, not modeled. This is what allows the lines to diverge, and makes the gap interpretable:

**Gap(q) = Demand(q) / Supply(q) − 1** — "unserved demand at 2025 prices."

Consequence to accept knowingly: demand never self-corrects, so the gap runs hotter than any real-world gap would. It is a **pressure index, not a physical shortfall forecast**. `market.py` is stubbed as the seam where a price/elasticity layer plugs in later, if ever.

---

## 1. Units, time base, and core identities

- Internal unit: **bits**. Display unit: **exabytes per quarter (EB/q)**. The Gb/GB/EB 8x conversion error is the #1 silent-failure mode in this domain — `units.py` with explicit converters and tests, no bare floats crossing module boundaries.
- Time base: **quarterly**, `2018Q1 … 2032Q4`. Backcast 2018–2025, project 2026–2032.
- Quarterly resolution is load-bearing, not cosmetic — fab ramps are S-curves measured in quarters, tool lead times are quoted in quarters, inventory swings and consumer seasonality (Q3/Q4 build) are quarterly phenomena, and node transitions land mid-year.
- DRAM and NAND get **separate line pairs** with separate density curves. They are not fungible and are never aggregated.

**Demand identity:**
```
Demand(q) = Σ_segments  Units(s,q) × GB_per_unit(s,q) × (1 − efficiency_deflator(s,q))
```

**Supply identity** (producer `p`, node `n`):
```
raw_capacity(q) = Σ_p Σ_n  WSPM(p,n,q) × 3 months × GB_per_wafer(n,q) × Util × Yield(n,q)
```

## 2. Supply: one binding bottleneck per quarter

Per your instruction, supply is constrained by **a single binding factor at any point in time**, and the model's job is to **project which factor binds in each quarter**:

```
Supply(q)  = min over candidates:
    C1  wafer capacity      # installed cleanroom + tools
    C2  lithography         # EUV/DUV scanner availability
    C3  other WFE           # HAR etch / depo / implant (Lam, TEL, AMAT)
    C4  HBM back-end        # TSV, thinning, bonding, KGD
    C5  test                # HBM test time is 3-5x commodity
    C6  advanced packaging  # TSMC CoWoS — gates HBM *consumption*

binding_constraint(q) = argmin(...)     ← a first-class model output
```

**`binding_constraint(q)` is a headline deliverable**, not a diagnostic: a plotted band across the quarterly x-axis showing which factor is the gate at each point in time, and where the handoffs occur. The identity of the bottleneck can change over the horizon, and knowing *when* it changes is the point.

The gap between the binding constraint and the next-tightest candidate is also reported — a bottleneck that binds by 1% is a different situation from one that binds by 30%, because relieving the former just exposes the next one.

---

## 3. Supply-side variables

### Installed capacity
| ID | Variable | Notes |
|---|---|---|
| S1 | Base-quarter wafer capacity (kWSPM, 300mm) by producer | DRAM: Samsung, SK Hynix, Micron, CXMT, Nanya/Winbond. NAND: + Kioxia/SanDisk, YMTC, Solidigm |
| S2 | Greenfield fab pipeline, **quarterly S-curve ramps** | shell → tool-in → qual → volume, ~12–16 quarters. MU Boise ID1/ID2, MU Clay NY, MU Hiroshima; SK M15X, Yongin; Samsung P4/P5; Kioxia Kitakami K2 |
| S3 | **Capacity loss on node conversion** | Shrinks *cost wafers*: more process steps → longer cycle time → 5–15% fewer wafer-outs on the same toolset. Means bit growth < density growth |
| S4 | Samsung foundry↔DRAM line allocation | Swing factor; capacity can shift between logic and DRAM |
| S5 | Legacy node retirement (DDR4 EOL) | |
| S6 | Utilization | |
| S7 | Disruption term | Fire / quake / power-outage haircut (Hsinchu, Xi'an precedent) |
| S8 | **NAND↔DRAM capex and cleanroom competition** | Shared budget and shell space — the reason both must be in one model |

### Equipment / WFE (feeds constraints C2, C3)
| ID | Variable | Notes |
|---|---|---|
| S9 | ASML EUV units/yr and **memory's share** of them | Logic takes most |
| S10 | EUV layers per node, by roadmap step | ~1–2 on 1γ DRAM today; rises with 1δ/0a. NAND is near-EUV-free |
| S11 | HAR etch/depo capacity (Lam, TEL) | Binds 3D NAND layer scaling especially — that's an etch problem, not a litho problem |
| S12 | HBM back-end: TSV drill, thinning, TC-NCF/MR-MUF, hybrid bonding | → C4 |
| S13 | Test capacity (Advantest/Teradyne); HBM test time 3–5x commodity | → C5 |
| S14 | TSMC CoWoS / advanced packaging | → C6 |
| S15 | ABF substrate supply | Historical chokepoint |
| S16 | **Tool order → qualified-production lead time (4–6+ quarters)** | Makes near-term supply near-fixed; central to the quarterly model |
| S17 | WFE $ → kWSPM conversion ($/wspm, rising per node) | Cross-check vs ASML/AMAT/LRCX/KLA/TEL memory-segment disclosures |

### Bit density / technology
| ID | Variable | Notes |
|---|---|---|
| S18 | **Bit-growth-per-wafer decay curve (DRAM)** ⭐ | Fell from ~30–40%/yr (2010s) to ~5–10%/yr. Explicit, tunable, decaying quarterly series |
| S19 | DRAM node roadmap & cadence per player (1α→1β→1γ→1δ→0a) | Capacitor aspect-ratio limits |
| S20 | **NAND layer roadmap (2xx→3xx→4xx→1000) + string stacking** ⭐ | NAND still scales where DRAM doesn't — a major asymmetry between the two line pairs |
| S21 | Die size, gross-die-per-wafer, quarterly **yield ramp curves** | New nodes start low and climb |
| S22 | **HBM bit trade-ratio `k` ≈ 2–3x** ⭐ | An HBM bit consumes ~2–3x the wafer capacity of a DDR5 bit (larger die from TSVs/periphery, stack yield loss, KGD, test loss). HBM growth **multiplicatively subtracts** from commodity DRAM supply. Highest-leverage single input in the supply model |
| S23 | Trajectory of `k` | HBM4 with a logic base die differs from HBM3E |
| S24 | **3D DRAM / 4F² + VCT** ⭐ | Potential regime break, ~2030+. Timing switch |
| S25 | QLC/PLC adoption (NAND) | Density vs endurance |

### Producer behavior
| ID | Variable | Notes |
|---|---|---|
| S26 | **Capex reaction function** — capex as f(lagged profitability), ~8–12 quarter lag ⭐ | The classic memory hog-cycle feedback loop |
| S27 | Oligopoly concentration (3 players ≈90% of DRAM) | |
| S28 | **China (CXMT/YMTC) — see §5** ⭐ | Modeled as captive; does not relieve the global gap |
| S29 | Export-control policy (both directions) | |
| S30 | **Inventory** — producer + channel + customer, weeks-of-supply | A **stock**, not a flow, with target-days behavior. Destocking/restocking swings effective supply and demand by 5–10% and is inherently quarterly |

---

## 4. Demand-side variables

### AI / datacenter
| ID | Variable | Notes |
|---|---|---|
| D1 | AI accelerator units/quarter | Nvidia GB200/GB300/Rubin/Rubin Ultra; AMD MI4xx; Google TPU; AWS Trainium; Meta MTIA; MSFT Maia; Huawei Ascend |
| D2 | **HBM GB per accelerator** ⭐ | H100 80GB → H200 141 → B200 192 → GB300 288 → Rubin ~288–384 → Rubin Ultra ~1TB-class. Compounds *on top of* unit growth |
| D3 | Stack height (8→12→16-hi) and per-stack capacity | |
| D4 | **Conventional DDR5/LPDDR inside AI servers** ⭐ | Underrated: a Grace CPU carries ~480GB LPDDR5X; an AI rack carries TBs of *non-HBM* DRAM. AI pulls commodity DRAM, not just HBM |
| D5 | LPDDR in datacenter (SOCAMM/LPCAMM) | New pool competing with mobile for the same lines |
| D6 | **KV-cache sub-model** ⭐ | tokens_served/quarter × KV-bytes/token × context-length distribution → capacity requirement. Long-context / reasoning / agentic workloads scale KV cache superlinearly |
| D7 | Training vs inference mix | Inference is capacity- and bandwidth-bound |
| D8 | **AI NAND pull (QLC eSSD)** ⭐ | 122TB/245TB drives for data lakes, KV-cache offload, checkpointing. NAND is no longer a consumer story |
| D9 | Hyperscaler capex ($/quarter) → accelerator units | **Top-down cross-check on the bottom-up D1 build** |
| D10 | **Datacenter power ceiling (GW)** ⭐ | Hard physical cap on deployable accelerators from ~2028; a genuine demand-side brake |
| D11 | Sovereign AI / enterprise on-prem | |

### Conventional
| ID | Variable | Notes |
|---|---|---|
| D12 | Traditional servers: units × GB/server | Content grows with core count; DDR5 → MRDIMM |
| D13 | PCs: units (~250M/yr) × GB/PC | Win10 EOL pull-forward; AI-PC 16→32GB floor |
| D14 | Smartphones: ~1.2B units × GB/phone | On-device AI pushes 8→12→16GB |
| D15 | Automotive (ADAS/L3) | Small bits, fast growth, long qual cycles → sticky |
| D16 | Graphics / console / networking / industrial / IoT | GDDR7 competes for the same fabs; PS6/next-Xbox (~2027–28) is a real bit sink |
| D17 | Robotics / physical AI | Out-year optionality |
| D18 | Legacy DDR4 | Big-3 EOL → supply cliff; CXMT absorbing |
| D19 | **Consumer seasonality** | Quarterly build cycles — visible only at this resolution |

### Demand-side offsets
| ID | Variable | Notes |
|---|---|---|
| D20 | **AI memory-efficiency deflator** ⭐⭐ | Bits per unit of delivered intelligence, falling over time: quantization (FP16→FP8→FP4 is a 4x cut), MoE sparsity, KV-cache compression, PagedAttention, speculative decoding, distillation. The largest single downward force on AI demand and the natural counterweight to D2+D6 |
| D21 | Substitution: DRAM→NAND (KV offload, storage-class memory) | Moves bits *between* the two line pairs |
| D22 | **CXL memory pooling** ⭐ | Raises utilization of *installed* DRAM → reduces demand for *new* DRAM |
| D23 | AI capex digestion / air-pocket | |

---

## 5. China / CXMT treatment

Per your correction: **CXMT output is fully booked domestically.** Chinese memory supply serves Chinese memory demand; exporting it westward would be a *reallocation*, not net new global bits.

So China is modeled as a **captive region**, and this is a structural feature of the model rather than a footnote:

- Supply and demand are each split into **China** and **Rest-of-World**.
- CXMT/YMTC bits enter **global supply and global demand symmetrically** — a CXMT ramp therefore does **not** move the gap. It displaces Chinese domestic demand for imported bits by exactly as much as it adds to global supply.
- Headline output: the **global** pair you asked for, plus an **addressable (ex-captive)** pair as a companion, since those are the bits actually available to the merchant market.
- Exposed parameter: `china_captive_share` (default ~1.0). Dialing it below 1.0 lets CXMT leak into the merchant market — and the model will show that as reallocation, with the *global* gap unchanged and only the regional split moving. That behavior is worth being able to demonstrate explicitly.

---

## 6. Architecture

```
memoryProjection/
  00-plan.md                # this document, committed to the repo
  assumptions/              # every number lives here, NOT in code
    supply_capacity.yaml    #   each entry: {value, source_url, confidence, notes}
    tech_roadmap.yaml
    constraints.yaml        #   C1–C6 candidate ceilings
    demand_ai.yaml
    demand_conventional.yaml
    china.yaml
    scenarios.yaml
  model/
    units.py                # bit/GB/EB converters + guards
    calendar.py             # quarterly index 2018Q1–2032Q4, S-curve ramp helpers
    supply.py               # capacity → bits; HBM trade-ratio; the C1–C6 min() and argmin
    demand.py               # segment build-up; KV-cache sub-model; efficiency deflator
    china.py                # captive-region netting
    market.py               # STUB — seam for a future price layer
    scenarios.py
  report/
    charts.py               # the two lines (quarterly) + gap + binding-constraint band
    interactive.html        # sliders on the ⭐ variables
  tests/
    test_units.py
    test_backcast.py
  README.md
```

Assumptions are **data, not code**. Every input carries a source URL and a confidence tag, so the YAML files double as the research record and a disagreement becomes a one-line edit rather than a code change.

## 7. Scenarios

Three neutrally-named cases driven off the ⭐ variables — **Tight**, **Central**, **Loose** — spanning the plausible range of HBM trade-ratio, density decay, capex response, 3D DRAM timing, and the efficiency deflator.

Plus a **sensitivity tornado** on the gap in a chosen quarter (e.g. 2029Q4): which single input moves it most.

## 8. Calibration

Backcast **2018Q1–2025Q4** against published quarterly bit-shipment and capacity data. Bit shipments are observable from public filings, so this works with no price model. Target: within ~10% on quarterly DRAM/NAND bit-supply growth. This is where S18 (density decay) and S22 (HBM trade-ratio) get fitted values instead of guessed ones. If the model can't retrodict the 2023 trough and the 2024–26 ramp, it isn't ready to project 2028.

## 9. Build order

1. Write this plan to `memoryProjection/00-plan.md`
2. `units.py` + `calendar.py` + tests (prevents the worst class of silent bug)
3. Base-quarter supply from public filings → DRAM + NAND bits, calibrated to 2024/25 actuals
4. Constraint stack C1–C6 → produce `binding_constraint(q)` early, since its identity shapes everything downstream
5. Demand build-up: conventional segments first (well-documented), then AI/HBM, then the KV-cache sub-model
6. China captive-region netting
7. Backcast 2018–2025; fit S18/S22
8. Project 2026Q1–2032Q4; scenarios; tornado
9. Charts + interactive HTML + a summary note in the Obsidian vault

## 10. Verification

- `pytest` — unit conversions, and backcast within tolerance of published actuals
- **Independent cross-check**: bottom-up AI demand (D1 × D2) vs top-down hyperscaler capex (D9). A >20% disagreement means one is wrong, and I'll surface it rather than paper over it
- **China invariant test**: varying `china_captive_share` must leave the *global* gap unchanged — it only moves the regional split. This is an assertable property and a good guard against double-counting
- Every ⭐ variable exposed as a slider in the HTML so the inputs can be stressed directly

## 11. Open inputs

Public data is thin on a few of the ⭐ variables — notably CXMT's true yield and the AI efficiency deflator (D20). These are judgment calls rather than data lookups. I'll ship defaults with explicit confidence tags and surface them as the first sliders, so they're easy to override.
