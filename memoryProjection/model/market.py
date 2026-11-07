"""The industry DRAM price layer (Nov 2026). Inputs: assumptions/market.yaml.

Price, margin and revenue, projected forward from the last observed quarter. It reads the
model's two physical outputs (supply and the two demand lines) and never feeds back into
them: the gap stays a pressure index, and this layer says what that pressure does to price.

Why not solve for the clearing price directly? The two demand lines (at 2025 prices and at
2026Q3 prices) give an elasticity of about -0.1. At that elasticity a 5% error in
quantities moves the clearing price ~60%, and seasonal consumer demand alone swings it
$21-36/GB within 2027. The level is not identifiable from quantities that carry 5-15%
error. So the layer projects the PATH instead:

    ln P(t) = ln P(t-1) + kappa * (gap(t-1) at P(t-1) - baseline_offset)

starting from the observed price, with demand at the going price from the two-point
elasticity, kappa solved from one guide (the first projected quarter's price change), and
a budget ceiling: cloud providers' DRAM spend cannot exceed a share of their capex.
Without the ceiling the path compounds to 95% margins by 2030, because nothing in an
elasticity of -0.1 stops it. In reality buyers' budgets stop it.

All prices are real 2025 dollars per GB.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import actuals, units
from .calendar import Quarter, interpolate_annual
from .config import Assumptions

# Segments bought by cloud providers / datacentres: the ones the CSP budget pays for.
DATACENTRE_SEGMENTS = ("hbm", "ai_server_host", "kv_offload", "ai_cpu_server", "servers_traditional")


@dataclass
class MarketQuarter:
    quarter: Quarter
    is_actual: bool
    price_usd_per_gb: float
    shipped_eb: float
    revenue_usd_bn: float
    cost_usd_per_gb: float | None = None
    gross_margin: float | None = None
    gap_at_model_price: float | None = None
    budget_bound: bool = False
    price_ceiling_usd_per_gb: float | None = None


def _observed(a: Assumptions) -> dict[str, tuple[float, float]]:
    """quarter -> (revenue $bn, bits EB), for quarters with both observed."""
    rev = a.value("actuals.dram_industry_revenue_usd_bn")
    eb = a.value("actuals.dram_supply_eb_per_quarter")
    return {q: (float(rev[q]), float(eb[q])) for q in rev if q in eb}


def calibrate_kappa(central) -> float:
    """Adjustment speed, solved once on the CENTRAL run and shared by every scenario:
    it describes how the market moves, not the quantities the scenarios disagree about."""
    a = central.assumptions
    anchor = actuals.actuals_end(a)
    off = a.scalar("market.baseline_offset")
    guide = a.scalar("market.price_change_guide_first_projected_quarter")
    d, b = next((d, b) for q, d, b in zip(central.quarters, central.demand, central.dram)
                if q == anchor)
    gap_anchor = d.at_price.dram_total_bits / b.global_supply_bits - 1.0
    if gap_anchor <= off:
        raise ValueError(f"anchor at-price gap {gap_anchor:+.3f} is not above the offset; "
                         "the price-change guide cannot be calibrated from it")
    return math.log(1.0 + guide) / (gap_anchor - off)


def market_series(run, kappa: float) -> list[MarketQuarter]:
    a = run.assumptions
    obs = _observed(a)
    anchor = actuals.actuals_end(a)
    if anchor.label not in obs:
        raise KeyError(f"no observed revenue and bits for the anchor quarter {anchor}")

    p0 = sum(r for q, (r, _) in obs.items() if q.startswith("2025")) / \
        sum(e for q, (_, e) in obs.items() if q.startswith("2025"))   # 2025 average price
    p1 = obs[anchor.label][0] / obs[anchor.label][1]                    # anchor price
    off = a.scalar("market.baseline_offset")
    gm0 = a.scalar("market.gross_margin_at_anchor")
    gm_floor = a.scalar("market.gross_margin_floor")
    capex = a.series("demand_ai.hyperscaler_capex_usd_bn")
    budget_2027 = (a.scalar("market.csp_capex_nominal_2027_usd_bn")
                   * a.scalar("market.memory_share_of_csp_capex_max")
                   * a.scalar("market.dram_share_of_memory_spend"))     # $bn/yr in 2027

    rows = list(zip(run.quarters, run.supply, run.demand, run.dram))
    i_anchor = next(i for i, (q, *_) in enumerate(rows) if q == anchor)
    _, s_a, d_a, b_a = rows[i_anchor]
    gap_anchor = d_a.at_price.dram_total_bits / b_a.global_supply_bits - 1.0
    bpw_anchor = s_a.dram_total_bits / s_a.installed_kwspm
    cost_anchor = p1 * (1.0 - gm0)

    out: list[MarketQuarter] = []
    for q, s, d, b in rows[: i_anchor + 1]:
        if q.label in obs:
            r, e = obs[q.label]
            out.append(MarketQuarter(q, True, r / e, e, r))
    out[-1].cost_usd_per_gb, out[-1].gross_margin = cost_anchor, gm0
    out[-1].gap_at_model_price = gap_anchor

    price, gap_prev = p1, gap_anchor
    for q, s, d, b in rows[i_anchor + 1:]:
        supply = b.global_supply_bits
        eps = math.log(d.at_price.dram_total_bits / d.dram_total_bits) / math.log(p1 / p0)

        price *= math.exp(kappa * (gap_prev - off))

        dc_bits = sum(d.at_price.dram_by_segment.get(k, 0.0) for k in DATACENTRE_SEGMENTS)
        budget_q = budget_2027 * interpolate_annual(capex, q) / capex[2027] / 4.0   # $bn/qtr
        ceiling = budget_q / units.bits_to_eb(dc_bits * (price / p1) ** eps)
        bound = price > ceiling
        price = min(price, ceiling)
        cost = (cost_anchor
                * interpolate_annual(a.series("market.wafer_cost_index"), q)
                * bpw_anchor / (s.dram_total_bits / s.installed_kwspm))
        price = max(price, cost / (1.0 - gm_floor))   # producers cut output below this

        demand = d.at_price.dram_total_bits * (price / p1) ** eps
        gap_prev = demand / supply - 1.0
        shipped = min(supply, demand)
        out.append(MarketQuarter(
            quarter=q, is_actual=False, price_usd_per_gb=price,
            shipped_eb=units.bits_to_eb(shipped),
            revenue_usd_bn=units.bits_to_eb(shipped) * price,
            cost_usd_per_gb=cost, gross_margin=1.0 - cost / price,
            gap_at_model_price=gap_prev, budget_bound=bound, price_ceiling_usd_per_gb=ceiling,
        ))
    return out
