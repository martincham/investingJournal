"""The price engine after the guided quarter.

price_source: market (default since Nov 2026) indexes Micron's guided price to upstream's
industry DRAM price path; the fitted response is computed alongside as a cross-check.
These tests pin down what that means: the index is applied verbatim, the floor is
Micron's own observed trough, the fitted coefficients are reproducible, and switching
back to `fitted` still works.
"""

from __future__ import annotations

import math

import pytest

from model import calibrate, pnl, upstream
from model.conf import deep_copy, load
from model.vendor.calendar import Quarter

GUIDED = Quarter(2026, 4)


@pytest.fixture(scope="module")
def a():
    return load()


@pytest.fixture(scope="module")
def runs(a):
    return {s: pnl.run(a, s) for s in ("central", "tight", "loose")}


def test_response_coefficients_reproduce_from_calibrate(a):
    """'Re-run it and the YAML values must reappear' -- held, not asserted."""
    f = calibrate.fit(calibrate.observations(a))
    assert f.n == 35
    for key, val in (("a", f.a), ("b", f.b), ("d", f.d), ("rho", f.rho), ("r2", f.r2)):
        assert a.scalar(f"asp.response_{key}") == pytest.approx(val, abs=6e-5), key
    assert a.scalar("asp.fitted_tightness_max") == pytest.approx(max(abs(f.t_min), f.t_max), abs=1e-3)


def test_price_floor_is_micron_observed_trough(a):
    obs = calibrate.observations(a)
    trough = min(obs, key=lambda o: o.markup)
    assert trough.quarter == Quarter(2023, 1)
    assert a.scalar("asp.price_floor_markup") == pytest.approx(trough.markup, abs=0.005)


@pytest.mark.parametrize("scenario", ["central", "tight", "loose"])
def test_projected_price_is_the_market_index_on_the_guided_price(a, runs, scenario):
    """ASP(q) / ASP(guided) == P_mkt(q) / P_mkt(guided) x inflation, wherever the floor
    does not bind. No damping, no blending -- upstream's path, verbatim."""
    run = runs[scenario]
    mkt = upstream.load_market(a, scenario)
    infl = a.scalar("asp.market_inflation_annual")
    g = run.at(GUIDED.label)
    checked = 0
    for r in run.rows:
        if r.quarter <= GUIDED or r.is_floored:
            continue
        years = (r.quarter.index - GUIDED.index) / 4
        want = mkt[r.quarter].price_usd_per_gb / mkt[GUIDED].price_usd_per_gb * (1 + infl) ** years
        assert r.commodity_asp_per_gb / g.commodity_asp_per_gb == pytest.approx(want, rel=1e-9), r.quarter
        checked += 1
    assert checked >= 8


@pytest.mark.parametrize("scenario", ["central", "tight", "loose"])
def test_margin_never_goes_below_the_2023_trough(runs, scenario):
    """The floor sits on cash cost, so with D&A the gross margin bottoms near 2023's
    -32.7%. Following upstream's index unfloored took loose to -107% by FY30."""
    for fy in range(2027, 2033):
        rr = runs[scenario].fiscal_year(fy)
        if len(rr) == 4:
            gm = sum(r.gross_profit for r in rr) / sum(r.revenue for r in rr)
            assert gm > -0.36, f"{scenario} FY{fy}: gross margin {gm:.1%}"


def test_loose_reaches_the_floor_and_central_does_not(runs):
    assert any(r.is_floored for r in runs["loose"].rows)
    assert not any(r.is_floored for r in runs["central"].rows)


def test_fitted_cross_check_exists_for_every_projected_quarter(runs):
    for run in runs.values():
        for r in run.rows:
            if not r.is_actual:
                assert r.fitted_asp_per_gb > 0, r.quarter


def test_market_path_is_continuous_at_the_seam(runs):
    """An index on Micron's own last price has no step at the seam by construction."""
    run = runs["central"]
    g, nxt = run.at(GUIDED.label), run.at((GUIDED + 1).label)
    assert 0.8 < nxt.commodity_asp_per_gb / g.commodity_asp_per_gb < 1.25


def test_fitted_source_still_runs_and_differs(a, runs):
    f = deep_copy(a)
    f.override("asp.price_source", "fitted")
    fitted = pnl.run(f, "central")
    g = fitted.at(GUIDED.label)
    assert g.revenue == pytest.approx(runs["central"].at(GUIDED.label).revenue)
    later = fitted.at("2027Q3")
    assert later.commodity_asp_per_gb == pytest.approx(later.fitted_asp_per_gb)
    assert later.commodity_asp_per_gb != pytest.approx(runs["central"].at("2027Q3").commodity_asp_per_gb)


def test_unknown_price_source_raises(a):
    bad = deep_copy(a)
    bad.override("asp.price_source", "vibes")
    with pytest.raises(ValueError):
        pnl.run(bad, "central")


def test_nominal_conversion_is_small_in_fy27(a, runs):
    """Inflation is a units conversion, not a driver: ~1-2% on FY27."""
    flat = deep_copy(a)
    flat.override("asp.market_inflation_annual", 0.0)
    real = sum(r.revenue for r in pnl.run(flat, "central").fiscal_year(2027))
    nom = sum(r.revenue for r in runs["central"].fiscal_year(2027))
    assert 0.0 < nom / real - 1 < 0.02
    assert math.isfinite(nom)
