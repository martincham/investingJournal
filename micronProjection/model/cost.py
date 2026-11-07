"""Cash cost per bit, and the shipments/production bridge.

Two jobs, and they are the same arithmetic seen from two sides.

**1. The bridge.** Upstream's supply line is bits PRODUCED. Micron's revenue is bits
SHIPPED. They diverge whenever inventory moves, and over 9M FY26 they diverged a lot:
Micron shipped +~30% YoY while industry production grew +14%, by draining the warehouse
(days-of-inventory 161 -> 121 across FY25). Billing production would understate revenue
by the whole wedge. The bridge closes with no free parameters:

    full_cost_of_production(q) = COGS(q) + inventory(q) - inventory(q-1)
    cash_cost_of_production(q) = full_cost(q) - D&A(q) * dna_in_cogs_share
    cash_cost_per_bit(q)       = cash_cost_of_production(q) / bits_produced(q)
    inventory_bits(q)          = inventory(q) / full_cost_per_bit(q)
    bits_shipped(q)            = bits_produced(q) - (inventory_bits(q) - inventory_bits(q-1))

The first line is "what it cost to make what we made" -- COGS measures what was SOLD, so
adding back the inventory build recovers production. Every term is reported.

The second line is not optional, and an earlier cut omitted it. COGS INCLUDES D&A, so
the first line yields a FULL cost, not a cash cost. Handing that to a P&L that then adds
D&A again double-counts it -- which is exactly what happened here, and it cost ~15pp of
projected gross margin while looking entirely plausible. Cash and full cost are different
numbers and the name must say which one it is. Inventory is valued at FULL cost (that is
how absorption accounting works), so the bridge deliberately uses full cost there and
cash cost for the P&L.

**2. The learning curve.** Cost per bit falls as nodes shrink, but Micron's BLENDED cost
also RISES on HBM mix, because an HBM bit consumes ~2.85-3.3x the wafer of a commodity
bit. Both happen at once, and a single-curve model reads the mix effect as a
learning-rate collapse that never happened. So cost is built per-pool and blended:

    commodity(q) = base * (1 - learning_rate)^years
    hbm(q)       = commodity(q) * hbm_cost_multiple(q)     ~ the trade ratio, + test/packaging
    blended(q)   = weighted by Micron's own bit mix

The price index everything hangs on is COMMODITY DRAM $/GB. HBM and NAND are expressed
as multiples of it, so there is one price to model rather than three.
"""

from __future__ import annotations

from dataclasses import dataclass

from model import upstream
from model.conf import Assumptions
from model.edgar import ReportedQuarter
from model.fiscal import normalise_flow
from model.micron import MicronBits
from model.vendor import units
from model.vendor.calendar import Quarter, interpolate_annual


@dataclass(frozen=True)
class Shipments:
    """The production -> shipments bridge for one quarter. Actuals only."""

    quarter: Quarter
    produced_bits: float
    shipped_bits: float
    inventory_bits: float
    inventory_build_bits: float        # negative = a drain: shipping more than making
    cost_of_production_usd: float      # FULL: includes D&A
    full_cost_per_bit: float           # commodity-equivalent, incl. D&A
    cash_cost_per_bit: float           # commodity-equivalent, EXCLUDING D&A

    @property
    def drain_fraction(self) -> float:
        """Share of shipments that came out of the warehouse rather than the fab."""
        return -self.inventory_build_bits / self.shipped_bits if self.shipped_bits else 0.0


def commodity_equivalent_bits(a: Assumptions, mu: MicronBits, q: Quarter) -> float:
    """Micron's bits re-expressed in commodity-DRAM-equivalents.

    One price index, not three. An HBM gigabyte sells for ~3x a commodity gigabyte and a
    NAND gigabyte for ~1/4, so weighting the bits by those ratios turns "total revenue"
    into "commodity DRAM ASP x equivalent bits" -- one number to model, and the mix
    effects fall out rather than being assumed.
    """
    hbm_prem = interpolate_annual(a.series("asp.hbm_asp_premium"), q)
    nand_ratio = interpolate_annual(a.series("asp.nand_asp_ratio"), q)
    return mu.dram_commodity_bits + hbm_prem * mu.dram_hbm_bits + nand_ratio * mu.nand_bits


def commodity_equivalent_cost_bits(a: Assumptions, mu: MicronBits, q: Quarter) -> float:
    """The same trick on the cost side, weighted by COST ratios rather than price ones.

    An HBM bit costs ~the trade ratio more to make; a NAND bit costs far less. Keeping
    the two weightings separate is what lets HBM carry a different margin from
    commodity -- if we reused the price weights, every product would earn the same
    margin by construction and the mix story would vanish.
    """
    hbm_mult = interpolate_annual(a.series("cost.hbm_cost_multiple"), q)
    nand_ratio = interpolate_annual(a.series("cost.nand_cost_ratio"), q)
    return mu.dram_commodity_bits + hbm_mult * mu.dram_hbm_bits + nand_ratio * mu.nand_bits


def bridge(
    a: Assumptions,
    reported: list[ReportedQuarter],
    mu_by_q: dict[Quarter, MicronBits],
) -> list[Shipments]:
    """Production -> shipments, from the filings. No free parameters.

    Needs the previous quarter's inventory, so the first reported quarter is dropped.
    """
    out: list[Shipments] = []
    for prev, cur in zip(reported, reported[1:]):
        q = cur.calendar
        mu = mu_by_q.get(q)
        if mu is None:
            continue

        produced = commodity_equivalent_cost_bits(a, mu, q)
        if produced <= 0:
            continue

        # Length-normalise the flows: a 98-day quarter books ~7.7% more COGS for reasons
        # that have nothing to do with memory. Inventory is an instant and is never
        # normalised -- it is a level, not a rate.
        cogs = normalise_flow(cur.cogs, cur.fiscal.days)
        build_usd = cur.inventory - prev.inventory
        cost_of_production = cogs + build_usd
        full_cost_per_bit = cost_of_production / produced

        # Strip D&A to get a CASH cost. Uses Micron's REPORTED D&A rather than an assumed
        # share of COGS -- most of it sits in manufacturing, the rest in R&D/SG&A.
        dna_in_cogs = normalise_flow(cur.dna, cur.fiscal.days) * interpolate_annual(
            a.series("cost.dna_in_cogs_share"), q
        )
        cash_of_production = cost_of_production - dna_in_cogs
        cash_cost_per_bit = cash_of_production / produced

        # Inventory is carried at FULL absorbed cost, so the bit conversion uses full cost.
        inv_bits = cur.inventory / full_cost_per_bit if full_cost_per_bit > 0 else 0.0
        prev_inv_bits = prev.inventory / full_cost_per_bit if full_cost_per_bit > 0 else 0.0
        build_bits = inv_bits - prev_inv_bits
        shipped = produced - build_bits

        out.append(
            Shipments(
                quarter=q,
                produced_bits=produced,
                shipped_bits=shipped,
                inventory_bits=inv_bits,
                inventory_build_bits=build_bits,
                cost_of_production_usd=cost_of_production,
                full_cost_per_bit=full_cost_per_bit,
                cash_cost_per_bit=cash_cost_per_bit,
            )
        )
    return out


@dataclass(frozen=True)
class CostQuarter:
    quarter: Quarter
    commodity_per_gb: float
    hbm_per_gb: float
    nand_per_gb: float
    blended_per_gb: float
    is_actual: bool


def modelled_commodity_cost_per_bit(
    a: Assumptions, q: Quarter, anchor_q: Quarter, anchor_cost_per_bit: float
) -> float:
    """The learning curve. Commodity DRAM cash cost per bit, compounded from an anchor.

    ANCHORED ON THE LAST KNOWN QUARTER, passed in rather than stored. Since the November
    2026 revision that is the guided quarter: Micron's GAAP gross-margin guide pins its
    COGS, and model/pnl.py backs the cash cost per bit out of it. Without a guide it is
    the last reported quarter's derived cost. Either way the curve starts from a number
    Micron published, never from a constant typed into a YAML that drifts out of date
    every time a quarter is reported (the old cost.commodity_cash_cost_per_gb_base was
    re-derived by hand three times).

    The rate DECAYS: bits per wafer used to come from lithographic shrink and now come
    from stacking and process tweaks, which are slower and dearer. Assuming a constant
    17%/yr to 2032 would hand Micron a cost advantage nobody has earned, and would be
    the second-easiest way (after a compounding density premium) to make this model
    quietly bullish.
    """
    rate = interpolate_annual(a.series("cost.learning_rate_annual"), q)
    years = q.fractional_year - anchor_q.fractional_year
    return anchor_cost_per_bit * (1.0 - rate) ** years


def modelled(
    a: Assumptions, mu: MicronBits, q: Quarter, anchor_q: Quarter, anchor_cost_per_bit: float
) -> CostQuarter:
    commodity = modelled_commodity_cost_per_bit(a, q, anchor_q, anchor_cost_per_bit)
    hbm_mult = interpolate_annual(a.series("cost.hbm_cost_multiple"), q)
    nand_ratio = interpolate_annual(a.series("cost.nand_cost_ratio"), q)

    hbm = commodity * hbm_mult
    nand = commodity * nand_ratio

    total_bits = mu.dram_bits + mu.nand_bits
    blended = (
        (
            commodity * mu.dram_commodity_bits
            + hbm * mu.dram_hbm_bits
            + nand * mu.nand_bits
        )
        / total_bits
        if total_bits
        else commodity
    )

    per_gb = lambda x: x * units.GIGA * units.BITS_PER_BYTE  # noqa: E731
    return CostQuarter(
        quarter=q,
        commodity_per_gb=per_gb(commodity),
        hbm_per_gb=per_gb(hbm),
        nand_per_gb=per_gb(nand),
        blended_per_gb=per_gb(blended),
        is_actual=False,
    )
