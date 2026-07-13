"""The credibility gate.

If the model cannot retrodict the cycle it has already lived through, it has no
business projecting 2029. These tests pin the backcast to what actually happened.
"""

import pytest

from model import scenarios

# What the industry actually did. Sign of the gap, not its magnitude -- the model is
# not precise enough to claim a magnitude, and pretending otherwise would be false
# precision.
KNOWN_CYCLE = {
    2018: "shortage",   # record DRAM prices
    2019: "glut",       # prices roughly halved
    2020: "balanced",
    2021: "shortage",   # the chip crisis
    2023: "glut",       # the worst downturn in the industry's history
    2024: "balanced",   # recovery
    2025: "shortage",
    2026: "shortage",   # severe: 1Q26 DRAM industry revenue +81% QoQ
}

THRESHOLD = 0.04


def phase(gap: float) -> str:
    if gap > THRESHOLD:
        return "shortage"
    if gap < -THRESHOLD:
        return "glut"
    return "balanced"


@pytest.fixture(scope="module")
def central():
    return scenarios.run("central")


@pytest.mark.parametrize("year,expected", sorted(KNOWN_CYCLE.items()))
def test_backcast_reproduces_cycle_phase(central, year, expected):
    got = central.annual(year)["dram_gap"]
    assert phase(got) == expected, (
        f"{year}: model says {phase(got)} ({got:.1%}), history says {expected}"
    )


def test_2022_h2_crash_is_visible_at_quarterly_resolution(central):
    """2022 averages out to ~flat, which is why an annual model would miss it.

    The year had a tight first half and a collapsing second half. Catching that is the
    entire justification for the quarterly time base.
    """
    gaps = {b.quarter_label: b.global_gap for b in central.dram}
    assert gaps["2022Q4"] < gaps["2022Q1"] - 0.03, "the H2 2022 collapse should be visible"


def test_2025_dram_output_matches_public_anchors(central):
    """~40 EB in 2025, corroborated three independent ways: wafer capacity x density;
    $122B of DRAM revenue at a ~$2.9/GB blend; and Micron's ~22% bit share against its
    own disclosed output. Wide band -- this is an order-of-magnitude gate, not a claim
    to precision."""
    eb = central.annual(2025)["dram_supply_eb"]
    assert 33 <= eb <= 50, f"2025 DRAM supply {eb:.1f} EB is outside the sourced band"


def test_2026_bit_supply_growth_matches_trendforce_guide(central):
    """TrendForce guided industry DRAM capacity/bit growth to 10-15% for 2026."""
    g = central.annual(2026)["dram_supply_eb"] / central.annual(2025)["dram_supply_eb"] - 1
    assert 0.08 <= g <= 0.17, f"2026 DRAM bit-supply growth {g:.1%} outside the guided band"


def test_hbm_bit_share_matches_sourced_ratio(central):
    """HBM is ~22% of DRAM WAFERS but only ~9% of DRAM BITS in 2026. That divergence is
    the trade-ratio, and it is the mechanism behind the whole commodity squeeze."""
    a = central.annual(2026)
    share = a["hbm_supply_eb"] / a["dram_supply_eb"]
    assert 0.07 <= share <= 0.13, f"HBM bit share {share:.1%} inconsistent with sourced ~9%"


def test_nand_output_is_order_of_magnitude_larger_than_dram(central):
    """NAND ships far more bytes than DRAM. If this ratio ever collapses, a unit
    conversion has gone wrong somewhere."""
    a = central.annual(2025)
    ratio = a["nand_supply_eb"] / a["dram_supply_eb"]
    assert 20 <= ratio <= 50, f"NAND/DRAM byte ratio of {ratio:.0f}x is implausible"
