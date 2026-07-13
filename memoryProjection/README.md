# Global memory bit supply & demand model, 2026Q1–2032Q4

Two lines, quarterly, for **DRAM and NAND separately** (never summed — NAND ships ~25x
more bytes, so an aggregate would drown the DRAM story):

- **Supply** — bits the industry can physically produce, through the tightest of six
  candidate bottlenecks, with the binding one identified in every quarter.
- **Demand** — bits the world would consume **at constant 2025 real prices**.

No price layer, no financials. This is a model, not an argument: it takes no position
and produces what the inputs imply.

## Run it

```bash
python3 -m venv .venv && PIP_USER=0 ./.venv/bin/pip install numpy pandas pyyaml plotly pytest
./.venv/bin/python -m pytest tests/ -q        
./.venv/bin/python -m report.build          
```

Open `report/memory_model.html` in a browser. It has scenario toggles, sliders on the
12 load-bearing inputs, the binding-constraint band, the demand decomposition, a
sensitivity tornado, and a table view.

## Why the demand line is defined the way it is

Realised bits shipped **always** equal bits produced — every bit made gets sold, and
supply and demand reconcile through price. Plotted naively, the two lines would be the
same line twice.

So demand here is **unrationed** demand: what buyers would take if memory still cost
2025 money. That is why the conventional segments use *trend* content per unit (the
32GB AI PC, the 16GB phone) and not the cut-down configurations OEMs are actually
shipping in 2026 while memory is unaffordable. **Those cuts are the shortage.**
Subtracting them from demand would define away the thing being measured.

Consequence, stated plainly: the gap is a **pressure index, not a forecast of physical
shortfall**. It says how hard price and rationing have to work. `model/market.py` is
the stub where a price/elasticity layer would plug in.

## Observed vs projected — and the one thing that can never be pinned

Everything up to **2026Q2 is observed data**, sourced in `assumptions/actuals.yaml`, and it
overrides the model. The supply line therefore has **no uncertainty band** before that
point. A bug like "the power ceiling binds in 2026" is impossible by construction: you
cannot have a modelling error in a quarter you are not modelling.

But **demand can never be pinned, and its band never collapses — not even over history.**
"Bits the world would consume at constant 2025 prices" is a *counterfactual*. What was
observed in 2026 is what actually cleared, at 2026's prices, after phone makers cut
memory content and PC OEMs killed low-end SKUs. That rationed outcome is not demand; it
is demand after the shortage got done with it. So demand is inferred in 2019 exactly as
much as in 2031. This is a property of the question, not a gap in the data.

After 2026Q2, bands are P10–P90 from a 400-draw Monte Carlo (`model/uncertainty.py`),
widening as `sigma * sqrt(years)`. The draws are **correlated** — the world where AI
demand disappoints is the same world where the buildout stalls and producers over-build.
Everything going wrong at once is not a coincidence; it is what a memory cycle *is*.

## Where AI memory demand comes from

Accelerator shipments are an **output**, not an assumption:

```
shipments = (new datacentre power)/kW  +  (power freed by retirements)/kW
```

- `model/datacenter.py` — announced GW minus attrition. Projects die in grid-interconnect
  queues, for want of transformers, on local opposition, or because the tenant walks. Most
  of the shortfall is **slip** (arrives late) rather than **cancellation** (never arrives),
  and the two are tracked separately because they have opposite out-year implications.
- `model/fleet.py` — vintage cohorts that get retired and replaced. **Retiring an A100
  (80GB, 0.4kW) and refilling its watt with a Rubin Ultra (~1TB) is a large HBM purchase
  for zero net growth in power.** That replacement stream is the piece an exogenous
  shipments series cannot see.

Two retirement rules, and the spread between them is the whole point:

| | rule | when the 2020 vintage dies |
|---|---|---|
| **Power eviction** | not worth the watt it occupies, given what a frontier chip would do with it | **2026Q1** |
| **Cash unviability** | compute no longer earns its electricity + hosting | 2030Q3 |

A GPU can be simultaneously **profitable to run and not worth keeping**. Eviction only
switches on when the fleet is actually against its power ceiling, so the mechanism has to
earn its own relevance rather than being assumed.

## Layout

```
assumptions/     every number, as data: {value, source, confidence, notes}
  actuals.yaml           OBSERVED data through 2026Q2 -- overrides the model
  supply_capacity.yaml   tech_roadmap.yaml   constraints.yaml
  demand_ai.yaml         demand_conventional.yaml
  datacenter.yaml        announced pipeline, slip, cancellation
  gpu_fleet.yaml         vintages, viability economics, power eviction
  china.yaml             uncertainty.yaml    scenarios.yaml
model/
  units.py       bits/GB/EB converters + guards (the 8x footgun)
  calendar.py    quarterly index, S-curve fab ramps, year-centred interpolation
  actuals.py     reality overrides the model through 2026Q2
  supply.py      capacity -> bits; HBM trade-ratio; the C1-C6 min() and argmin
  datacenter.py  announced GW -> delivered GW (attrition + slip + grid ceiling)
  fleet.py       vintages, economic viability, retirement, replacement demand
  demand.py      segment build-up; KV-cache sub-model; efficiency deflator; inventory
  china.py       captive-region netting
  uncertainty.py correlated Monte Carlo -> P10/P90 bands
  market.py      STUB (price layer, deliberately out of scope)
  scenarios.py   Tight / Central / Loose; sensitivity tornado
report/build.py  -> memory_model.html
tests/           53 tests: units, backcast, china invariants, cross-checks, fleet
```

Assumptions are **data, not code**. Every input carries a source URL and a confidence
tag, so the YAML files double as the research record and disagreeing with the model is
a one-line edit.

## The six bottlenecks

Supply is `min()` over these, and `binding_constraint(q)` is a first-class output:

| | ceiling | what it caps |
|---|---|---|
| C1 | Cleanroom / installed wafer capacity | total DRAM wafer starts |
| C2 | Lithography (EUV) | total DRAM wafer starts |
| C3 | Other WFE (HAR etch/depo) | total DRAM wafer starts |
| C4 | HBM back-end (TSV, bonding, KGD) | HBM bits |
| C5 | Test (HBM test time is 3-5x commodity) | HBM bits |
| C6 | Advanced packaging (TSMC CoWoS) | HBM bits *consumed* |

Note the asymmetry: when an **HBM** ceiling binds, the freed wafers flow back to
commodity DRAM, which is ~2.85x more bit-efficient. So an HBM bottleneck *raises* total
DRAM bit output while leaving AI demand unserved. The constraint on total bits and the
constraint on AI-usable bits are different constraints, and the model tracks both.

## Calibration

The backcast is the credibility gate, and it is not decoration — it caught three real
bugs. The model reproduces **8 of 9 known cycle phases** 2018–2026, including the 2019
and 2023 gluts and the 2021 chip crisis. The one "miss" (2022, called balanced) is a
year of two halves, and the *quarterly* series does show the H2 collapse the annual
average hides.

Base-year DRAM output (~39 EB in 2025) is corroborated three independent ways: wafer
capacity x density; $122bn of DRAM revenue at a ~$2.9/GB blend; and Micron's ~22% bit
share against its own disclosed output.

## What the tests are actually for

They exist to catch overclaiming, and they did. Bugs caught by tests rather than by
inspection, in build order:

- A **power ceiling that bound in 2026**, which would have shown HBM in surplus during a
  period when it was famously sold out. (Now impossible: 2026 is pinned to actuals.)
- An **accelerator build 85% larger than the assumed capex could fund**.
- **Annual anchors read as 1-Jan values**, which was halving the amplitude of the
  inventory swings that drive the entire memory cycle — and which made the backcast show
  2019 and 2023 as *shortages* when both were historic gluts.
- **HBM wafer share applied to the global pool including CXMT**, so a CXMT ramp made
  Samsung/SK/Micron "produce more HBM". CXMT makes no HBM.
- **A datacentre pipeline delivering negative gigawatts**: the Monte Carlo amplified the
  horizon in *linear* space, so a low draw pushed `realisation_rate` straight through
  zero. A multiplicative quantity has to be perturbed multiplicatively.
- **HBM demand ~20% below HBM supply** in 2026 — impossible for a fully-allocated product.
  The blended HBM-per-accelerator was too low.

The rest:

- **`test_china.py`** — the reallocation invariant. Where Chinese bits are *sold*
  cannot change the global balance, because a Chinese buyer who loses a bit imports a
  replacement. Formally the merchant deficit and the global deficit are identical for
  every value of `captive_share`. What is **not** true, and the model refuses to
  pretend: "a CXMT ramp cannot close the global gap." It can — more capacity means
  more bits exist. What it cannot do is make Samsung/SK/Micron ship one extra bit.
- **`test_crosscheck.py`** — can the world *afford* the accelerators the demand line
  buys? This failed on the first build (an 85% divergence against the capex path) and
  forced a reconciliation. It also caught a power ceiling that was binding in 2026,
  which would have shown HBM in surplus during a period when it was famously sold out.
- **`test_units.py`** — the Gb/GB 8x error, and the year-centring of annual anchors
  (which was quietly halving the amplitude of the inventory swings that drive the
  memory cycle).

## Known limitations

- No price layer, so demand never self-corrects and the gap runs hotter than any real
  gap would. Read the *deficit in EB*, not the ratio, when comparing scopes.
- Out-year wafer capacity (2029+) is the model's assumption, not anyone's guidance.
- The efficiency deflator (`demand_ai.efficiency_deflator_annual`) and CXMT's true
  yield are judgment calls, not data lookups. They are the first two sliders.
- Deterministic. Three scenarios cannot support a probability statement; a Monte Carlo
  over the starred inputs is the natural next step.
