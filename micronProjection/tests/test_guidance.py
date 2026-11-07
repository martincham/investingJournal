"""The seam: reported FQ4'26, guided FQ1'27, and the guide file against the dataset.

The guided quarter is pinned on four lines (revenue, GAAP gross margin, opex, tax) and
modelled on the rest. These tests hold the pinned lines exactly, use the EPS guide as a
check on the unpinned ones, and keep guidance.yaml from drifting away from the figures
recorded in data/reported/guidance.csv.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from model import edgar, pnl
from model.conf import load
from model.vendor.calendar import Quarter

ROOT = Path(__file__).resolve().parent.parent
GUIDED = Quarter(2026, 4)        # FQ1'27
LAST_REPORTED = Quarter(2026, 3)  # FQ4'26


@pytest.fixture(scope="module")
def a():
    return load()


@pytest.fixture(scope="module")
def runs(a):
    return {s: pnl.run(a, s) for s in ("central", "tight", "loose")}


@pytest.fixture(scope="module")
def guide_csv():
    with (ROOT / "data" / "reported" / "guidance.csv").open() as fh:
        return list(csv.DictReader(fh))


def _g(rows, period, metric, basis, col="mid"):
    hit = [r for r in rows if r["period"] == period and r["metric"] == metric and r["basis"] == basis]
    assert len(hit) == 1, (period, metric, basis)
    return float(hit[0][col])


def test_one_guided_quarter_directly_after_the_pin(a):
    pin = Quarter.parse(str(a.value("asp.pin_end")))
    assert pin == LAST_REPORTED
    assert Quarter.parse(str(a.value("guidance.guidance_end"))) == pin + 1 == GUIDED


def test_fq4_26_is_reported_verbatim(runs):
    """FQ4'26 used to be a guided $51bn. It is now Micron's 10-K, untouched."""
    row = runs["central"].at(LAST_REPORTED.label)
    rep = edgar.by_calendar(edgar.load(edgar.fetch(max_age_days=3650)))[LAST_REPORTED]
    assert row.is_actual and not row.is_guided
    assert row.fiscal_label == "FY26Q4"
    assert row.revenue == rep.revenue == pytest.approx(54_229e6)
    assert row.net_income == pytest.approx(37_701e6)
    assert row.fiscal.days == 98, "FY26 was a 53-week year"


@pytest.mark.parametrize("scenario", ["central", "tight", "loose"])
def test_guided_quarter_hits_the_pinned_lines(a, runs, scenario):
    row = runs[scenario].at(GUIDED.label)
    target = a.value("guidance.revenue_usd_bn")[scenario] * 1e9
    assert row.is_guided and not row.is_actual
    assert row.revenue == pytest.approx(target, rel=1e-9)
    assert row.gross_margin == pytest.approx(a.scalar("guidance.gross_margin"), abs=1e-9)
    assert (row.rnd + row.sga) == pytest.approx(a.scalar("guidance.opex_usd_bn") * 1e9, rel=1e-9)
    assert row.tax / (row.net_income + row.tax) == pytest.approx(a.scalar("guidance.tax_rate"), abs=1e-9)


def test_guided_eps_lands_inside_the_guided_range(a, runs):
    """EPS is NOT pinned -- D&A, other income and the share count are modelled. Landing
    inside Micron's $37.84 +/- $1.00 is the check that those unpinned pieces are sane."""
    eps = runs["central"].at(GUIDED.label).eps
    rng = a.value("guidance.eps_diluted")
    assert rng["low"] <= eps <= rng["high"], f"FQ1'27 EPS {eps:.2f} outside the GAAP guide"


def test_guided_share_count_is_near_the_guide(runs):
    """Micron: 'a share count of approximately 1.15 billion'."""
    shares = runs["central"].at(GUIDED.label).diluted_shares
    assert shares == pytest.approx(1.15e9, rel=0.01)


def test_fy27_opex_matches_the_guided_increase(runs):
    """FY27 opex 'increase by approximately $2.5bn' on FY26's $7.6bn of GAAP R&D + SG&A."""
    fy26 = sum(r.rnd + r.sga for r in runs["central"].fiscal_year(2026))
    fy27 = sum(r.rnd + r.sga for r in runs["central"].fiscal_year(2027))
    assert fy26 == pytest.approx(7_597e6, rel=1e-6)
    assert fy27 - fy26 == pytest.approx(2.5e9, abs=0.3e9)


def test_fy27_capex_follows_micron_plan(a, runs):
    """~$55bn net (H1 ~$25bn, FQ1 ~$11.5bn); the model carries it gross."""
    net = a.value("guidance.capex_net_usd_bn_by_quarter")
    vals = [float(net[k]) for k in sorted(net)]
    assert vals[0] == 11.5 and vals[0] + vals[1] == pytest.approx(25.0)
    assert sum(vals) == pytest.approx(55.0, abs=1.0)
    for scenario, run in runs.items():
        capex = sum(r.capex for r in run.fiscal_year(2027))
        assert 55e9 < capex < 61e9, f"{scenario}: FY27 gross capex {capex / 1e9:.1f}bn"


def test_guidance_yaml_matches_the_dataset(a, guide_csv):
    """Every guided figure the model reads is the one recorded from the press release."""
    rev = a.value("guidance.revenue_usd_bn")
    assert rev["central"] * 1e3 == _g(guide_csv, "FY27Q1", "revenue", "non_gaap", "mid")
    assert rev["loose"] * 1e3 == _g(guide_csv, "FY27Q1", "revenue", "non_gaap", "low")
    assert rev["tight"] * 1e3 == _g(guide_csv, "FY27Q1", "revenue", "non_gaap", "high")
    assert a.scalar("guidance.gross_margin") == _g(guide_csv, "FY27Q1", "gross_margin", "gaap")
    assert a.scalar("guidance.tax_rate") == _g(guide_csv, "FY27Q1", "tax_rate", "non_gaap")
    assert a.value("guidance.eps_diluted")["central"] == _g(guide_csv, "FY27Q1", "eps_diluted", "gaap")
    net = a.value("guidance.capex_net_usd_bn_by_quarter")
    first = float(net[min(net)])
    assert first * 1e3 == _g(guide_csv, "FY27Q1", "capex_net_of_incentives", "non_gaap")
