"""The GPU fleet: vintages, economic viability, retirement, and replacement demand.

The point of this module is that accelerator SHIPMENTS are not an input. They are an
output, of a fleet that is being continuously killed off and refilled:

    shipments(t) = (new power available) / kW  +  (power freed by retirements) / kW

The second term is the one everybody forgets, and it is enormous. Retiring an A100
(80GB, 0.4kW) and refilling its watt with a Rubin Ultra (~1TB, 1.45kW) is a large HBM
purchase for ZERO net growth in datacentre power. As the installed base ages, the
replacement stream becomes a bigger and bigger share of total memory demand.

So "how much HBM does the world need" reduces to "when is a GPU no longer worth the
watt it sits on", which is an economics question, which is what this file answers.

TWO RETIREMENT RULES. The model applies whichever bites first, and reports both dates:

  CASH UNVIABILITY -- the chip's compute no longer earns its electricity and hosting.
      This is the textbook rule. On its own it retires GPUs very LATE, because power is
      cheap relative to the value of scarce compute. It is why an A100 is still worth
      running in 2026.

  POWER EVICTION -- when power is the binding constraint, the real cost of an old GPU
      is not its electricity bill but the OUTPUT FOREGONE by not putting a frontier chip
      in that same watt. A chip doing 2% of the frontier's work per watt gets thrown out
      long before it is cash-unviable.

The second is why a GPU can be simultaneously profitable to run and not worth keeping.

Eviction only switches on when power is GENUINELY scarce, and the model is careful about
what that means. Scarcity is judged against an INDEPENDENT yardstick -- how many
accelerators hyperscaler capex wants to buy -- not against the fleet's own appetite. An
earlier version simply refilled all available headroom every quarter, so the fleet
consumed 100% of available power BY CONSTRUCTION, and "is power scarce?" silently
degenerated into "is the buildout decelerating?". You cannot detect scarcity with a fleet
that is defined to expand into whatever space it is given; you need something that wants
more than it can have.

So shipments are a min() over three ceilings, and the binding one is reported:

    capex     -- what the money wants to buy      (hyperscaler capex / ASP)
    power     -- what the grid can actually run   (headroom / kW)
    packaging -- what TSMC can package            (CoWoS)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .calendar import Quarter, interpolate_annual
from .config import Assumptions
from .datacenter import PowerQuarter

MONTHS_PER_QUARTER = 3


@dataclass
class FleetQuarter:
    quarter: Quarter
    units_by_vintage: dict[int, float] = field(default_factory=dict)

    shipments: float = 0.0            # units this quarter
    retirements: float = 0.0          # units retired this quarter
    retired_power_gw: float = 0.0     # watts those retirements handed back
    replacement_share: float = 0.0    # what fraction of shipments merely refill freed watts

    # The demand-side constraint stack -- shipments are min() over these three, and the
    # binding one is a first-class output, exactly as on the supply side.
    desired_units: float = 0.0        # what the money wants to buy   (capex / ASP)
    power_feasible_units: float = 0.0 # what the grid can run         (headroom / kW)
    packaging_feasible_units: float = 0.0  # what TSMC can package    (CoWoS)
    binding_demand_constraint: str = ""

    fleet_units: float = 0.0
    fleet_power_gw: float = 0.0
    available_power_gw: float = 0.0
    power_scarce: bool = False

    hbm_gb_shipped: float = 0.0
    dram_gb_shipped: float = 0.0

    frontier_tflops_per_watt: float = 0.0


def _vintage(a: Assumptions, year: int) -> dict:
    """Spec for a cohort. Clamped to the roadmap's range: a 2033 quarter still ships
    the 2032 vintage rather than exploding.

    Memory content is NOT read from this table -- see `hbm_gb` / `dram_gb` below. The
    vintage table owns power and performance; demand_ai.yaml owns memory content. One
    number, one home: duplicating them meant a scenario that scaled HBM GB/accelerator
    left the vintage table behind, and the two silently disagreed.
    """
    v = a.group("gpu_fleet.vintages")
    years = sorted(v)
    year = min(max(year, years[0]), years[-1])
    return v[year]


def hbm_gb(a: Assumptions, q: Quarter) -> float:
    """HBM per accelerator. Single source of truth, and it is scenario/slider-aware."""
    return interpolate_annual(a.series("demand_ai.hbm_gb_per_accelerator"), q)


def dram_gb(a: Assumptions, q: Quarter) -> float:
    """Conventional (non-HBM) DRAM per accelerator: host DDR5/LPDDR5X."""
    return interpolate_annual(a.series("demand_ai.conventional_dram_gb_per_accelerator"), q)


def desired_units(a: Assumptions, q: Quarter) -> float:
    """How many accelerators the money WANTS to buy this quarter.

    Derived from hyperscaler capex / accelerator ASP -- a chain that is entirely
    independent of power, which is precisely what makes it usable as the yardstick for
    whether power is actually scarce.
    """
    capex = interpolate_annual(a.series("demand_ai.hyperscaler_capex_usd_bn"), q) * 1e9
    share = interpolate_annual(a.series("demand_ai.accelerator_share_of_capex"), q)
    asp = interpolate_annual(a.series("demand_ai.avg_accelerator_asp_usd"), q)
    return (capex * share / asp) / 4.0 if asp > 0 else 0.0


def packaging_feasible_units(a: Assumptions, q: Quarter) -> float:
    """C6. TSMC CoWoS: an accelerator with no interposer to sit on does not exist."""
    kwpm = interpolate_annual(a.series("constraints.advanced_packaging.cowos_wafers_kwpm"), q)
    per_wafer = interpolate_annual(
        a.series("constraints.advanced_packaging.accelerators_per_cowos_wafer"), q
    )
    return kwpm * 1000.0 * MONTHS_PER_QUARTER * per_wafer


def _perf_tflops(spec: dict) -> float:
    return spec["tflops_per_watt"] * spec["kw_per_unit"] * 1000.0


def _annual_revenue(a: Assumptions, spec: dict, q: Quarter) -> float:
    rev_per_tflop = interpolate_annual(
        a.series("gpu_fleet.economics.revenue_per_tflop_year_usd"), q
    )
    util = a.scalar("gpu_fleet.economics.utilisation")
    return _perf_tflops(spec) * rev_per_tflop * util


def _annual_cost(a: Assumptions, spec: dict, q: Quarter) -> float:
    kwh = interpolate_annual(a.series("gpu_fleet.economics.electricity_usd_per_kwh"), q)
    pue = a.scalar("gpu_fleet.economics.pue")
    hosting = a.scalar("gpu_fleet.economics.hosting_usd_per_kw_year")
    kw = spec["kw_per_unit"]
    return kw * (8760.0 * kwh * pue + hosting)


def is_cash_viable(a: Assumptions, vintage_year: int, q: Quarter) -> bool:
    spec = _vintage(a, vintage_year)
    return _annual_revenue(a, spec, q) >= _annual_cost(a, spec, q)


def is_power_viable(a: Assumptions, vintage_year: int, q: Quarter, frontier_ppw: float) -> bool:
    """Is this vintage worth the watt it occupies, given what a new chip would do with it?"""
    thr = a.scalar("gpu_fleet.power_eviction.efficiency_threshold")
    spec = _vintage(a, vintage_year)
    if frontier_ppw <= 0:
        return True
    return spec["tflops_per_watt"] >= thr * frontier_ppw


def retirement_dates(a: Assumptions, timeline: list[Quarter]) -> dict[int, dict]:
    """When each vintage dies, by each rule. A diagnostic worth reading on its own:
    the spread between the two columns is the whole 'profitable but not worth the watt'
    argument, quantified."""
    out: dict[int, dict] = {}
    for vy in sorted(a.group("gpu_fleet.vintages")):
        cash = None
        evict = None
        for q in timeline:
            if q.year < vy:
                continue
            frontier = _vintage(a, q.year)["tflops_per_watt"]
            if cash is None and not is_cash_viable(a, vy, q):
                cash = q.label
            if evict is None and not is_power_viable(a, vy, q, frontier):
                evict = q.label
        out[vy] = {
            "cash_unviable": cash,
            "power_evicted": evict,
            "tflops_per_watt": _vintage(a, vy)["tflops_per_watt"],
            "hbm_gb": round(hbm_gb(a, Quarter(vy, 3))),
        }
    return out


def fleet_series(a: Assumptions, timeline: list[Quarter],
                 power: list[PowerQuarter],
                 supply_cap_units: dict[str, float] | None = None) -> list[FleetQuarter]:
    """Evolve the fleet quarter by quarter.

    supply_cap_units: optional ceiling on units shippable per quarter (e.g. CoWoS /
    advanced-packaging limited). Demand for accelerators can exceed what TSMC can
    package, and when it does the fleet simply cannot be refreshed as fast as the
    economics want.
    """
    max_life = a.scalar("gpu_fleet.max_life_years")
    ramp = max(int(a.scalar("gpu_fleet.power_eviction.retirement_ramp_quarters")), 1)
    # Datacentre GW is FACILITY power; the vintage table is CHIP power. Conflating them
    # overstates how many accelerators a gigawatt can hold by ~55%.
    overhead = a.scalar("datacenter.facility_overhead")

    def facility_kw(vy: int) -> float:
        return _vintage(a, vy)["kw_per_unit"] * overhead

    units: dict[int, float] = {}
    # Cohorts already condemned, being decommissioned over `ramp` quarters. A datacentre
    # does not rip out a hall overnight.
    retiring: dict[int, int] = {}

    out: list[FleetQuarter] = []

    # Scarcity is judged on the PREVIOUS quarter's verdict, because this quarter's
    # eviction decision has to be made before we know how many chips we can ship (the
    # retirements are what free the watts). Seeded False: at t=0 the fleet is empty.
    scarce = False

    for pq in power:
        q = pq.quarter
        frontier_spec = _vintage(a, q.year)
        frontier_ppw = frontier_spec["tflops_per_watt"]
        available = pq.cumulative_gw

        # ---- condemn cohorts -------------------------------------------------
        for vy in list(units):
            if vy in retiring:
                continue
            age = q.year - vy
            doomed = (
                age >= max_life
                or not is_cash_viable(a, vy, q)
                # Eviction only applies when power is genuinely scarce -- i.e. when the
                # world WANTS more accelerators than the grid can run. If there are
                # spare watts, an old GPU is costing nobody anything and gets to live.
                or (scarce and not is_power_viable(a, vy, q, frontier_ppw))
            )
            if doomed:
                retiring[vy] = ramp

        retired_units = 0.0
        retired_power_gw = 0.0
        for vy in list(retiring):
            left = retiring[vy]
            take = units.get(vy, 0.0) / left if left > 0 else units.get(vy, 0.0)
            take = min(take, units.get(vy, 0.0))
            units[vy] = units.get(vy, 0.0) - take
            retired_units += take
            retired_power_gw += take * facility_kw(vy) / 1e6
            retiring[vy] = left - 1
            if retiring[vy] <= 0 or units[vy] <= 1e-6:
                units.pop(vy, None)
                retiring.pop(vy, None)

        # ---- the demand-side constraint stack ---------------------------------
        # Shipments are min() over three ceilings, and we report which one binds --
        # exactly as the supply side does. Previously the fleet simply refilled all
        # available headroom, which meant it ALWAYS consumed 100% of available power by
        # construction, and "is power scarce?" degenerated into "is the buildout
        # decelerating?". You cannot detect scarcity with a fleet that is defined to
        # expand into whatever space it is given. You need something that wants more.
        fleet_power_gw = sum(n * facility_kw(vy) / 1e6 for vy, n in units.items())
        headroom_gw = max(available - fleet_power_gw, 0.0)
        new_kw = facility_kw(q.year)

        power_units = headroom_gw * 1e6 / new_kw if new_kw > 0 else 0.0
        want_units = desired_units(a, q)            # what the money wants
        pack_units = packaging_feasible_units(a, q)  # what TSMC can package
        if supply_cap_units is not None:
            pack_units = min(pack_units, supply_cap_units.get(q.label, float("inf")))

        ceilings = {
            "capex": want_units,
            "power": power_units,
            "packaging": pack_units,
        }
        binding = min(ceilings, key=lambda k: ceilings[k])
        shipments = max(ceilings[binding], 0.0)

        # Power is scarce iff it is what is stopping us buying more -- a judgement made
        # against an INDEPENDENT yardstick (capex), not against the fleet's own appetite.
        scarce = power_units < want_units

        # Never ship into a cohort that is being decommissioned: that pool would never
        # drain, and the retire loop would keep taking 1/left of a set that keeps growing.
        target_vintage = q.year if q.year not in retiring else q.year - 1
        units[target_vintage] = units.get(target_vintage, 0.0) + shipments
        fleet_power_gw = sum(n * facility_kw(vy) / 1e6 for vy, n in units.items())

        out.append(FleetQuarter(
            quarter=q,
            units_by_vintage=dict(units),
            shipments=shipments,
            retirements=retired_units,
            replacement_share=_replacement_share(shipments, new_kw, retired_power_gw),
            retired_power_gw=retired_power_gw,
            desired_units=want_units,
            power_feasible_units=power_units,
            packaging_feasible_units=pack_units,
            binding_demand_constraint=binding,
            fleet_units=sum(units.values()),
            fleet_power_gw=fleet_power_gw,
            available_power_gw=available,
            power_scarce=scarce,
            hbm_gb_shipped=shipments * hbm_gb(a, q),
            dram_gb_shipped=shipments * dram_gb(a, q),
            frontier_tflops_per_watt=frontier_ppw,
        ))

    return out


def _replacement_share(shipments: float, new_kw: float, retired_power_gw: float) -> float:
    """What fraction of this quarter's shipments merely refills watts a retirement freed?

    Measured in WATTS, not units, because units are not comparable across generations:
    one new chip can replace several old ones and still draw more power than all of them
    put together.

    This is the memory demand that would still exist in a world where datacentre power
    stopped growing entirely -- the piece an exogenous shipments series cannot see.

    (The previous version inferred the freed watts by differencing cumulative available
    power, which only worked while the fleet was defined to consume 100% of it. Now that
    shipments can be capex- or packaging-limited, that identity no longer holds, so the
    retired power is tracked directly.)
    """
    shipped_gw = shipments * new_kw / 1e6
    if shipped_gw <= 0:
        return 0.0
    return min(retired_power_gw / shipped_gw, 1.0)
