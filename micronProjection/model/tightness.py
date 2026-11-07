"""The price signal: how hard the contested pool is being squeezed.

Derived from upstream's output. Never a modification of it -- every input here is a
column memoryProjection emitted, and `test_tightness_is_a_pure_function_of_upstream`
holds it that way.

Two decisions make this signal work, and both were found by testing rather than reasoning:

**1. The inelastic core is served in full, first.** Upstream's AGENTS.md states the core
(HBM, AI host DRAM, KV offload, auto/industrial) "always fits under supply" and that HBM
runs in slight surplus in every quarter. So the whole squeeze lands on the contested
pool -- PC, phone, console, graphics, traditional servers -- which is where price is
actually set. Honouring a stated property of the input, not adding an assumption.

**2. The inventory swing is INCLUDED.** This is the one that matters. AGENTS.md says to
exclude `inventory` when summing end-demand, which is right for that purpose and fatal
for this one. Computed without it, the contested served fraction says 2023 -- the deepest
glut in memory history, when Micron ran a -32.7% gross margin -- was TIGHTER than the
2021 boom:

    year  phase          ex-inventory   inc-inventory   upstream gap
    2019  glut              0.908        1.158 surplus    -12.8%
    2021  boom              0.912        0.837 deficit    +17.9%
    2023  glut, GM -32.7%   0.833        1.105 surplus     -8.5%
    2026  boom              0.807        0.782 deficit    +21.1%

Only the inclusive column signs all four correctly. The reason is that upstream's demand
is *unrationed demand at constant 2025 prices* -- a counterfactual. The 2019 and 2023
gluts were destocks, and a destock lives entirely in the inventory segment. The destock
IS the glut. Drop the column and you have deleted the thing that distinguishes a glut
from a boom.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from model.conf import Assumptions
from model.upstream import Baseline, BaselineQuarter
from model.vendor.calendar import Quarter


@dataclass(frozen=True)
class Signal:
    """The tightness signal for one quarter, with the pieces that built it."""

    quarter: Quarter
    contested_supply_bits: float
    contested_demand_bits: float
    inventory_bits: float
    served_fraction: float          # <1 = short, >1 = surplus
    served_fraction_ex_inventory: float   # diagnostic ONLY -- signs 2023 backwards
    tightness: float                # log(reference/served). >0 tight, <0 loose
    gap_upstream: float             # for contrast, as given

    @property
    def is_tight(self) -> bool:
        return self.tightness > 0


def signal(a: Assumptions, b: BaselineQuarter) -> Signal:
    reference = a.scalar("asp.served_reference")

    contested_supply = b.contested_supply_bits
    contested_demand = b.contested_demand_bits + b.inventory_bits

    served = contested_supply / contested_demand if contested_demand > 0 else float("inf")
    served_ex = (
        contested_supply / b.contested_demand_bits if b.contested_demand_bits > 0 else float("inf")
    )

    # LOG of the ratio, not the ratio minus one. Both are ~identical near balance (log x
    # ~ x-1) and the fit is statistically indistinguishable (R2 0.526 vs 0.533), but
    # `ref/served - 1` is a HYPERBOLA: as served falls toward zero it runs away to
    # infinity. Composed with an exponential price response that is exp(1/x), and it
    # detonates -- the tight scenario reached a served fraction of 0.20, a tightness of
    # +3.97 and an ASP of $3,053/GB before this was fixed. A log-ratio is the natural
    # scale for a ratio and is symmetric between shortage and surplus, which the
    # hyperbola is not.
    #
    # Referenced, not absolute. `served` never equals 1.0 even in balanced years (2020 =
    # 0.967, 2022 = 1.022) because upstream's demand line is a counterfactual with a
    # level of its own. What matters is distance from the served fraction that
    # historically coincided with flat real ASP, which is what `reference` calibrates.
    return Signal(
        quarter=b.quarter,
        contested_supply_bits=contested_supply,
        contested_demand_bits=contested_demand,
        inventory_bits=b.inventory_bits,
        served_fraction=served,
        served_fraction_ex_inventory=served_ex,
        tightness=math.log(reference / served) if served > 0 else float("inf"),
        gap_upstream=b.gap,
    )


def series(a: Assumptions, baseline: Baseline) -> list[Signal]:
    return [signal(a, b) for b in baseline.quarters]
