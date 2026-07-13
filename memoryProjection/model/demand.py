"""Demand: bits the world would consume at constant 2025 real prices.

The definition matters and is easy to get wrong. Realised bits shipped ALWAYS equal
bits produced -- the market clears. So a demand line built from realised shipments is
just the supply line wearing a hat, and it would show equilibrium forever.

What we build instead is UNRATIONED demand: what buyers would take if memory still
cost what it cost in 2025. That is why the conventional segments use TREND content
per unit (the 32GB AI PC, the 16GB phone) rather than the cut-down configurations
OEMs are actually shipping in 2026 while memory is unaffordable. Those cuts ARE the
shortage. Subtracting them from demand would define away the thing we are measuring.

The gap this produces is therefore a PRESSURE INDEX, not a forecast of physical
shortfall. It says how hard prices and rationing have to work, not how many bits go
missing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import actuals, units
from .calendar import Quarter, interpolate_annual
from .config import Assumptions
from .datacenter import power_series
from .fleet import FleetQuarter, fleet_series

CONSUMER_SEGMENTS = {"pc", "smartphone", "graphics", "console"}


@dataclass
class DemandQuarter:
    quarter: Quarter

    dram_by_segment: dict[str, float] = field(default_factory=dict)  # bits
    nand_by_segment: dict[str, float] = field(default_factory=dict)  # bits

    dram_total_bits: float = 0.0
    nand_total_bits: float = 0.0
    dram_china_bits: float = 0.0
    nand_china_bits: float = 0.0

    # Diagnostics
    accelerators: float = 0.0
    accelerators_before_power_cap: float = 0.0
    power_capped: bool = False
    efficiency_multiplier: float = 1.0
    kv_working_set_bits: float = 0.0
    capex_implied_accelerators: float = 0.0

    # Fleet diagnostics -- shipments are now an OUTPUT of the fleet, not an input
    retirements: float = 0.0
    replacement_share: float = 0.0
    fleet_units: float = 0.0
    fleet_power_gw: float = 0.0
    available_power_gw: float = 0.0
    is_actual: bool = False

    @property
    def dram_eb(self) -> float:
        return units.bits_to_eb(self.dram_total_bits)

    @property
    def nand_eb(self) -> float:
        return units.bits_to_eb(self.nand_total_bits)


def _seasonal(a: Assumptions, q: Quarter, segment: str) -> float:
    if segment not in CONSUMER_SEGMENTS:
        return 1.0  # Datacenters do not have a holiday season.
    mult = a.value("demand_conventional.seasonality.consumer_quarterly_multiplier")
    return float(mult[q.q])


def _efficiency_multiplier(a: Assumptions, q: Quarter, base_year: int = 2025) -> float:
    """D20. Cumulative fall in bits per unit of delivered intelligence.

    Compounds forward from the base year. This is the single largest force that could
    close the gap without a single new fab being built, so it is applied honestly and
    exposed as the first slider rather than buried.
    """
    deflator = a.series("demand_ai.efficiency_deflator_annual")
    mult = 1.0
    step = 0.25  # quarterly compounding
    y = base_year
    while y < q.fractional_year:
        rate = interpolate_annual(deflator, Quarter(int(y), min(4, int((y % 1) * 4) + 1)))
        mult *= (1.0 - rate) ** step
        y += step
    return mult


def _kv_working_set_bits(a: Assumptions, q: Quarter) -> float:
    """D6. The KV-cache sub-model: 'token demand is real', in bytes.

    peak concurrent sessions x active context length x KV bytes per token.

    Worth being honest about what this shows. It is the reason HBM PER ACCELERATOR has
    to keep climbing -- it is what forces 288GB and then 1TB packages. But at global
    aggregate it is a modest number of exabytes, because model weights and batch
    activations dominate the HBM footprint, and because bytes-per-token is falling
    (GQA/MLA/quantised KV) nearly as fast as context length is rising.

    So it is NOT added to HBM demand -- that would double-count against
    hbm_gb_per_accelerator. It is used as a cross-check, and it drives the DRAM and
    NAND offload tiers, which ARE additive.
    """
    sessions = interpolate_annual(a.series("demand_ai.kv_cache.peak_concurrent_sessions_millions"), q) * 1e6
    context = interpolate_annual(a.series("demand_ai.kv_cache.avg_active_context_tokens"), q)
    kb_per_token = interpolate_annual(a.series("demand_ai.kv_cache.kv_kb_per_token"), q)
    bytes_total = sessions * context * kb_per_token * 1e3
    return bytes_total * units.BITS_PER_BYTE


def demand_quarter(a: Assumptions, q: Quarter, f: FleetQuarter) -> DemandQuarter:
    out = DemandQuarter(quarter=q)
    dram: dict[str, float] = {}
    nand: dict[str, float] = {}
    out.is_actual = actuals.is_actual(a, q)

    # ---------------- AI / datacentre ----------------------------------------
    # Accelerator shipments are an OUTPUT of the fleet model, not an assumption:
    #
    #     shipments = (new datacentre power) / kW  +  (power freed by retirements) / kW
    #
    # The second term is replacement demand, and it is the piece an exogenous shipments
    # series cannot see. Retiring an A100 (80GB, 0.4kW) and refilling its watt with a
    # Rubin Ultra (~1TB, 1.45kW) is a large HBM purchase for ZERO net growth in power.
    out.accelerators_before_power_cap = f.shipments
    out.retirements = f.retirements
    out.replacement_share = f.replacement_share
    out.fleet_units = f.fleet_units
    out.fleet_power_gw = f.fleet_power_gw
    out.available_power_gw = f.available_power_gw
    out.power_capped = f.power_scarce

    # Through 2026Q2 the observed shipment count wins over the model's.
    accel_q = actuals.accelerator_units(a, q)
    if accel_q is None:
        accel_q = f.shipments
    out.accelerators = accel_q

    eff = _efficiency_multiplier(a, q)
    out.efficiency_multiplier = eff

    # Memory content comes from the vintage actually being shipped this quarter, so the
    # HBM step-ups (192 -> 288 -> ~1TB) are tied to the fleet's generation, not to a
    # free-floating series.
    hbm_gb = interpolate_annual(a.series("demand_ai.hbm_gb_per_accelerator"), q)
    host_gb = interpolate_annual(a.series("demand_ai.conventional_dram_gb_per_accelerator"), q)
    nand_tb = interpolate_annual(a.series("demand_ai.nand_tb_per_accelerator"), q)

    dram["hbm"] = units.gb_to_bits(accel_q * hbm_gb) * eff
    dram["ai_server_host"] = units.gb_to_bits(accel_q * host_gb) * eff
    nand["ai_essd"] = units.tb_to_bits(accel_q * nand_tb)

    # KV-cache offload tiers (additive; the primary KV cache lives in HBM above).
    kv_bits = _kv_working_set_bits(a, q)
    out.kv_working_set_bits = kv_bits
    dram_off = interpolate_annual(a.series("demand_ai.kv_cache.offload_to_dram_share"), q)
    nand_off = interpolate_annual(a.series("demand_ai.kv_cache.offload_to_nand_share"), q)
    dram["kv_offload"] = kv_bits * dram_off * eff
    nand["kv_offload"] = kv_bits * nand_off

    # Top-down cross-check on the bottom-up accelerator count.
    capex = interpolate_annual(a.series("demand_ai.hyperscaler_capex_usd_bn"), q) * 1e9
    accel_share = interpolate_annual(a.series("demand_ai.accelerator_share_of_capex"), q)
    asp = interpolate_annual(a.series("demand_ai.avg_accelerator_asp_usd"), q)
    out.capex_implied_accelerators = (capex * accel_share / asp) / 4.0 if asp > 0 else 0.0

    # ---------------- Conventional -------------------------------------------
    for seg in ("servers_traditional", "pc", "smartphone"):
        # Observed unit shipments win through 2026Q2. Note these are ALREADY rationed
        # outcomes -- IDC attributes the 1Q26 smartphone decline directly to memory
        # constraints -- but they are what shipped, and the demand line's job is to say
        # what those buyers WOULD have taken at 2025 prices. Hence: actual units, TREND
        # content per unit.
        u = actuals.conventional_units(a, seg, q)
        if u is None:
            u = interpolate_annual(
                a.series(f"demand_conventional.{seg}.units_millions"), q
            ) * 1e6 / 4.0
            u *= _seasonal(a, q, seg)
        gb = interpolate_annual(a.series(f"demand_conventional.{seg}.dram_gb_per_unit"), q)
        tb = interpolate_annual(a.series(f"demand_conventional.{seg}.nand_tb_per_unit"), q)
        dram[seg] = units.gb_to_bits(u * gb)
        nand[seg] = units.tb_to_bits(u * tb)

    for seg, path in (
        ("graphics", "demand_conventional.graphics.dram_eb_per_year"),
        ("console", "demand_conventional.console.dram_eb_per_year"),
        ("auto_industrial_iot", "demand_conventional.automotive_industrial_iot.dram_eb_per_year"),
        ("other", "demand_conventional.other_dram_eb_per_year"),
    ):
        eb_yr = interpolate_annual(a.series(path), q)
        dram[seg] = units.eb_to_bits(eb_yr / 4.0) * _seasonal(a, q, seg)

    for seg, path in (
        ("auto_industrial_iot", "demand_conventional.automotive_industrial_iot.nand_eb_per_year"),
        ("other", "demand_conventional.other_nand_eb_per_year"),
    ):
        eb_yr = interpolate_annual(a.series(path), q)
        nand[seg] = units.eb_to_bits(eb_yr / 4.0)

    # D22. CXL pooling raises utilisation of ALREADY-INSTALLED DRAM, so it reduces
    # demand for NEW DRAM. A genuine force against the shortage, applied to the server
    # pools where pooling actually happens.
    cxl = interpolate_annual(a.series("demand_conventional.cxl_pooling_savings"), q)
    for seg in ("servers_traditional", "ai_server_host"):
        dram[seg] *= 1.0 - cxl

    # S30. Inventory. Customers and the channel buying ahead (or refusing to buy while
    # they work off a glut) is a real, large component of demand in any given quarter,
    # and it is what gives the memory cycle its amplitude. Can be negative.
    dram["inventory"] = units.eb_to_bits(
        interpolate_annual(a.series("demand_conventional.inventory_swing.dram_eb_per_year"), q) / 4.0
    )
    nand["inventory"] = units.eb_to_bits(
        interpolate_annual(a.series("demand_conventional.inventory_swing.nand_eb_per_year"), q) / 4.0
    )

    out.dram_by_segment = dram
    out.nand_by_segment = nand
    out.dram_total_bits = sum(dram.values())
    out.nand_total_bits = sum(nand.values())

    units.assert_global_scale(out.dram_total_bits, f"DRAM demand {q.label}")
    units.assert_global_scale(out.nand_total_bits, f"NAND demand {q.label}")

    # China's domestic demand pool -- the thing CXMT's output is netted against.
    out.dram_china_bits = units.eb_to_bits(
        interpolate_annual(a.series("china.domestic_dram_demand_eb_per_year"), q) / 4.0
    )
    out.nand_china_bits = units.eb_to_bits(
        interpolate_annual(a.series("china.domestic_nand_demand_eb_per_year"), q) / 4.0
    )
    return out


def demand_series(a: Assumptions, timeline: list[Quarter],
                  packaging_cap: dict[str, float] | None = None) -> list[DemandQuarter]:
    """Build the fleet once (it is path-dependent -- this quarter's fleet depends on last
    quarter's retirements), then read demand off it."""
    power = power_series(a, timeline)
    fleet = fleet_series(a, timeline, power, supply_cap_units=packaging_cap)
    return [demand_quarter(a, q, f) for q, f in zip(timeline, fleet)]
