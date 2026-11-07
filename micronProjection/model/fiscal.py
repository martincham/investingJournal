"""Micron's fiscal calendar, mapped onto the model's calendar quarters.

Micron's fiscal year ends on the Thursday closest to 31 August, so its quarters run
about a month ahead of calendar quarters and drift within the month year to year.
memoryProjection is indexed by CALENDAR quarter. Something has to reconcile them.

**The rule: a fiscal quarter belongs to the calendar quarter containing its midpoint.**

Verified identical to max-month-overlap across every quarter 2019Q3..2026Q2, and
simpler -- a 91-day period has an unambiguous middle day, so there are no ties to
break. It is also what the SEC itself does: XBRL's own `frame` field tags the quarter
ended 2025-11-27 as `CY2025Q4`, which is what this rule returns. That agreement is
worth more than our arithmetic alone, and test_midpoint_rule_matches_sec_frames
checks it against every frame the filings publish.

Consequences worth knowing:

  FQ1'26 (Aug 29 - Nov 27 2025) -> 2025Q4
  FQ2'26 (Nov 28 - Feb 26 2026) -> 2026Q1
  FQ3'26 (Feb 27 - May 28 2026) -> 2026Q2   <- Micron's last reported quarter

That last line is why the seams line up: upstream's `actuals_end` is 2026Q2 too, so the
bit actuals, the EDGAR actuals and the ASP pin all end on the same quarter.

The 53-week trap: FY2020 was 370 days, with a 98-day FQ4 (2020-05-29..2020-09-03). A
98-day quarter earns ~7.7% more revenue than a 91-day one for reasons that have nothing
to do with memory. Reported figures must never be touched -- but anything we divide to
get a RATE ($/bit) has to be normalised first, or we impute a price move that did not
happen. See `normalise_flow`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from model.vendor.calendar import Quarter

DAYS_PER_QUARTER = 91.25
STANDARD_QUARTER_DAYS = 91


@dataclass(frozen=True)
class FiscalQuarter:
    """One Micron fiscal quarter, as reported, plus where it lands on the calendar."""

    start: date
    end: date
    calendar: Quarter

    @property
    def days(self) -> int:
        """Inclusive length. 91 normally; 98 in the FQ4 of a 53-week year."""
        return (self.end - self.start).days + 1

    @property
    def is_long(self) -> bool:
        """A 14-week quarter. FY2020's FQ4 is the one in our window."""
        return self.days > 95

    @property
    def midpoint(self) -> date:
        return self.start + timedelta(days=(self.end - self.start).days // 2)

    @property
    def label(self) -> str:
        """Micron's own name for it, e.g. 'FY26Q3'.

        Derived from the calendar mapping rather than from EDGAR's fy/fp fields, which
        are unreliable here -- they label the FILING a fact appeared in, not the fact's
        period, so a prior-year comparative carries the current filing's year. See
        model/edgar.py.
        """
        fy, fq = fiscal_year_and_quarter(self.calendar)
        return f"FY{fy % 100:02d}Q{fq}"


def fiscal_to_calendar(start: date, end: date) -> Quarter:
    """Midpoint rule. The one place fiscal->calendar is decided."""
    mid = start + timedelta(days=(end - start).days // 2)
    return Quarter(mid.year, (mid.month - 1) // 3 + 1)


def max_overlap_calendar(start: date, end: date) -> Quarter:
    """Max-month-overlap mapping. Not used in anger -- kept so the tests can prove the
    midpoint rule agrees with it, rather than asking the reader to take that on faith."""
    counts: dict[Quarter, int] = {}
    day = start
    while day <= end:
        q = Quarter(day.year, (day.month - 1) // 3 + 1)
        counts[q] = counts.get(q, 0) + 1
        day += timedelta(days=1)
    return max(counts, key=lambda k: (counts[k], -k.index))


def fiscal_year_and_quarter(cal: Quarter) -> tuple[int, int]:
    """Calendar quarter -> (fiscal_year, fiscal_quarter).

    The fiscal year runs one calendar quarter ahead: 2025Q4 is FY26Q1. So shifting
    forward one quarter lands in the calendar year that names the fiscal year, and the
    quarter position follows.
    """
    shifted = cal + 1
    return shifted.year, shifted.q


def normalise_flow(value: float, days: int) -> float:
    """Scale a flow to a standard 91-day quarter.

    ONLY for deriving rates -- $/bit, cost/bit, QoQ growth. Never apply this to a
    reported figure: FQ4'20 revenue was $6,056M over 14 weeks and that is the number
    Micron reported, full stop. But dividing that unnormalised by bits imputes a +7.7%
    ASP move that is an artifact of the calendar, not of the memory market.
    """
    return value * STANDARD_QUARTER_DAYS / days


def build_calendar(periods: list[tuple[date, date]]) -> list[FiscalQuarter]:
    """Fiscal quarters from observed (start, end) pairs, sorted, mapped, checked.

    Boundaries come from the filings themselves rather than a hardcoded table, so the
    53-week years and the Thursday-nearest-31-August drift take care of themselves and
    there is no second source of truth to fall out of date.
    """
    out = [FiscalQuarter(s, e, fiscal_to_calendar(s, e)) for s, e in sorted(set(periods))]
    seen: dict[Quarter, FiscalQuarter] = {}
    for fq in out:
        if fq.calendar in seen:
            raise ValueError(
                f"two fiscal quarters map to {fq.calendar}: "
                f"{seen[fq.calendar].start}..{seen[fq.calendar].end} and {fq.start}..{fq.end}. "
                f"The midpoint rule should be a bijection; a collision means the period "
                f"boundaries are wrong."
            )
        seen[fq.calendar] = fq
    return out
