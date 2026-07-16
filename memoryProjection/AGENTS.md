# Agent guide to this folder

You are looking at a **global memory (DRAM + NAND) bit supply/demand model**, quarterly,
2018Q1–2032Q4. This file tells you how to *use* it. For *why it is built the way it is*,
read `README.md` first — it is not optional, because most wrong conclusions from this
model come from misreading what the numbers mean, not from the numbers.

## The one thing you must not get wrong

The headline output is a **gap** (demand ÷ supply − 1, e.g. +44% in 2029). It is a
**pressure index, not a forecast of missing bits.** The model deliberately switches off
the three things that end every real memory shortage — producer discipline, buyer
destocking, and a capacity-investment supply response — plus price elasticity. So the gap
*cannot* close by construction (`p_gap_closed ≈ 0` in out-years). That zero is a property
of the model's shape, **not** evidence a glut is unlikely. If you quote the gap as
"bits the world will be short," you are wrong. Quote it as "how hard price and rationing
have to work."

Corollary an agent will trip on: **AI/datacenter demand is never rationed in this model.**
The inelastic core (HBM, AI host DRAM, KV offload, AI eSSD, auto/industrial) peaks near
~⅓ of world DRAM bits and always fits under supply; HBM specifically runs in slight
surplus every year (`hbm_is_capped` is false in all quarters). The *entire* gap is the
contested consumer pool (PC, phone, console, graphics, traditional servers) getting
squeezed from 100% served to ~60% served. Report those two pieces separately if you can.

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
| `assumption` | **every input flattened**: `key`, `value_json`, `unit`, `source`, `confidence`, `notes` |
| `run_meta` | key/value: generation time, `actuals_end` (2026Q2), timeline, confidence audit |

Segments in `demand_segment`: inelastic = `hbm`, `ai_server_host`, `kv_offload`,
`ai_essd`, `auto_industrial_iot`; contested = `pc`, `smartphone`, `console`, `graphics`,
`servers_traditional`, `other`; plus `inventory` (a swing term, not a buyer — exclude it
when summing end-demand).

Everything at/before **2026Q2 is observed data** (`is_actual=1`), overrides the model, and
carries no supply uncertainty band. Do not "correct" an actual against the model.

## Re-running the model (only when you changed an input)

```bash
./.venv/bin/python -m pytest tests/ -q     # 50 tests — the overclaim guard; run first
./.venv/bin/python -m report.build         # -> report/memory_model.html
./.venv/bin/python -m report.export        # -> report/memory_model.sqlite (re-query after this)
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
fab ramps · `actuals.py` reality overrides through 2026Q2 · `supply.py` capacity→bits, HBM
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
