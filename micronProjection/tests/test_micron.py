"""Micron's bit share.

Upstream pools every producer away, so this share is rebuilt rather than read. That
makes it the first place in the model where a number could be quietly invented, and
these tests are what stop that: two disclosed anchors, a consistency check against
upstream's own pooled capacity, and a set of guards that would catch the share drifting
into fantasy in the out-years where nobody can check it.
"""

from __future__ import annotations

import pytest

from model import micron, upstream
from model.conf import load
from model.vendor import units
from model.vendor.calendar import Quarter, interpolate_annual


@pytest.fixture(scope="module")
def a():
    return load()


@pytest.fixture(scope="module")
def base(a):
    return upstream.load_baseline(a, "central")


@pytest.fixture(scope="module")
def rows(a, base):
    return micron.series(a, base)


def _annual_share(base, rows, year: int) -> float:
    mu = sum(m.dram_bits for b, m in zip(base.quarters, rows) if b.quarter.year == year)
    ind = sum(b.dram_supply_bits for b in base.quarters if b.quarter.year == year)
    return mu / ind


def test_producer_capacities_sum_to_upstreams_pooled_total(a, base):
    """Our per-producer read must reconstruct upstream's own installed_kwspm exactly.

    This is the load-bearing consistency check for the whole share construction: if the
    five producers we read do not re-sum to the number upstream actually used, we are
    dividing up a pool that does not exist, and every share below is meaningless.
    """
    for b in base.quarters:
        total = sum(micron.capacity_kwspm(a, p, b.quarter) for p in micron.PRODUCERS)
        assert total == pytest.approx(b.installed_kwspm, rel=1e-9), b.quarter


def test_micron_bit_share_matches_disclosed_2025(a, base, rows):
    """~22% of DRAM bits. memoryProjection/assumptions/actuals.yaml leans on this same
    fact to corroborate its bit level, so our share and its supply line cannot drift
    apart without one of them contradicting a shared source."""
    assert _annual_share(base, rows, 2025) == pytest.approx(0.22, abs=0.01)


def test_micron_bit_share_matches_disclosed_2020(a, base, rows):
    """~23.5%, from TrendForce's 2020 DRAM revenue shares. The early anchor -- it is
    what forces the density premium below 1.0 in the years Micron trailed on node."""
    assert _annual_share(base, rows, 2020) == pytest.approx(0.235, abs=0.01)


def test_density_premium_crosses_one_around_2023(a):
    """The shape is a claim about history, not a curve fit.

    A first cut assumed Micron always led on density and put its 2020 bit share at 26.9%
    against a real ~23.5%. Micron was roughly a node behind Samsung/SK through 2020 and
    only led with 1-beta/1-gamma from ~2024. If this ever monotonically decays again,
    that regression is back.
    """
    s = a.series("micron_share.density_premium_vs_row_blend")
    assert interpolate_annual(s, Quarter(2020, 2)) < 1.0, "Micron did not lead on density in 2020"
    assert interpolate_annual(s, Quarter(2025, 2)) > 1.0, "Micron does lead by 2025"
    assert interpolate_annual(s, Quarter(2032, 2)) < interpolate_annual(s, Quarter(2026, 2)), (
        "the lead must narrow -- compounding a density edge for eight years is the "
        "easiest way to make this model quietly bullish"
    )


def test_share_never_leaves_a_plausible_band(base, rows):
    """A blanket guard over all 60 quarters. Micron has never been below ~15% or above
    ~30% of DRAM bits, and upstream's capacity path implies nothing that dramatic."""
    for b, m in zip(base.quarters, rows):
        assert 0.15 < m.dram_bit_share < 0.30, f"{b.quarter}: share {m.dram_bit_share:.1%}"


def test_micron_bits_never_exceed_the_industry(base, rows):
    for b, m in zip(base.quarters, rows):
        assert m.dram_bits < b.dram_supply_bits, b.quarter
        assert m.dram_hbm_bits <= b.dram_hbm_bits + 1e-6, b.quarter
        assert m.nand_bits < b.nand_supply_bits, b.quarter


def test_commodity_and_hbm_sum_to_total(base, rows):
    for b, m in zip(base.quarters, rows):
        assert m.dram_commodity_bits + m.dram_hbm_bits == pytest.approx(m.dram_bits, rel=1e-9)


def test_hbm_intensity_costs_micron_bits(a, base):
    """The trade-ratio mechanic, verified rather than assumed.

    An HBM bit eats ~2.85-3.3x the wafer of a commodity bit, and that ratio is already
    inside upstream's numbers. So raising Micron's HBM wafer share must LOWER its bit
    count from the same wafers -- with no trade ratio appearing anywhere in micron.py.
    If this ever fails, the per-pool split has collapsed into a blended share and HBM
    mix has stopped being economically real.
    """
    from model.conf import deep_copy

    q = Quarter(2029, 2)
    b = upstream.load_baseline(a, "central").at(q.label)
    lo = micron.bits(a, b)

    more_hbm = deep_copy(a)
    s = dict(more_hbm.series("micron_share.hbm_wafer_share_of_own_wafers"))
    more_hbm.override(
        "micron_share.hbm_wafer_share_of_own_wafers", {k: min(v * 1.3, 0.9) for k, v in s.items()}
    )
    hi = micron.bits(more_hbm, b)

    assert hi.dram_hbm_bits > lo.dram_hbm_bits, "more HBM wafers must make more HBM bits"
    assert hi.dram_bits < lo.dram_bits, "...and fewer total bits, because HBM trades ~3:1"


FY26_9M = (Quarter(2025, 4), Quarter(2026, 1), Quarter(2026, 2))
FY25_9M = (Quarter(2024, 4), Quarter(2025, 1), Quarter(2025, 2))


def _growth(by_q, attr: str, new, old) -> float:
    return sum(getattr(by_q[q], attr) for q in new) / sum(getattr(by_q[q], attr) for q in old) - 1


def test_micron_production_growth_tracks_the_industry(a, base, rows):
    """What Phase 3 actually claims: Micron's PRODUCTION grows with the industry's,
    give or take the slow share drift the density premium and CXMT's ramp imply.

    It does not claim to reproduce Micron's reported SHIPMENT growth -- see
    test_shipments_exceed_production_in_the_fy26_drain for why those are different
    numbers.
    """
    by_mu = {b.quarter: m for b, m in zip(base.quarters, rows)}
    by_ind = {b.quarter: b for b in base.quarters}
    mu = _growth(by_mu, "dram_bits", FY26_9M, FY25_9M)
    ind = _growth(by_ind, "dram_supply_bits", FY26_9M, FY25_9M)
    assert mu == pytest.approx(ind, abs=0.04), (
        f"Micron production {mu:.1%} vs industry {ind:.1%} -- a share move this fast is not "
        f"something upstream's capacity path supports"
    )


@pytest.mark.xfail(
    reason="Known and deliberate: production != shipments. Resolve in the P&L phase.",
    strict=True,
)
def test_shipments_exceed_production_in_the_fy26_drain(a, base, rows):
    """THE SHIPMENTS/PRODUCTION WEDGE. Documented as a failure rather than hidden.

    Micron reported DRAM bit shipments +~30% YoY over the first nine months of FY2026
    (memoryProjection/assumptions/actuals.yaml:92, corroborated by its own arithmetic:
    9M revenue +203% against ASP +~140% implies bits +~26%).

    Upstream's supply line is PRODUCTION -- bits physically made. Our share of it grows
    ~11% over the same window. The ~15-19pp wedge is not an error in either number: it
    is Micron shipping out of inventory. Upstream's own actuals.yaml says so, in the note
    explaining the 2026Q1 bit dip -- suppliers' inventories were "almost depleted" and
    "they could no longer ship more than they made". Draining a warehouse lets shipments
    outrun production until the warehouse is empty, which is exactly what 2026Q1 marks.

    Why this matters well beyond this test: REVENUE IS SHIPMENTS x ASP, NOT PRODUCTION
    x ASP. A model that bills production would have understated Micron's FY26 revenue by
    the whole wedge. The P&L phase adds an inventory bridge (EDGAR gives us InventoryNet
    quarterly, so the drain is observable, not assumed) and this test flips to passing on
    shipments. Until then it stays xfail(strict) -- if it ever passes by accident, that
    means someone has conflated the two series again.
    """
    by_q = {b.quarter: m for b, m in zip(base.quarters, rows)}
    growth = _growth(by_q, "dram_bits", FY26_9M, FY25_9M)
    assert growth == pytest.approx(0.30, abs=0.08), f"modelled 9M FY26 bit growth {growth:.1%}"


def test_shipments_are_pinned_to_actuals_through_2026q3(base, rows):
    """Through upstream's actuals_end the bits rest on observed supply, so Micron's
    bits there are share-of-reality rather than share-of-forecast."""
    actual = [b for b in base.quarters if b.is_actual]
    assert actual[-1].quarter == Quarter(2026, 3)


def test_reconciliation_explains_the_19_vs_22_gap(a, base, rows):
    """The three denominators are three questions, not a contradiction. At 2025 the
    disclosed ~22% is close to the EX-CHINA wafer share, while the global wafer share is
    ~19% -- the difference is CXMT's wafers, which make bits Micron never competed for.
    """
    b = base.at("2025Q3")
    m = next(m for bb, m in zip(base.quarters, rows) if bb.quarter == b.quarter)
    r = micron.reconcile(a, b, m)

    assert r.share_global_wafer == pytest.approx(0.19, abs=0.01)
    assert r.share_ex_china_wafer == pytest.approx(0.22, abs=0.01)
    assert r.share_global_wafer < r.share_bit_weighted < r.share_ex_china_wafer, (
        "the bit-weighted denominator must sit between the two wafer denominators: "
        "CXMT's wafers count, but at a density discount"
    )
    assert abs(r.residual) < 0.06, f"modelled share is {r.residual:+.1%} off the disclosed anchor"


def test_reconciliation_is_a_diagnostic_not_a_correction(a, base, rows):
    """share_modelled must come from the bit construction, never be snapped to the
    disclosed anchor. If they were identical every quarter, the table would be a mirror
    and the calibration would be unfalsifiable."""
    residuals = []
    for b, m in zip(base.quarters, rows):
        r = micron.reconcile(a, b, m)
        residuals.append(abs(r.residual))
    assert max(residuals) > 0.01, "modelled share appears pinned to the anchor"
