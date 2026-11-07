"""The tightness signal -- the gate on the whole design.

If this signal cannot tell a boom from a glut on the four cycles we have data for, then
the gap->price map is worthless and nothing downstream (ASP, margin, EPS) is worth
building. So it is tested before any of that exists.
"""

from __future__ import annotations

import pytest

from model import tightness, upstream
from model.conf import load

# The four phases we have ground truth for. Micron's actual gross margin is the
# arbiter -- it is not in the model, it is in the 10-Qs.
#   2019  glut   (industry-wide oversupply, MU GM collapsed from 59% to 30s)
#   2021  boom   (MU GM ~40s and rising)
#   2023  glut   (the deepest on record: MU GM -32.7% in FQ2'23)
#   2026  boom   (MU GM 84.6% in FQ3'26)
KNOWN_PHASES = {2019: "glut", 2021: "boom", 2023: "glut", 2026: "boom"}


@pytest.fixture(scope="module")
def a():
    return load()


@pytest.fixture(scope="module")
def sigs(a):
    base = upstream.load_baseline(a, "central")
    return {s.quarter: s for s in tightness.series(a, base)}


def _annual(sigs, year: int, attr: str) -> float:
    vals = [getattr(s, attr) for q, s in sigs.items() if q.year == year]
    return sum(vals) / len(vals)


def test_tightness_signal_has_correct_sign_in_every_known_phase(sigs):
    """THE GATE.

    Ground truth is Micron's reported gross margin, which this model has never seen.
    A boom must read tight (>0), a glut must read loose (<0). No tolerance on sign.
    """
    for year, phase in KNOWN_PHASES.items():
        t = _annual(sigs, year, "tightness")
        if phase == "boom":
            assert t > 0, f"{year} was a boom; signal reads {t:+.3f} (loose)"
        else:
            assert t < 0, f"{year} was a glut; signal reads {t:+.3f} (tight)"


def test_2023_reads_looser_than_2021(sigs):
    """The specific inversion that killed the first design.

    2023 is the deepest glut in memory history; 2021 was a boom. Any signal that ranks
    them the other way round will project a price spike into a -32.7% gross margin.
    """
    assert _annual(sigs, 2023, "tightness") < _annual(sigs, 2021, "tightness")


def test_tightness_excluding_inventory_gets_2023_backwards(sigs):
    """Documents WHY the inventory swing is in the signal, by showing what happens
    without it. This is not a hypothetical -- it is the bug that was there first.

    Asserted as a real expectation, not an xfail, because the day this stops being true
    is the day the justification in asp.yaml and tightness.py needs rewriting.
    """
    ex_2023 = _annual(sigs, 2023, "served_fraction_ex_inventory")
    ex_2021 = _annual(sigs, 2021, "served_fraction_ex_inventory")
    assert ex_2023 < ex_2021, "the ex-inventory bug has changed shape; re-verify the docs"

    inc_2023 = _annual(sigs, 2023, "served_fraction")
    inc_2021 = _annual(sigs, 2021, "served_fraction")
    assert inc_2023 > 1.0 > inc_2021, "including inventory must sign 2023 as surplus"


def test_served_fraction_signs_all_four_phases(sigs):
    """The same claim one level down, in the units the docs quote."""
    assert _annual(sigs, 2019, "served_fraction") > 1.0   # glut
    assert _annual(sigs, 2021, "served_fraction") < 1.0   # boom
    assert _annual(sigs, 2023, "served_fraction") > 1.0   # glut
    assert _annual(sigs, 2026, "served_fraction") < 1.0   # boom


def test_tightness_agrees_with_upstreams_own_gap_sign_in_history(sigs):
    """Sanity: over the backcast our contested signal should broadly agree with
    upstream's headline gap about which way the cycle points. Where they disagree,
    upstream's gap is the coarser number -- but a systematic disagreement would mean
    we have misread its output."""
    disagreements = [
        q.label
        for q, s in sigs.items()
        if q.year <= 2026 and (s.tightness > 0) != (s.gap_upstream > 0)
    ]
    assert len(disagreements) <= 6, f"signal and upstream gap disagree on sign in {disagreements}"


def test_tightness_is_a_pure_function_of_upstream_columns(a):
    """No hidden state, no path dependence, no free-floating drift: the same baseline
    quarter must always give the same signal. This is what makes 'we never override the
    input' checkable rather than aspirational."""
    base = upstream.load_baseline(a, "central")
    b = base.at("2029Q2")
    assert tightness.signal(a, b) == tightness.signal(a, b)


def test_signal_responds_to_the_reference_not_to_absolutes(a):
    """served_reference is a calibration, so moving it must move the signal. If it did
    not, the reference would be decorative and the zero point arbitrary."""
    from model.conf import deep_copy

    base = upstream.load_baseline(a, "central")
    b = base.at("2022Q2")
    loose = deep_copy(a)
    loose.override("asp.served_reference", 0.90)
    assert tightness.signal(loose, b).tightness < tightness.signal(a, b).tightness


def test_scenarios_span_tight_to_glut_in_the_out_years(a):
    """Not a finding of ours -- a property of the input, recorded so it is not mistaken
    for one. In the July vintage every scenario stayed tight to 2032. In November's,
    tight and central stay tight through 2030 while LOOSE turns into a glut from 2027
    (upstream AGENTS.md: loose supply jumps above demand straight after the observed
    data and nothing in that model cuts supply to end it). Our earnings path inherits
    both, which is exactly what 'conditional on those bit lines' means.
    """
    sigs = {n: {s.quarter: s for s in tightness.series(a, upstream.load_baseline(a, n))}
            for n in ("tight", "central", "loose")}
    for name in ("tight", "central"):
        for year in range(2027, 2031):
            assert _annual(sigs[name], year, "tightness") > 0, f"{name}: {year} reads loose"
    assert _annual(sigs["loose"], 2028, "tightness") < 0, "loose no longer gluts -- re-read upstream"
