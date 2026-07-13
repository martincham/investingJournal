"""Independent cross-checks. These are the tests that caught real errors.

A model can be internally consistent and still be nonsense. These check it against
things known from OUTSIDE its own machinery: money, physics, and the fact that a
ceiling which binds in the past is not a ceiling.
"""

import pytest

from model import scenarios


@pytest.fixture(scope="module")
def central():
    return scenarios.run("central")


def _q4(run, year):
    return next(d for q, d in zip(run.quarters, run.demand) if q.year == year and q.q == 4)


@pytest.mark.parametrize("year", [2026, 2028, 2030, 2032])
def test_bottom_up_accelerators_agree_with_top_down_capex(central, year):
    """Can the world AFFORD the accelerators the model says it buys?

    Bottom-up (unit shipments x HBM content) against top-down (hyperscaler capex x
    accelerator share / ASP). These are independent chains and they must agree.

    This test failed on the first build -- the demand line implied ~46M accelerators in
    2032 against a capex path that could only fund ~26M, an 85% divergence. Capex was
    raised to what the unit build actually costs. If you ever find that capex path
    implausible, this test is telling you the demand line is too high.
    """
    d = _q4(central, year)
    effective = d.accelerators
    top_down = d.capex_implied_accelerators
    div = effective / top_down - 1
    assert abs(div) < 0.20, (
        f"{year}: bottom-up {effective * 4 / 1e6:.1f}M accelerators vs capex-implied "
        f"{top_down * 4 / 1e6:.1f}M -- {div:+.0%}. One of the two chains is wrong."
    )


def test_power_ceiling_does_not_bind_in_the_present(central):
    """A ceiling that binds in a year we can already observe is a bug, not a constraint.

    The world is visibly deploying ~18-20M accelerators in 2026. An earlier version of
    the power ceiling capped it at ~11M, which silently deflated HBM demand below its
    own known supply -- i.e. the model would have claimed HBM was in surplus during a
    period when it is famously sold out.
    """
    for year in (2025, 2026, 2027):
        assert not _q4(central, year).power_capped, (
            f"{year}: the power ceiling is binding in a year we can observe. "
            f"Either the GW/yr figure is too low or kW/accelerator is too high."
        )


def test_power_ceiling_does_bind_eventually(central):
    """...but it must bite somewhere, or it isn't doing any work.

    Grid interconnect, turbines and transformers are a real physical limit on the AI
    buildout. If the model never feels them, it is projecting a world with infinite
    electricity.
    """
    assert _q4(central, 2032).power_capped, "the power ceiling never binds -- it is inert"


def test_hbm_demand_is_not_below_hbm_supply_during_the_shortage(central):
    """HBM is sold out in 2026. A model that shows it in surplus has gone wrong."""
    for q, s, d in zip(central.quarters, central.supply, central.demand):
        if q.year == 2026:
            hbm_demand = d.dram_by_segment["hbm"]
            assert hbm_demand >= s.dram_hbm_bits * 0.85, (
                f"{q.label}: model shows HBM demand below supply during a period when "
                f"HBM was famously allocated and sold out."
            )
