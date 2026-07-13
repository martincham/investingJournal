"""Supply: wafers in, bits out, through the tightest of six bottlenecks.

The structure that matters here is that supply is a min() over competing ceilings and
the model reports WHICH one binds each quarter. Two families of ceiling, and they do
different things:

  WAFER ceilings (C1 cleanroom, C2 litho, C3 other WFE) cap total DRAM wafer starts.

  HBM ceilings (C4 back-end, C5 test, C6 CoWoS packaging) cap HBM bits specifically.
  When one of these binds, the wafers HBM would have used flow back to commodity DRAM
  -- which is ~2.85x more bit-efficient per wafer. So an HBM bottleneck RAISES total
  DRAM bit output while leaving AI demand unserved.

That asymmetry is why "what is the bottleneck" has no single answer: the constraint on
total bits and the constraint on AI-usable bits are different constraints, and the
model tracks both.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import actuals, units
from .calendar import Quarter, interpolate_annual, s_curve
from .config import Assumptions

WAFER_CONSTRAINTS = {
    "C1_wafer_capacity": "Installed cleanroom / wafer capacity",
    "C2_lithography": "EUV/DUV scanner availability",
    "C3_other_wfe": "HAR etch / depo / implant (Lam, TEL, AMAT)",
}

HBM_CONSTRAINTS = {
    "C4_hbm_backend": "TSV, thinning, bonding, known-good-die",
    "C5_test": "HBM test capacity (Advantest/Teradyne)",
    "C6_advanced_packaging": "TSMC CoWoS interposer capacity",
}

MONTHS_PER_QUARTER = 3


@dataclass
class SupplyQuarter:
    quarter: Quarter

    # DRAM, in bits
    dram_total_bits: float = 0.0
    dram_commodity_bits: float = 0.0
    dram_hbm_bits: float = 0.0
    dram_china_bits: float = 0.0

    # NAND, in bits
    nand_total_bits: float = 0.0
    nand_china_bits: float = 0.0

    # Which ceiling actually bound, and by how much
    wafer_ceilings_kwspm: dict[str, float] = field(default_factory=dict)
    binding_wafer_constraint: str = ""
    wafer_margin_to_next: float = 0.0

    hbm_ceilings_bits: dict[str, float] = field(default_factory=dict)
    binding_hbm_constraint: str = ""
    hbm_is_capped: bool = False

    installed_kwspm: float = 0.0
    hbm_wafer_share: float = 0.0
    is_actual: bool = False

    @property
    def dram_eb(self) -> float:
        return units.bits_to_eb(self.dram_total_bits)

    @property
    def nand_eb(self) -> float:
        return units.bits_to_eb(self.nand_total_bits)

    @property
    def hbm_eb(self) -> float:
        return units.bits_to_eb(self.dram_hbm_bits)


def _sum_capacity(a: Assumptions, group_path: str, q: Quarter) -> dict[str, float]:
    group = a.group(group_path)
    return {name: interpolate_annual(asm.value, q) for name, asm in group.items()}


def _litho_ceiling_kwspm(a: Assumptions, q: Quarter, installed_kwspm: float) -> float:
    """C2. The 'ASML is the limiting factor' hypothesis, made arithmetic.

    One EUV scanner delivers ~104,000 wafer-LAYERS/month. A DRAM wafer needing L EUV
    layers therefore consumes L of those, so fleet x throughput / L = the wafer starts
    EUV can support.

    The part a naive version of this gets wrong: MOST DRAM WAFERS NEVER TOUCH AN EUV
    SCANNER. DRAM only started using EUV around 2020, and legacy nodes, DDR4, niche
    DRAM and every single CXMT wafer are pure DUV multipatterning. So the EUV ceiling
    applies only to the EUV-dependent share of capacity; the rest is limited by
    cleanroom and etch, not by ASML.

        ceiling = (wafers that need no EUV) + (wafers EUV can support)

    This is the arithmetic that decides whether the "ASML is the bottleneck" claim is
    actually true, rather than assuming it.
    """
    scanners = interpolate_annual(a.series("constraints.litho.euv_scanners_available_to_memory"), q)
    per_scanner = a.scalar("constraints.litho.wafer_layers_per_scanner_month")
    layers = max(interpolate_annual(a.series("constraints.litho.euv_layers_per_dram_wafer"), q), 0.1)
    euv_share = interpolate_annual(
        a.series("constraints.litho.euv_dependent_share_of_dram_wafers"), q
    )

    euv_supportable_kwspm = scanners * per_scanner / layers / 1000.0
    non_euv_kwspm = installed_kwspm * (1.0 - euv_share)
    return non_euv_kwspm + euv_supportable_kwspm


def _hbm_ceilings_bits(a: Assumptions, q: Quarter) -> dict[str, float]:
    """C4, C5, C6 -- all converted to a ceiling on HBM bits produced this quarter."""
    backend_eb_yr = interpolate_annual(a.series("constraints.hbm_backend.max_hbm_bits_eb_per_year"), q)
    test_eb_yr = interpolate_annual(a.series("constraints.test.max_hbm_bits_eb_per_year"), q)

    # CoWoS gates how much HBM can be *consumed*: an HBM stack with no interposer to
    # sit on is inventory, not supply.
    cowos_kwpm = interpolate_annual(a.series("constraints.advanced_packaging.cowos_wafers_kwpm"), q)
    accel_per_wafer = interpolate_annual(
        a.series("constraints.advanced_packaging.accelerators_per_cowos_wafer"), q
    )
    hbm_gb_per_accel = interpolate_annual(a.series("demand_ai.hbm_gb_per_accelerator"), q)
    accelerators_per_quarter = cowos_kwpm * 1000.0 * MONTHS_PER_QUARTER * accel_per_wafer
    cowos_bits = units.gb_to_bits(accelerators_per_quarter * hbm_gb_per_accel)

    return {
        "C4_hbm_backend": units.eb_to_bits(backend_eb_yr / 4.0),
        "C5_test": units.eb_to_bits(test_eb_yr / 4.0),
        "C6_advanced_packaging": cowos_bits,
    }


def _three_d_dram_uplift(a: Assumptions, q: Quarter) -> float:
    """S24. The regime break, phased in over ~4 years once it starts.

    Multiplies bits/wafer. Before first volume it is 1.0 and changes nothing.
    """
    first_year = int(a.value("tech_roadmap.three_d_dram.first_volume_year"))
    uplift = a.scalar("tech_roadmap.three_d_dram.density_uplift")
    start = Quarter(first_year, 1)
    return 1.0 + uplift * s_curve(q, start, ramp_quarters=16)


def supply_quarter(a: Assumptions, q: Quarter) -> SupplyQuarter:
    out = SupplyQuarter(quarter=q)

    # --- DRAM wafer ceilings: C1, C2, C3 ------------------------------------
    dram_caps = _sum_capacity(a, "supply_capacity.dram_wafer_capacity_kwspm", q)
    installed_kwspm = sum(dram_caps.values())
    cxmt_kwspm = dram_caps.get("cxmt", 0.0)

    ceilings = {
        "C1_wafer_capacity": installed_kwspm,
        "C2_lithography": _litho_ceiling_kwspm(a, q, installed_kwspm),
        "C3_other_wfe": interpolate_annual(
            a.series("constraints.other_wfe.dram_supportable_kwspm"), q
        ),
    }
    binding = min(ceilings, key=lambda k: ceilings[k])
    wafer_ceiling = ceilings[binding]
    others = sorted(v for k, v in ceilings.items() if k != binding)
    # How much slack is there behind the binding constraint? A bottleneck that binds
    # by 1% is a different world from one that binds by 30%: relieving the first just
    # exposes the next one immediately.
    margin = (others[0] / wafer_ceiling - 1.0) if others and wafer_ceiling > 0 else 0.0

    out.wafer_ceilings_kwspm = ceilings
    out.binding_wafer_constraint = binding
    out.wafer_margin_to_next = margin
    out.installed_kwspm = installed_kwspm

    # --- Losses: utilisation, the shrink tax, disruption ---------------------
    util = interpolate_annual(a.series("supply_capacity.utilisation.dram"), q)
    conv_loss = interpolate_annual(a.series("supply_capacity.node_conversion_loss.dram"), q)
    disruption = interpolate_annual(a.series("supply_capacity.disruption_haircut"), q)
    effective_kwspm = wafer_ceiling * util * (1.0 - conv_loss) * (1.0 - disruption)

    wafers = effective_kwspm * 1000.0 * MONTHS_PER_QUARTER
    china_wafer_frac = (cxmt_kwspm / installed_kwspm) if installed_kwspm > 0 else 0.0

    # --- Density -------------------------------------------------------------
    gb_per_wafer = interpolate_annual(a.series("tech_roadmap.dram_gb_per_wafer"), q)
    gb_per_wafer *= _three_d_dram_uplift(a, q)
    cxmt_discount = interpolate_annual(a.series("tech_roadmap.cxmt_density_discount"), q)
    trade_ratio = interpolate_annual(a.series("tech_roadmap.hbm_trade_ratio"), q)
    hbm_share = interpolate_annual(a.series("tech_roadmap.hbm_wafer_share"), q)
    out.hbm_wafer_share = hbm_share

    # --- HBM allocation, then the HBM-specific ceilings ---------------------
    # CXMT makes no meaningful HBM: no EUV, no advanced-packaging access, no HBM
    # customers. So the HBM share applies to the EX-CHINA wafer pool only.
    #
    # Getting this wrong (applying the share to the global pool) has an absurd
    # consequence that a test caught: a CXMT ramp would make Samsung/SK/Micron
    # "produce more HBM", because CXMT's wafers would be inflating the base that the
    # HBM percentage is taken from.
    china_wafers = wafers * china_wafer_frac
    row_wafers = wafers - china_wafers
    hbm_wafers_desired = row_wafers * hbm_share

    hbm_bits_desired = units.gb_to_bits(hbm_wafers_desired * gb_per_wafer / trade_ratio)

    hbm_ceilings = _hbm_ceilings_bits(a, q)
    hbm_binding = min(hbm_ceilings, key=lambda k: hbm_ceilings[k])
    hbm_ceiling = hbm_ceilings[hbm_binding]

    hbm_bits = min(hbm_bits_desired, hbm_ceiling)
    out.hbm_ceilings_bits = hbm_ceilings
    out.binding_hbm_constraint = hbm_binding if hbm_bits < hbm_bits_desired else ""
    out.hbm_is_capped = hbm_bits < hbm_bits_desired * 0.999

    # Wafers HBM actually used. If a back-end/test/packaging ceiling bound, the
    # surplus wafers go back to commodity -- where they are ~2.85x more productive.
    hbm_wafers_used = units.bits_to_gb(hbm_bits) * trade_ratio / gb_per_wafer if gb_per_wafer else 0.0

    commodity_wafers = wafers - hbm_wafers_used
    china_commodity_wafers = min(china_wafers, commodity_wafers)
    row_commodity_wafers = commodity_wafers - china_commodity_wafers

    china_bits = units.gb_to_bits(china_commodity_wafers * gb_per_wafer * cxmt_discount)
    row_commodity_bits = units.gb_to_bits(row_commodity_wafers * gb_per_wafer)

    out.dram_hbm_bits = hbm_bits
    out.dram_china_bits = china_bits
    out.dram_commodity_bits = row_commodity_bits + china_bits
    out.dram_total_bits = out.dram_commodity_bits + hbm_bits
    units.assert_global_scale(out.dram_total_bits, f"DRAM supply {q.label}")

    # --- NAND ---------------------------------------------------------------
    nand_caps = _sum_capacity(a, "supply_capacity.nand_wafer_capacity_kwspm", q)
    nand_installed = sum(nand_caps.values())
    nand_ceiling = min(
        nand_installed,
        interpolate_annual(a.series("constraints.other_wfe.nand_supportable_kwspm"), q),
    )
    nand_util = interpolate_annual(a.series("supply_capacity.utilisation.nand"), q)
    nand_loss = interpolate_annual(a.series("supply_capacity.node_conversion_loss.nand"), q)
    nand_effective = nand_ceiling * nand_util * (1.0 - nand_loss) * (1.0 - disruption)
    nand_wafers = nand_effective * 1000.0 * MONTHS_PER_QUARTER
    tb_per_wafer = interpolate_annual(a.series("tech_roadmap.nand_tb_per_wafer"), q)

    out.nand_total_bits = units.tb_to_bits(nand_wafers * tb_per_wafer)
    ymtc_frac = (nand_caps.get("ymtc", 0.0) / nand_installed) if nand_installed else 0.0
    out.nand_china_bits = out.nand_total_bits * ymtc_frac
    units.assert_global_scale(out.nand_total_bits, f"NAND supply {q.label}")

    return out


def _apply_actuals(a: Assumptions, s: SupplyQuarter) -> SupplyQuarter:
    """Reality overrides the model through 2026Q2.

    Supply is observable -- bits were produced, the number exists -- so for those
    quarters we report what happened, not what the model thinks would have happened.
    The model still computes them (that is the backcast, and it is how we find out
    whether the machinery works), but the reported line is the measured one.

    The HBM/commodity SPLIT is not separately observed, so it is preserved from the
    model and rescaled to the observed total. Honest: the total is measured, the mix
    is inferred.
    """
    observed = actuals.dram_supply_bits(a, s.quarter)
    if observed is not None and s.dram_total_bits > 0:
        scale = observed / s.dram_total_bits
        s.dram_total_bits = observed
        s.dram_commodity_bits *= scale
        s.dram_hbm_bits *= scale
        s.dram_china_bits *= scale
        s.is_actual = True

    observed_nand = actuals.nand_supply_bits(a, s.quarter)
    if observed_nand is not None and s.nand_total_bits > 0:
        scale = observed_nand / s.nand_total_bits
        s.nand_total_bits = observed_nand
        s.nand_china_bits *= scale
        s.is_actual = True

    return s


def supply_series(a: Assumptions, timeline: list[Quarter]) -> list[SupplyQuarter]:
    return [_apply_actuals(a, supply_quarter(a, q)) for q in timeline]
