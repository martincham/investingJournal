"""The demand-at-current-prices line (Nov 2026) and the agentic-CPU segment.

The at-price line is demand if real memory prices stay at today's level. These tests
pin down what it can and cannot be: never above unrationed demand, identical before
the shortage, and in observed quarters positive but smaller than the unrationed gap,
because prices kept rising in every one of those quarters.
"""

import pytest

from model import actuals, scenarios
from model.calendar import Quarter


@pytest.fixture(scope="module")
def central():
    return scenarios.run("central")


def test_at_price_never_exceeds_unrationed(central):
    """Rationing can only take bits away. A segment that grows when prices rise is a bug."""
    for d in central.demand:
        for seg, bits in d.at_price.dram_by_segment.items():
            if seg == "inventory":
                continue
            assert bits <= d.dram_by_segment[seg] * (1 + 1e-9), (d.quarter.label, seg)


def test_lines_are_identical_before_the_shortage(central):
    start = actuals.rationing_start(central.assumptions)
    for d in central.demand:
        if d.quarter < start:
            assert d.at_price.dram_total_bits == pytest.approx(d.dram_total_bits), d.quarter.label
            assert d.at_price.nand_total_bits == pytest.approx(d.nand_total_bits), d.quarter.label


def test_observed_rationed_quarters_sit_between_clearing_and_unrationed(central):
    """In 2026Q1-Q3 contract prices rose every quarter (+80%, +52%, +21% blended), so
    demand at each quarter's price still exceeded what shipped: the at-price gap must be
    positive. It must also be well below the unrationed gap, or the at-price inputs are
    not cutting anything."""
    a = central.assumptions
    start, end = actuals.rationing_start(a), actuals.actuals_end(a)
    seen = 0
    for d, b in zip(central.demand, central.dram):
        if start <= d.quarter <= end:
            gap_at = d.at_price.dram_total_bits / b.global_supply_bits - 1
            assert 0 < gap_at < b.global_gap, (d.quarter.label, gap_at, b.global_gap)
            seen += 1
    assert seen >= 3


def test_at_price_gap_shrinks_as_price_gains_slow(central):
    """Blended DRAM ASP gains slowed every quarter of 2026 (+80%, +52%, +21%). Excess
    demand at the going price should shrink with them."""
    gaps = {
        d.quarter.label: d.at_price.dram_total_bits / b.global_supply_bits - 1
        for d, b in zip(central.demand, central.dram)
    }
    assert gaps["2026Q1"] > gaps["2026Q2"] > gaps["2026Q3"]


def test_rationed_units_do_not_feed_the_unrationed_line(central):
    """From rationing_start, observed PC/phone units pin the at-price line only."""
    a = central.assumptions
    q = Quarter(2026, 3)
    d = next(x for x in central.demand if x.quarter == q)
    observed = actuals.conventional_units(a, "smartphone", q, basis="at_price")
    assert observed is not None
    assert actuals.conventional_units(a, "smartphone", q, basis="unrationed") is None
    # 255M phones shipped in 2026Q3 (-22% YoY): the unrationed line must carry more.
    assert d.dram_by_segment["smartphone"] > d.at_price.dram_by_segment["smartphone"]


def test_ai_cpu_servers_are_present_and_unaffected_by_price(central):
    d = next(x for x in central.demand if x.quarter == Quarter(2027, 4))
    assert d.dram_by_segment["ai_cpu_server"] > 0
    assert d.at_price.dram_by_segment["ai_cpu_server"] == pytest.approx(d.dram_by_segment["ai_cpu_server"])
