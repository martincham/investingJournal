# Agent guide to this folder

You are looking at a **global memory (DRAM + NAND) bit supply/demand model**, quarterly,
2018Q1–2032Q4. This file tells you how to *use* it. For *why it is built the way it is*,
read `README.md` first — it is not optional, because most wrong conclusions from this
model come from misreading what the numbers mean, not from the numbers.

## The one thing you must not get wrong

The headline output is a **gap** (demand ÷ supply − 1, e.g. +27% in 2029). It is a
**pressure index, not a forecast of missing bits.** The model deliberately switches off
the three things that end every real memory shortage — producer discipline, buyer
destocking, and a capacity-investment supply response — plus price elasticity. So the gap
is biased toward staying open. Since the November 2026 vintage the out-years include
announced fabs and a faster node cadence, and `p_gap_closed` rises from ~2% (2027) to
~13% (2030) and ~42% (2032); before that it was ≈ 0 by construction. Either way it is
biased low, **not** evidence about how likely a glut is. If you quote the gap as
"bits the world will be short," you are wrong. Quote it as "how hard price and rationing
have to work."

Corollary an agent will trip on: **on the unrationed line, AI/datacenter demand is served
first and in full.** The inelastic core (HBM, AI host DRAM, KV offload, AI eSSD, agentic
CPU servers, auto/industrial) fits under supply, and HBM runs in surplus through 2031
(`hbm_is_capped` is true only in 2032Q2–Q4, where the test ceiling C5 binds). The gap is
therefore the contested consumer pool (PC, phone, console, graphics, traditional servers)
getting squeezed. Report those two pieces separately if you can.

**But reality now rations AI too (Nov 2026).** NVIDIA halved SOCAMM per Vera CPU, Rubin
Ultra is being tested with 192–384GB instead of 1TB, CSPs are evaluating 8-Hi HBM for
2027 ASICs, and LPDDR allocations cover ~60% of NVIDIA's 2027 need. That is price
rationing of AI memory per unit. It lives in the second demand line below, not in the
unrationed one.

## The second demand line: demand at current prices (Nov 2026)

`balance.demand_at_price_eb` / `gap_at_price`, `annual_summary.*_at_price*`, and the
per-segment `demand_segment_at_price` table hold **demand if real prices stay at their
2026Q3 level** (inputs: `assumptions/demand_at_price.yaml`). It equals the unrationed line
before `actuals.rationing_start` (2026Q1) and is never above it after. Read it as: positive
`gap_at_price` = today's prices are still too low to clear the market, so prices must rise
further; negative = today's prices would leave bits unsold, so prices fall. In observed
2026 quarters it is positive and shrinking (+18%, +15%, +12%), matching blended ASP gains
of +80%, +52%, +21%. Note 2025Q1, at roughly flat prices, already shows +6%: treat ~5% as
the model's baseline demand-over-supply offset, not as signal. The at-price line is a
counterfactual at a held price, not a price forecast.

## Fastest way to get numbers: query the SQLite, don't re-run

`report/memory_model.sqlite` holds every output of the last run, queryable. Use it before
you reach for the Python — it is faster and you cannot break it.

```bash
./.venv/bin/python -c "
import sqlite3, pandas as pd
c = sqlite3.connect('report/memory_model.sqlite')
print(pd.read_sql('''
  select year, dram_supply_eb, dram_demand_eb, dram_gap, binding
  from annual_summary where scenario=\"central\" and year>=2025''', c))
"
```

Tables (all keyed by `scenario` ∈ {tight, central, loose} and usually `quarter`; product
∈ {dram, nand}). Units are **EB (exabytes) of bits** unless noted:

| table | what it holds |
|---|---|
| `annual_summary` | the headline table: supply/demand/gap per year, binding constraint |
| `balance` | quarterly supply, demand, gap, deficit_eb, addressable_gap, captive_eb, `is_actual` |
| `demand_segment` | demand_eb by `segment` — the decomposition (see segment list below) |
| `supply_detail` | dram_total/commodity/hbm/china EB, `hbm_wafer_share`, `hbm_is_capped`, binding constraints |
| `uncertainty_band` | P10/P50/P90 for supply, demand, gap; `p_gap_closed` |
| `fleet`, `vintage_viability` | GPU cohorts, retirement/replacement, power-eviction vs cash economics |
| `power_pipeline` | announced→delivered datacentre GW (slip, cancellation, grid ceiling) |
| `capex_crosscheck` | can the world afford the accelerators demand implies (the top-down check) |
| `tornado` | sensitivity: gap_low/gap_high per slider, ranked |
| `market` | industry DRAM price, cost, gross margin, shipped EB, revenue per quarter (see price layer below) |
| `assumption` | **every input flattened**: `key`, `value_json`, `unit`, `source`, `confidence`, `notes` |
| `run_meta` | key/value: generation time, `actuals_end` (2026Q3), timeline, confidence audit |

Segments in `demand_segment`: inelastic = `hbm`, `ai_server_host`, `kv_offload`,
`ai_essd`, `ai_cpu_server` (new Nov 2026: agentic-AI CPU servers), `auto_industrial_iot`; contested = `pc`, `smartphone`, `console`, `graphics`,
`servers_traditional`, `other`; plus `inventory` (a swing term, not a buyer — exclude it
when summing end-demand).

Everything at/before **2026Q3 is observed data** (`is_actual=1`), overrides the model, and
carries no supply uncertainty band. Do not "correct" an actual against the model.

## The price layer: industry DRAM price, margin, revenue (Nov 2026)

Table `market` (per scenario × quarter), from `model/market.py` and `assumptions/market.yaml`.
Real 2025 $/GB. Starts at the observed anchor quarter (`actuals_end`: revenue ÷ bits) and
moves each quarter by `kappa × (gap at the going price − baseline_offset)`. Demand at the
going price uses the elasticity implied by the two demand lines (~−0.1). `kappa` is solved
once on central so that 2026Q4 = TrendForce's +15% guide, stored in `run_meta.market_kappa`,
and shared by every scenario. Caps: cloud providers' DRAM spend ≤ 68% × 67% of their capex
(TrendForce), and price ≥ cost / 1.33 (Micron's 2023 trough margin). Cost per GB is anchored
at an 87% margin in 2026Q3 and falls with bits per wafer.

Why a path and not a clearing price: at elasticity −0.1, a 5% quantity error moves the
clearing price ~60%, so the level can't be read off this model's quantities. The path is
checked, not fitted, against Micron's FY27 guide (86.25% floor, rising): central 2027
margins come out at 88–90%.

Read with care: the price layer never feeds back into supply or demand. **Loose collapses
to the cost floor from 2028 and stays there**, because loose supply jumps above demand
straight after the observed data and the model has no supply cut to end a glut. Treat loose
prices as "a glut is possible", not as a path.

## Vintages: earlier projections, frozen

`vintages/<YYYY-MM>/` holds each published projection exactly as it was produced:
`memory_model.sqlite`, `memory_model.html`, a copy of `assumptions/`, and `VINTAGE.md`
(commit, actuals cutoff, sqlite sha256). Never edit or re-run one. `report/vintages.html`
puts them side by side with a slider. micronProjection reads a vintage by path and sha256,
never `report/`, so re-running here cannot move its numbers until it is repointed.

## Re-running the model (only when you changed an input)

```bash
./.venv/bin/python -m pytest tests/ -q     # 66 tests — the overclaim guard; run first
./.venv/bin/python -m report.build         # -> report/memory_model.html
./.venv/bin/python -m report.export        # -> report/memory_model.sqlite (re-query after this)
./.venv/bin/python -m report.freeze YYYY-MM # -> vintages/YYYY-MM/ (only to publish a new projection)
./.venv/bin/python -m report.compare        # -> report/vintages.html
```

If `.venv` is missing: `python3 -m venv .venv && ./.venv/bin/pip install numpy pandas pyyaml plotly pytest`.

**The tests are the credibility gate, not a formality** — they exist to catch overclaiming
and have caught real sign errors (2019/2023 showing as shortages instead of gluts). If you
change the model and a backcast test fails, the model is now wrong, not the test. Fix the
model.

## Changing assumptions

Every number lives in `assumptions/*.yaml` as `{value, source, confidence, notes}` — data,
not code. Disagreeing with the model is a **one-line YAML edit**, then re-run build+export.
Do not hardcode numbers in `model/*.py`; if a value isn't in YAML it is a derived quantity,
not an input. Start points: `demand_ai.yaml` (efficiency deflator, HBM-per-accelerator),
`supply_capacity.yaml` (wafer capacity, `hbm_wafer_share`, trade ratio),
`datacenter.yaml` (announced GW, slip, cancellation), `uncertainty.yaml` (Monte Carlo sigmas).

## Model code map (`model/`)

`units.py` bit/GB/EB converters (the 8× Gb/GB footgun) · `calendar.py` quarterly index +
fab ramps · `actuals.py` reality overrides through 2026Q3 · `supply.py` capacity→bits, HBM
trade-ratio, the C1–C6 `min()` and argmin · `datacenter.py` announced→delivered GW ·
`fleet.py` vintages, viability, replacement demand · `demand.py` segment build-up, KV-cache
sub-model, efficiency deflator, inventory · `china.py` captive-region netting ·
`uncertainty.py` correlated Monte Carlo → P10/P90 · `scenarios.py` tight/central/loose +
tornado · `market.py` **STUB** — the price/elasticity seam, deliberately empty; the module
docstring documents what a price layer would do and why it's out of scope.

## The six supply bottlenecks

Supply is `min()` over C1 cleanroom/wafer capacity, C2 EUV lithography, C3 other WFE, C4
HBM back-end, C5 test, C6 CoWoS packaging; `binding_constraint(q)` is a first-class output.
Asymmetry to remember: when an **HBM** ceiling (C4–C6) binds, freed wafers flow back to
commodity DRAM (~2.85× more bit-efficient), so an HBM bottleneck *raises* total DRAM bits
while leaving AI demand unserved. Total-bit and AI-usable-bit constraints are different;
the model tracks both.
