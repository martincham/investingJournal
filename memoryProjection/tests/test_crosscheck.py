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


def test_modelled_accelerators_match_the_observed_count(central):
    """The fleet derives shipments from min(capex, power, packaging). It must land on the
    ~18M units the world actually bought in 2026, or every HBM number downstream is wrong.

    Note this is now the real cross-check: `capex_implied_accelerators` is one of the
    three ceilings the fleet minimises over, so agreement between the fleet's output and
    the observed count is a statement about the whole stack, not about one series.
    """
    d = _q4(central, 2026)
    assert abs(d.modelled_accelerators * 4 / 18e6 - 1) < 0.25, (
        f"fleet ships {d.modelled_accelerators * 4 / 1e6:.1f}M accelerators in 2026; "
        f"the observed figure is ~18M"
    )


def test_power_scarcity_is_judged_against_an_independent_yardstick(central):
    """The bug this test exists to prevent.

    Scarcity used to be "the fleet is using >=90% of available power". That was circular:
    the fleet refilled ALL available headroom every quarter, so it consumed 100% of
    available power BY CONSTRUCTION, and the test silently degenerated into "is the
    buildout decelerating?". In 2026Q4 the fleet was using literally every available watt
    and the model still reported power as not scarce.

    Scarcity is now: the grid can run FEWER accelerators than capex wants to buy. So it
    must be possible for the fleet to sit BELOW its power ceiling -- if it never does,
    we are back to a fleet that expands into whatever space it is given, and the
    measurement is meaningless again.
    """
    slack = [
        f for f in central.demand
        if f.available_power_gw > 0 and f.fleet_power_gw < f.available_power_gw * 0.999
    ]
    assert slack, (
        "the fleet consumes 100% of available power in every single quarter -- so "
        "'power is scarce' cannot be measuring anything. The headroom-filling bug is back."
    )


def test_every_demand_ceiling_binds_somewhere(central):
    """capex / power / packaging are a min() stack. A ceiling that never binds is either
    mis-calibrated or dead code pretending to be a constraint."""
    binding = {d.binding_demand_constraint for d in central.demand if d.quarter.year >= 2024}
    assert "capex" in binding, "capex never limits accelerator purchases -- money is free?"
    assert "power" in binding, (
        "power never limits accelerator deployment. Then the GPU eviction mechanism, and "
        "the replacement demand that flows from it, can never switch on."
    )


def test_hbm_demand_is_not_below_hbm_supply_during_the_shortage(central):
    """HBM is sold out in 2026. A model that shows it in surplus has gone wrong."""
    for q, s, d in zip(central.quarters, central.supply, central.demand):
        if q.year == 2026:
            hbm_demand = d.dram_by_segment["hbm"]
            assert hbm_demand >= s.dram_hbm_bits * 0.85, (
                f"{q.label}: model shows HBM demand below supply during a period when "
                f"HBM was famously allocated and sold out."
            )
