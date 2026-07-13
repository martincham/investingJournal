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
Crucially, eviction only switches on when the fleet is actually up against its power
ceiling -- so the mechanism has to earn its own relevance rather than being assumed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .calendar import Quarter, interpolate_annual
from .config import Assumptions
from .datacenter import PowerQuarter


@dataclass
class FleetQuarter:
    quarter: Quarter
    units_by_vintage: dict[int, float] = field(default_factory=dict)

    shipments: float = 0.0            # units this quarter
    retirements: float = 0.0          # units retired this quarter
    replacement_share: float = 0.0    # what fraction of shipments merely refill freed watts

    fleet_units: float = 0.0
    fleet_power_gw: float = 0.0
    available_power_gw: float = 0.0
    power_scarce: bool = False

    hbm_gb_shipped: float = 0.0
    dram_gb_shipped: float = 0.0

    frontier_tflops_per_watt: float = 0.0


def _vintage(a: Assumptions, year: int) -> dict:
    """Spec for a cohort. Clamped to the roadmap's range: a 2033 quarter still ships
    the 2032 vintage rather than exploding."""
    v = a.group("gpu_fleet.vintages")
    years = sorted(v)
    year = min(max(year, years[0]), years[-1])
    return v[year]


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
            "hbm_gb": _vintage(a, vy)["hbm_gb"],
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
    scarcity_trigger = a.scalar("gpu_fleet.power_eviction.scarcity_trigger")
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

    for pq in power:
        q = pq.quarter
        frontier_spec = _vintage(a, q.year)
        frontier_ppw = frontier_spec["tflops_per_watt"]

        fleet_power_gw = sum(n * facility_kw(vy) / 1e6 for vy, n in units.items())
        available = pq.cumulative_gw
        scarce = available > 0 and (fleet_power_gw / available) >= scarcity_trigger

        # ---- condemn cohorts -------------------------------------------------
        for vy in list(units):
            if vy in retiring:
                continue
            age = q.year - vy
            doomed = (
                age >= max_life
                or not is_cash_viable(a, vy, q)
                # Eviction only applies when power is genuinely scarce. If there are
                # spare watts, an old GPU costs nobody anything and gets to live.
                or (scarce and not is_power_viable(a, vy, q, frontier_ppw))
            )
            if doomed:
                retiring[vy] = ramp

        retired_units = 0.0
        for vy in list(retiring):
            left = retiring[vy]
            take = units.get(vy, 0.0) / left if left > 0 else units.get(vy, 0.0)
            take = min(take, units.get(vy, 0.0))
            units[vy] = units.get(vy, 0.0) - take
            retired_units += take
            retiring[vy] = left - 1
            if retiring[vy] <= 0 or units[vy] <= 1e-6:
                units.pop(vy, None)
                retiring.pop(vy, None)

        # ---- refill the freed watts + whatever new power arrived --------------
        fleet_power_gw = sum(n * facility_kw(vy) / 1e6 for vy, n in units.items())
        headroom_gw = max(available - fleet_power_gw, 0.0)
        new_kw = facility_kw(q.year)
        shipments = headroom_gw * 1e6 / new_kw if new_kw > 0 else 0.0

        if supply_cap_units is not None:
            shipments = min(shipments, supply_cap_units.get(q.label, float("inf")))

        units[q.year] = units.get(q.year, 0.0) + shipments
        fleet_power_gw = sum(n * facility_kw(vy) / 1e6 for vy, n in units.items())

        out.append(FleetQuarter(
            quarter=q,
            units_by_vintage=dict(units),
            shipments=shipments,
            retirements=retired_units,
            replacement_share=0.0,   # filled in by _annotate_replacement_share below
            fleet_units=sum(units.values()),
            fleet_power_gw=fleet_power_gw,
            available_power_gw=available,
            power_scarce=scarce,
            hbm_gb_shipped=shipments * frontier_spec["hbm_gb"],
            dram_gb_shipped=shipments * frontier_spec["dram_gb"],
            frontier_tflops_per_watt=frontier_ppw,
        ))

    _annotate_replacement_share(a, out)
    return out


def _annotate_replacement_share(a: Assumptions, series: list[FleetQuarter]) -> None:
    """Split each quarter's shipments into 'refilling freed watts' vs 'genuinely new'.

    Measured in WATTS, not units, because units are not comparable across generations:
    one new chip can replace several old ones and still draw more power than all of them
    put together.

    A quarter's new power is `growth_gw`. Anything shipped beyond that is refilling watts
    that a retirement freed up. That residual is the replacement stream -- the memory
    demand that would still exist in a world where datacentre power stopped growing
    entirely, and the thing an exogenous shipments series cannot see.
    """
    overhead = a.scalar("datacenter.facility_overhead")
    for i, f in enumerate(series):
        shipped_gw = f.shipments * _vintage(a, f.quarter.year)["kw_per_unit"] * overhead / 1e6
        if shipped_gw <= 0:
            f.replacement_share = 0.0
            continue
        prev_available = series[i - 1].available_power_gw if i else 0.0
        growth_gw = max(f.available_power_gw - prev_available, 0.0)
        replacement_gw = max(shipped_gw - growth_gw, 0.0)
        f.replacement_share = min(replacement_gw / shipped_gw, 1.0)
