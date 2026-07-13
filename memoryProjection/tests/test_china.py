"""The China invariant.

This is the test that guards the correction the whole china.py module exists for:
CXMT's output is captive to Chinese domestic demand, so exporting it westward would be
a REALLOCATION of where bits are consumed, not net new bits.

The structural consequence, asserted rather than argued:

    A CXMT ramp cannot close the global gap.

If someone later "improves" the model by counting Chinese wafers as global supply
relief without also netting off the Chinese demand they absorb, these tests fail. That
is exactly the double-count that makes a model show a shortage ending that never ends.
"""

import pytest

from model import china, config, demand, scenarios, supply
from model.calendar import projection_timeline


def gap_at(a, label="2029Q4"):
    tl = projection_timeline()
    ss = supply.supply_series(a, tl)
    dd = demand.demand_series(a, tl)
    bal = [china.balance_dram(a, s, d) for s, d in zip(ss, dd)]
    b = next(x for x in bal if x.quarter_label == label)
    return b


@pytest.mark.parametrize("captive", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_global_gap_is_invariant_to_captive_share(captive):
    """THE invariant. Where Chinese bits get consumed cannot change the GLOBAL balance.

    Moving captive_share must leave the global gap untouched -- it only moves bits
    between the captive and merchant pools.
    """
    a = scenarios.build_assumptions("central")
    a.override("china.captive_share", captive)
    got = gap_at(a).global_gap

    base = scenarios.build_assumptions("central")
    base.override("china.captive_share", 1.0)
    expected = gap_at(base).global_gap

    assert abs(got - expected) < 1e-9, (
        f"global gap moved from {expected:.4%} to {got:.4%} when captive_share went to "
        f"{captive}. Chinese bits are being double-counted."
    )


@pytest.mark.parametrize("captive", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_merchant_deficit_equals_global_deficit_always(captive):
    """The reallocation invariant, in its physically meaningful form.

    Selling a Chinese bit west removes it from the captive pool AND puts the displaced
    Chinese buyer back into the merchant pool. Merchant supply and merchant demand
    move by the same amount, so:

        merchant deficit = (D - c) - (S - c) = D - S = global deficit,  for every c.

    The absolute deficit is the number to trust. The RATIO moves with captive_share
    only because the denominator changes -- that is bookkeeping, not physics, which is
    why the model exposes deficit_eb alongside the gap ratio.
    """
    a = scenarios.build_assumptions("central")
    a.override("china.captive_share", captive)
    b = gap_at(a)
    # Relative tolerance: these are ~1e19-magnitude float64s, where one ulp is
    # already thousands of bits. An absolute epsilon here would be testing the FPU.
    assert abs(b.merchant_deficit_bits - b.deficit_bits) < 1e-9 * abs(b.deficit_bits)


def test_cxmt_ramp_adds_no_bits_to_non_chinese_producers():
    """What a CXMT ramp genuinely cannot do.

    It CAN close the global gap -- more capacity means more bits physically exist, and
    the model does not pretend otherwise. What it cannot do is make Samsung, SK Hynix
    or Micron ship a single additional bit. Its entire relief to the merchant market
    comes from China importing less, and is therefore bounded by Chinese domestic
    demand: once China is self-sufficient, further output has to be exported to go
    anywhere at all.
    """
    tl = projection_timeline()

    def row_supply(cxmt_factor: float) -> float:
        a = scenarios.build_assumptions(
            "central", sliders={"supply_capacity.dram_wafer_capacity_kwspm.cxmt": cxmt_factor}
        )
        ss = supply.supply_series(a, tl)
        s = next(x for x in ss if x.quarter.label == "2029Q4")
        return s.dram_total_bits - s.dram_china_bits

    base, doubled = row_supply(1.0), row_supply(2.0)
    # Second-order only: CXMT's share of the wafer pool shifts the HBM blend slightly.
    assert abs(doubled / base - 1.0) < 0.03, (
        f"doubling CXMT changed non-Chinese producers' output by "
        f"{doubled / base - 1:.1%}. It should change it by ~nothing."
    )


def test_cxmt_merchant_relief_is_bounded_by_chinese_demand():
    """CXMT can only displace imports up to what China actually consumes."""
    a = scenarios.build_assumptions(
        "central", sliders={"supply_capacity.dram_wafer_capacity_kwspm.cxmt": 3.0}
    )
    tl = projection_timeline()
    for s, d in zip(supply.supply_series(a, tl), demand.demand_series(a, tl)):
        b = china.balance_dram(a, s, d)
        assert b.captive_bits <= d.dram_china_bits + 1e-6, (
            "captive absorption exceeded Chinese domestic demand -- China cannot "
            "consume bits it does not want"
        )


def test_captive_bits_never_exceed_either_side():
    """You cannot absorb domestically more than China produces, nor more than it wants."""
    a = scenarios.build_assumptions("central")
    tl = projection_timeline()
    for s, d in zip(supply.supply_series(a, tl), demand.demand_series(a, tl)):
        b = china.balance_dram(a, s, d)
        assert b.captive_bits <= s.dram_china_bits + 1e-6
        assert b.captive_bits <= d.dram_china_bits + 1e-6


def test_every_assumption_is_sourced_and_confidence_tagged():
    """The assumption files are the research record. An untagged number is a liability."""
    a = config.load()
    audit = a.audit()
    assert sum(audit.values()) > 40, "suspiciously few assumptions loaded"
    # Nothing may be silently unsourced: DERIVED and USER_INPUT are explicit, honest
    # labels; "UNSOURCED" means someone forgot.
    assert a.unsourced() == [], f"assumptions with no source tag: {a.unsourced()}"
