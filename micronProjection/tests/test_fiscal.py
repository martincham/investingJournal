"""The fiscal->calendar mapping.

Micron's year ends on the Thursday closest to 31 August, so its quarters drift against
the calendar and every seventh-ish year has a 14-week quarter. memoryProjection is
indexed by calendar quarter. This mapping is the join between the two models, so a
silent off-by-one here would misalign every projected quarter against its bit line.
"""

from __future__ import annotations

from datetime import date

import pytest

from model import edgar, fiscal
from model.fiscal import fiscal_to_calendar, max_overlap_calendar, normalise_flow
from model.vendor.calendar import Quarter


@pytest.fixture(scope="module")
def doc():
    return edgar.fetch(max_age_days=3650)


@pytest.fixture(scope="module")
def qs(doc):
    return edgar.load(doc)


def test_fq3_fy26_maps_to_2026q2(qs):
    """The seam. Micron's last reported quarter must land on upstream's actuals_end,
    or the ASP pin, the bit actuals and the EDGAR actuals stop agreeing."""
    last = qs[-1]
    assert (last.fiscal.start, last.fiscal.end) == (date(2026, 2, 27), date(2026, 5, 28))
    assert last.calendar == Quarter(2026, 2)
    assert last.fiscal.label == "FY26Q3"


def test_fy26_quarters_map_as_documented(qs):
    cal = {q.fiscal.label: q.calendar for q in qs}
    assert cal["FY26Q1"] == Quarter(2025, 4)
    assert cal["FY26Q2"] == Quarter(2026, 1)
    assert cal["FY26Q3"] == Quarter(2026, 2)


def test_midpoint_rule_equals_max_overlap_for_every_known_quarter(qs):
    """The midpoint rule is chosen for being tie-free, not for being different. If it
    ever diverged from max-overlap on real data, the choice would need re-arguing."""
    for q in qs:
        assert fiscal_to_calendar(q.fiscal.start, q.fiscal.end) == max_overlap_calendar(
            q.fiscal.start, q.fiscal.end
        ), f"{q.fiscal.label}: rules disagree"


def test_midpoint_rule_matches_sec_frames(doc):
    """The strongest available check: the SEC publishes its OWN calendar assignment in
    the `frame` field (e.g. CY2025Q4 for the quarter ended 2025-11-27). Our rule must
    reproduce it. This is an independent authority, not our arithmetic twice.
    """
    rows = doc["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"]
    checked = 0
    for r in rows:
        frame = r.get("frame")
        if not frame or not r.get("start") or "Q" not in frame:
            continue
        if frame.endswith("I"):  # instant frames don't apply to durations
            continue
        start, end = edgar._d(r["start"]), edgar._d(r["end"])
        if not (80 <= (end - start).days + 1 <= 100):
            continue
        expected = Quarter(int(frame[2:6]), int(frame[7]))
        assert fiscal_to_calendar(start, end) == expected, f"{start}..{end}: SEC says {frame}"
        checked += 1
    assert checked >= 10, f"only {checked} SEC frames checked; the cross-check has gone slack"


def test_fiscal_calendar_mapping_is_bijective(qs):
    """No calendar quarter may receive two fiscal quarters or none. build_calendar
    raises on collision; this asserts the whole observed run is clean."""
    cals = [q.calendar for q in qs]
    assert len(cals) == len(set(cals))
    for prev, nxt in zip(cals, cals[1:]):
        assert nxt - prev == 1


def test_53_week_year_fq4_fy20_is_98_days(qs):
    """FY2020 ran 370 days with a 14-week FQ4 (2020-05-29..2020-09-03). The midpoint
    rule needs no special case for it -- but the length does need normalising."""
    long = [q for q in qs if q.fiscal.is_long]
    assert len(long) == 1, f"expected exactly one 14-week quarter in the window, got {[q.fiscal.label for q in long]}"
    fq4 = long[0]
    assert fq4.fiscal.days == 98
    assert fq4.fiscal.start == date(2020, 5, 29) and fq4.fiscal.end == date(2020, 9, 3)
    assert fq4.calendar == Quarter(2020, 3)


def test_53_week_quarter_still_maps_by_both_rules(qs):
    fq4 = next(q for q in qs if q.fiscal.is_long)
    assert fiscal_to_calendar(fq4.fiscal.start, fq4.fiscal.end) == max_overlap_calendar(
        fq4.fiscal.start, fq4.fiscal.end
    )


def test_length_normalisation_removes_the_98_day_artifact(qs):
    """A 98-day quarter earns ~7.7% more revenue than a 91-day one for calendar reasons.
    Dividing that raw by bits imputes an ASP move that did not happen.

    Reported figures are never normalised; only rates are.
    """
    fq4 = next(q for q in qs if q.fiscal.is_long)
    raw = fq4.revenue
    normed = normalise_flow(raw, fq4.fiscal.days)
    assert normed < raw
    assert normed / raw == pytest.approx(91 / 98, rel=1e-9)
    assert raw / normed - 1 == pytest.approx(0.0769, abs=0.001), "the ~7.7% artifact"


def test_normalisation_is_identity_for_standard_quarters(qs):
    for q in qs:
        if q.fiscal.days == 91:
            assert normalise_flow(q.revenue, q.fiscal.days) == q.revenue


def test_fiscal_year_runs_one_quarter_ahead_of_calendar():
    assert fiscal.fiscal_year_and_quarter(Quarter(2025, 4)) == (2026, 1)
    assert fiscal.fiscal_year_and_quarter(Quarter(2026, 2)) == (2026, 3)
    assert fiscal.fiscal_year_and_quarter(Quarter(2026, 3)) == (2026, 4)
    assert fiscal.fiscal_year_and_quarter(Quarter(2026, 4)) == (2027, 1)


def test_build_calendar_rejects_a_collision():
    """The bijection is enforced, not hoped for."""
    with pytest.raises(ValueError, match="two fiscal quarters map to"):
        fiscal.build_calendar([(date(2026, 1, 1), date(2026, 3, 31)), (date(2026, 1, 15), date(2026, 4, 14))])
