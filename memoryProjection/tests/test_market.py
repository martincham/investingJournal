"""The industry DRAM price layer (Nov 2026): model/market.py.

It must start from what was observed, hit the one guide it is calibrated to, stay inside
the 2027 margin guidance without being fitted to it, and respect its ceiling and floor.
"""

import pytest

from model import actuals, market, scenarios


@pytest.fixture(scope="module")
def central():
    return scenarios.run("central")


@pytest.fixture(scope="module")
def kappa(central):
    return market.calibrate_kappa(central)


@pytest.fixture(scope="module")
def mkt(central, kappa):
    return market.market_series(central, kappa)


def test_observed_quarters_are_observed(central, mkt):
    a = central.assumptions
    rev = a.value("actuals.dram_industry_revenue_usd_bn")
    for m in mkt:
        if m.is_actual:
            assert m.revenue_usd_bn == pytest.approx(rev[m.quarter.label])
    assert max(m.quarter for m in mkt if m.is_actual) == actuals.actuals_end(a)


def test_first_projected_quarter_hits_its_guide(central, mkt):
    guide = central.assumptions.scalar("market.price_change_guide_first_projected_quarter")
    i = next(i for i, m in enumerate(mkt) if not m.is_actual)
    assert mkt[i].price_usd_per_gb / mkt[i - 1].price_usd_per_gb - 1 == pytest.approx(guide)


def test_2027_margins_sit_in_the_guided_band(mkt):
    """NOT fitted to this. Micron guides FQ1-27 to 86.25% as the FY27 floor, with higher
    margins after and 'more moderate' price increases. Industry DRAM should sit at or a
    little above that, and nowhere near the 95% an unbudgeted path compounds to."""
    gms = [m.gross_margin for m in mkt if m.quarter.year == 2027]
    assert min(gms) >= 0.86
    assert max(gms) <= 0.92


def test_margins_never_reach_95_percent(mkt):
    assert max(m.gross_margin for m in mkt if m.gross_margin is not None) < 0.95


def test_budget_ceiling_binds_somewhere_but_not_everywhere(mkt):
    bound = [m.budget_bound for m in mkt if not m.is_actual]
    assert any(bound), "the ceiling never binds: dead code or a mis-scaled budget"
    assert not all(bound)


@pytest.mark.parametrize("scenario", ["tight", "loose"])
def test_floor_and_ceiling_hold_in_every_scenario(scenario, kappa):
    run = scenarios.run(scenario)
    floor = run.assumptions.scalar("market.gross_margin_floor")
    for m in market.market_series(run, kappa):
        if m.is_actual:
            continue
        assert m.gross_margin >= floor - 1e-9, m.quarter.label
        assert m.price_usd_per_gb <= m.price_ceiling_usd_per_gb + 1e-9 or m.gross_margin == pytest.approx(floor)
