"""Unit-conversion guards. Boring on purpose -- this is the class of bug that kills
memory models silently, because an 8x error still produces a plausible-looking chart.
"""

from model import units
from model.calendar import Quarter, interpolate_annual, s_curve


def test_gb_vs_gib_differ_by_exactly_eight():
    # A 16Gb DDR5 die is 2GB. If these two ever agree, something is very wrong.
    assert units.gib_to_bits(16) == units.gb_to_bits(2)
    assert units.gb_to_bits(1) == 8 * units.gib_to_bits(1)


def test_roundtrips():
    for eb in (0.5, 42.0, 1450.0):
        assert abs(units.bits_to_eb(units.eb_to_bits(eb)) - eb) < 1e-9
    assert abs(units.bits_to_gb(units.gb_to_bits(288)) - 288) < 1e-9
    assert abs(units.bits_to_eb(units.tb_to_bits(1e6)) - 1.0) < 1e-9


def test_known_quantities():
    # A 288GB Rubin package.
    assert units.gb_to_bits(288) == 288 * 8e9
    # 1 EB = 8e18 bits.
    assert units.eb_to_bits(1) == 8e18


def test_global_scale_guard_catches_the_8x_error():
    """The guard exists to catch a missing or doubled conversion, not to check precision."""
    good = units.eb_to_bits(42)  # plausible annual DRAM
    assert units.assert_global_scale(good, "dram") == good

    # A byte/bit mix-up on a global aggregate lands far outside the plausible band.
    for bad in (42.0, 42 * 8e18 * 1e6):
        try:
            units.assert_global_scale(bad, "dram")
        except ValueError:
            continue
        raise AssertionError(f"guard failed to catch implausible value {bad}")


def test_s_curve_is_monotonic_and_bounded():
    start = Quarter(2027, 1)
    prev = -1.0
    for i in range(-4, 24):
        v = s_curve(Quarter(2027, 1) + i, start, ramp_quarters=16)
        assert 0.0 <= v <= 1.0
        assert v >= prev - 1e-12, "a fab ramp must not go backwards"
        prev = v
    assert s_curve(start - 1, start, 16) == 0.0
    assert s_curve(start + 16, start, 16) == 1.0


def test_annual_anchors_are_year_centred():
    """An annual flow figure is the year's AVERAGE, not its 1-Jan value.

    Anchoring at 1 Jan pulls every series half a year early and damps sharp moves --
    it was halving the amplitude of the inventory swings that drive the memory cycle.
    So the four quarters of year Y must average to approximately the anchor for Y.
    """
    anchors = {2024: 10.0, 2025: 20.0, 2026: 30.0}
    mean_2025 = sum(interpolate_annual(anchors, Quarter(2025, q)) for q in (1, 2, 3, 4)) / 4
    assert abs(mean_2025 - 20.0) < 0.01
