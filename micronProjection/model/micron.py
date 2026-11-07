"""Micron's slice of upstream's bits.

memoryProjection pools every producer into `installed_kwspm` before it emits anything,
so there is no Micron bit line to read -- it has to be rebuilt from the per-producer
capacity inputs that survive in upstream's flattened `assumption` table.

**Construction: Micron's bits are a SHARE of upstream's emitted bits, never re-derived
from wafers.** Upstream's supply has already been through the min() over C1-C6,
utilisation, node-conversion loss and the disruption haircut. Recomputing bits from
wafer capacity would reproduce none of that and would quietly diverge from the input
this model exists to take as given. So we compute wafer *ratios* and apply them to
upstream's own bit totals, which keeps Micron inside upstream's world by construction.

The split that matters:

    ROW commodity bits = upstream commodity bits - upstream china bits   (CXMT: no HBM)
    Micron commodity   = ROW commodity x (MU commodity wafers / ROW commodity wafers) x premium
    Micron HBM         = upstream HBM   x (MU HBM wafers       / ROW HBM wafers)       x premium

Doing it per-pool rather than as one blended share is what makes HBM intensity work:
an HBM bit costs ~2.85-3.3x the wafer of a commodity bit, and that trade ratio is
already baked into upstream's bit numbers. A producer running more HBM than the blend
therefore ships fewer bits from the same wafers -- automatically, with no trade ratio
appearing anywhere in this file.
"""

from __future__ import annotations

from dataclasses import dataclass

from model import upstream
from model.conf import Assumptions
from model.upstream import BaselineQuarter
from model.vendor.calendar import Quarter, interpolate_annual

PRODUCERS = ("samsung", "sk_hynix", "micron", "cxmt", "other")


@dataclass(frozen=True)
class MicronBits:
    """Micron's DRAM/NAND output for one quarter, in bits."""

    quarter: Quarter
    dram_bits: float
    dram_commodity_bits: float
    dram_hbm_bits: float
    nand_bits: float

    # provenance for the reconciliation table
    micron_kwspm: float
    row_kwspm: float
    dram_bit_share: float
    hbm_bit_share: float
    hbm_share_of_own_bits: float


def capacity_kwspm(a: Assumptions, producer: str, q: Quarter) -> float:
    """One producer's DRAM wafer capacity at a quarter.

    Upstream's own year-anchored series, interpolated with upstream's own
    `interpolate_annual` (which treats an anchor as the MID-year value). Using the same
    function is the point: any other interpolation would put us on a different capacity
    path than the model whose bits we are dividing up.
    """
    return interpolate_annual(upstream.wafer_capacity(a, producer), q)


def _pools(a: Assumptions, b: BaselineQuarter) -> tuple[float, float, float]:
    """(micron, cxmt, row) wafer capacity in kwspm at this quarter.

    `row` is ex-China, because that is the pool upstream allocates HBM out of.
    """
    q = b.quarter
    micron = capacity_kwspm(a, "micron", q)
    cxmt = capacity_kwspm(a, "cxmt", q)
    row = b.installed_kwspm - cxmt
    return micron, cxmt, row


def bits(a: Assumptions, b: BaselineQuarter) -> MicronBits:
    """Micron's bits for one baseline quarter. Reads upstream; never modifies it."""
    q = b.quarter
    micron_kwspm, _cxmt_kwspm, row_kwspm = _pools(a, b)

    premium = interpolate_annual(a.series("micron_share.density_premium_vs_row_blend"), q)
    mu_hbm_share = interpolate_annual(a.series("micron_share.hbm_wafer_share_of_own_wafers"), q)

    # Wafer pools. b.hbm_wafer_share is upstream's, on the ex-China basis (supply.py:192);
    # mu_hbm_share is Micron's own, on the same basis by construction of the YAML.
    mu_hbm_wafers = micron_kwspm * mu_hbm_share
    mu_commodity_wafers = micron_kwspm - mu_hbm_wafers
    row_hbm_wafers = row_kwspm * b.hbm_wafer_share
    row_commodity_wafers = row_kwspm - row_hbm_wafers

    # CXMT's bits are all commodity, so the ROW commodity pool is what is left after
    # China. Netting it out here is what stops Micron's share being diluted by wafers
    # that were never competing for the same HBM allocation.
    row_commodity_bits = b.dram_commodity_bits - b.dram_china_bits

    commodity = (
        row_commodity_bits * (mu_commodity_wafers / row_commodity_wafers) * premium
        if row_commodity_wafers > 0
        else 0.0
    )
    hbm = (
        b.dram_hbm_bits * (mu_hbm_wafers / row_hbm_wafers) * premium
        if row_hbm_wafers > 0
        else 0.0
    )

    total = commodity + hbm
    nand_share = interpolate_annual(a.series("micron_share.nand_bit_share"), q)

    return MicronBits(
        quarter=q,
        dram_bits=total,
        dram_commodity_bits=commodity,
        dram_hbm_bits=hbm,
        nand_bits=b.nand_supply_bits * nand_share,
        micron_kwspm=micron_kwspm,
        row_kwspm=row_kwspm,
        dram_bit_share=total / b.dram_supply_bits if b.dram_supply_bits else 0.0,
        hbm_bit_share=hbm / b.dram_hbm_bits if b.dram_hbm_bits else 0.0,
        hbm_share_of_own_bits=hbm / total if total else 0.0,
    )


def series(a: Assumptions, baseline: upstream.Baseline) -> list[MicronBits]:
    return [bits(a, b) for b in baseline.quarters]


@dataclass(frozen=True)
class ShareReconciliation:
    """Why 19% and 22% are the same number seen from different denominators.

    The disclosed ~22% is not in tension with a ~19% wafer share -- they are simply
    different questions. This table emits all of them side by side every quarter so the
    density premium stays a visible, arguable calibration rather than a coefficient
    someone has to trust.
    """

    quarter: Quarter
    micron_kwspm: float
    global_kwspm: float
    ex_china_kwspm: float
    bit_weighted_denom_kwspm: float
    share_global_wafer: float
    share_ex_china_wafer: float
    share_bit_weighted: float
    density_premium: float
    share_modelled: float
    share_disclosed: float
    residual: float


def reconcile(a: Assumptions, b: BaselineQuarter, mu: MicronBits) -> ShareReconciliation:
    micron_kwspm, cxmt_kwspm, row_kwspm = _pools(a, b)
    discount = interpolate_annual(
        upstream.assumption_series(a, "tech_roadmap.cxmt_density_discount"), b.quarter
    )
    # The bit-weighted denominator: CXMT's wafers make fewer bits, so counting them at
    # face value understates everyone else's share of BITS.
    bit_denom = row_kwspm + cxmt_kwspm * discount
    disclosed = interpolate_annual(a.series("micron_share.disclosed_bit_share"), b.quarter)

    return ShareReconciliation(
        quarter=b.quarter,
        micron_kwspm=micron_kwspm,
        global_kwspm=b.installed_kwspm,
        ex_china_kwspm=row_kwspm,
        bit_weighted_denom_kwspm=bit_denom,
        share_global_wafer=micron_kwspm / b.installed_kwspm,
        share_ex_china_wafer=micron_kwspm / row_kwspm,
        share_bit_weighted=micron_kwspm / bit_denom,
        density_premium=interpolate_annual(
            a.series("micron_share.density_premium_vs_row_blend"), b.quarter
        ),
        share_modelled=mu.dram_bit_share,
        share_disclosed=disclosed,
        residual=mu.dram_bit_share / disclosed - 1.0,
    )
