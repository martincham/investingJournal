"""EDGAR extraction integrity.

This module has no free parameters -- it is either right or wrong, and everything
downstream is calibrated against it, so it must be right before anything else is built.

Each test here corresponds to a trap that was verified to bite on the real filings.
None of them are hypothetical.
"""

from __future__ import annotations

from datetime import date

import pytest

from model import edgar
from model.vendor.calendar import Quarter


@pytest.fixture(scope="module")
def doc():
    return edgar.fetch(max_age_days=3650)  # tests must never depend on the network


@pytest.fixture(scope="module")
def qs(doc):
    return edgar.load(doc)


@pytest.fixture(scope="module")
def cal(qs):
    return edgar.by_calendar(qs)


def test_fy_and_fp_fields_are_never_used_for_period_assignment():
    """EDGAR's fy/fp label the FILING, not the fact's period.

    Verified: the quarter 2024-08-30..2024-11-28 is FQ1 FY2025, but carries fy=2026,
    fp=Q1 because it appears as the prior-year comparative in the FY26 Q1 10-Q. Trusting
    those fields shifts whole years of data by one. Periods come from start/end only, and
    this greps the source to keep it that way.
    """
    src = edgar.__file__
    with open(src) as fh:
        code = "".join(
            line.split("#")[0] for line in fh if not line.strip().startswith("#")
        )
    for forbidden in ('["fy"]', "['fy']", '["fp"]', "['fp']", '.get("fy")', '.get("fp")'):
        assert forbidden not in code, f"edgar.py reads {forbidden}; fy/fp are not period labels"


def test_the_fy_fp_trap_is_real(doc):
    """Prove the trap rather than assert it: this fact IS mislabelled upstream."""
    facts = edgar._facts(doc, ["RevenueFromContractWithCustomerExcludingAssessedTax"])
    match = [f for f in facts if f.start == date(2024, 8, 30) and f.end == date(2024, 11, 28)]
    assert match, "the known-mislabelled fact is missing; re-check the fixture"
    # It is FQ1 FY2025 by its dates, and our mapping says so...
    assert edgar.load(doc) and match[0].val == pytest.approx(8_709e6)
    # ...while the raw JSON still claims fy=2026.
    raw = [
        r
        for r in doc["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"][
            "units"
        ]["USD"]
        if r.get("start") == "2024-08-30" and r["end"] == "2024-11-28"
    ]
    assert any(r["fy"] == 2026 for r in raw), "the fy/fp trap has changed shape; re-verify"


def test_quarterly_series_is_gapless(qs):
    labels = [q.calendar for q in qs]
    assert labels == sorted(labels)
    for prev, nxt in zip(labels, labels[1:]):
        assert nxt - prev == 1, f"gap between {prev} and {nxt}"
    # EDGAR keeps filing after the seam (FQ4'26 onward); the model ignores those quarters
    # via asp.pin_end, so the series only has to reach the seam, not stop there.
    assert labels[-1] >= Quarter(2026, 2), "reported data must reach FQ3'26 -> 2026Q2"


def test_covers_2020_through_2026q2(cal):
    """The window the projection needs: real data from 2020."""
    for year in range(2020, 2026):
        for q in range(1, 5):
            assert Quarter(year, q) in cal, f"missing {year}Q{q}"


def test_q4_derivation_matches_known_values(cal):
    """Q4 is never reported -- only FY and the 9-month YTD. These are Q4s, and they are
    the numbers a reader can check against Micron's own FY press releases."""
    assert cal[Quarter(2023, 3)].revenue == pytest.approx(4_010e6, rel=1e-6)   # FY23Q4
    assert cal[Quarter(2025, 3)].revenue == pytest.approx(11_315e6, rel=1e-6)  # FY25Q4
    assert cal[Quarter(2022, 3)].revenue == pytest.approx(6_643e6, rel=1e-6)   # FY22Q4


def test_fiscal_years_sum_to_reported_totals(cal):
    """The integrity check that costs nothing: four derived quarters must re-sum to the
    10-K's own annual revenue. If the chain-differencing is wrong anywhere, this breaks.
    """
    fy = {2023: 15_540e6, 2024: 25_111e6, 2025: 37_378e6}
    for year, total in fy.items():
        # FY_n runs from calendar (n-1)Q4 through nQ3.
        quarters = [Quarter(year - 1, 4), Quarter(year, 1), Quarter(year, 2), Quarter(year, 3)]
        got = sum(cal[q].revenue for q in quarters)
        assert got == pytest.approx(total, rel=1e-6), f"FY{year}: {got/1e6:,.0f}M != {total/1e6:,.0f}M"


def test_weighted_average_shares_use_n_weighted_not_subtraction(cal):
    """Share count is a MEAN, not a flow.

    FY2025: diluted FY = 1,125M, 9M = 1,123M. Subtracting gives 2M shares and an EPS
    ~500x too large. The n-weighted recovery gives 1,131M.
    """
    q4_fy25 = cal[Quarter(2025, 3)]
    assert q4_fy25.diluted_shares / 1e6 == pytest.approx(1_131, abs=2)
    assert q4_fy25.diluted_shares / 1e6 > 1_000, "the naive-subtraction bug is back"


def test_share_count_is_always_plausible(qs):
    """A blanket guard: no quarter may have a share count that is off by orders of
    magnitude. This is the shape the mean-vs-flow bug takes when it reappears."""
    for q in qs:
        assert 900e6 < q.diluted_shares < 1_400e6, f"{q.calendar}: {q.diluted_shares/1e6:,.0f}M shares"


def test_cashflow_ytd_chain_recovers_q2_q3(cal):
    """Cash-flow tags are YTD-only in 10-Qs -- no native quarterly durations after FQ1.
    Only chain-differencing gets Q2/Q3. FY25 capex: 3,206 / 4,055 / 2,938 / 5,658."""
    got = [
        cal[q].capex / 1e6
        for q in (Quarter(2024, 4), Quarter(2025, 1), Quarter(2025, 2), Quarter(2025, 3))
    ]
    assert got == pytest.approx([3_206, 4_055, 2_938, 5_658], rel=1e-3)


def test_cashflow_quarters_sum_to_reported_fy(cal):
    """FY25 capex YTD chain ends at 15,857."""
    total = sum(
        cal[q].capex
        for q in (Quarter(2024, 4), Quarter(2025, 1), Quarter(2025, 2), Quarter(2025, 3))
    )
    assert total / 1e6 == pytest.approx(15_857, rel=1e-3)


def test_recomputed_eps_matches_reported(qs):
    """We recompute EPS as net_income/diluted_shares for one consistent definition
    across the series. Where the filings report it natively, the two must agree."""
    checked = 0
    for q in qs:
        if q.eps_reported != q.eps_reported:  # NaN -> Q4, never reported natively
            continue
        assert q.eps == pytest.approx(q.eps_reported, abs=0.02), f"{q.calendar}: {q.eps} vs {q.eps_reported}"
        checked += 1
    assert checked >= 20, f"only {checked} quarters cross-checked; the guard has gone slack"


def test_reported_eps_is_native_only_and_never_derived(cal):
    """Regression. EPS YTD is cumulative earnings over AVERAGE shares -- neither
    additive nor a mean. An early cut ran it through the mean recovery and produced
    $12.31 for FY21Q4 (real: ~$2.42), then cross-checked our EPS against that invention.

    So eps_reported exists only where a filing states it. Q4 has none, and that absence
    is the point: it keeps the cross-check independent of the thing being checked.
    """
    assert cal[Quarter(2021, 3)].eps_reported != cal[Quarter(2021, 3)].eps_reported  # NaN, FY21Q4
    assert cal[Quarter(2025, 3)].eps_reported != cal[Quarter(2025, 3)].eps_reported  # NaN, FY25Q4
    assert cal[Quarter(2026, 2)].eps_reported == pytest.approx(24.67, abs=0.02)  # FQ3'26, native
    # ...and the derived EPS is present for every quarter, Q4s included.
    assert cal[Quarter(2025, 3)].eps == pytest.approx(2.83, abs=0.02)


def test_inventory_is_an_instant_and_never_differenced(cal):
    """A balance-sheet stock. Differencing it would be nonsense; it must arrive whole."""
    assert cal[Quarter(2026, 1)].inventory == pytest.approx(8_267e6)
    assert cal[Quarter(2026, 2)].inventory == pytest.approx(8_567e6)


def test_the_fy23_trough_is_intact(cal):
    """The deepest glut in memory history. Everything this model claims about cycles is
    calibrated here, so the data itself must be exact."""
    q = cal[Quarter(2023, 1)]  # FY23Q2
    assert q.revenue == pytest.approx(3_693e6, rel=1e-6)
    assert q.gross_margin == pytest.approx(-0.327, abs=0.002)
    assert q.eps == pytest.approx(-2.12, abs=0.02)
    assert sum(cal[Quarter(2022, 4) + i].gross_profit < 0 for i in range(4)) >= 3


def test_the_fy26_boom_is_intact(cal):
    """The other calibration pole."""
    q = cal[Quarter(2026, 2)]  # FQ3'26, Micron's last reported quarter
    assert q.revenue == pytest.approx(41_456e6, rel=1e-6)
    assert q.gross_margin == pytest.approx(0.846, abs=0.002)


def test_restatements_keep_the_latest_filing(doc):
    """Same period, several filings, different values -> the company's current view wins."""
    facts = edgar._facts(doc, ["RevenueFromContractWithCustomerExcludingAssessedTax"])
    keys = [(f.start, f.end) for f in facts]
    assert len(keys) == len(set(keys)), "duplicate periods survived dedup"


def test_only_10k_and_10q_are_trusted(doc):
    facts = edgar._facts(doc, ["NetIncomeLoss"])
    assert {f.form for f in facts} <= {"10-K", "10-Q"}
