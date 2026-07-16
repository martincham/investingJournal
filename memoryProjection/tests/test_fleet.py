"""Fleet, datacentre pipeline, actuals pin, and uncertainty bands."""

import pytest

from model import actuals, datacenter, fleet, scenarios, units, uncertainty
from model.calendar import Quarter, full_timeline


@pytest.fixture(scope="module")
def central():
    return scenarios.run("central")


@pytest.fixture(scope="module")
def a():
    return scenarios.build_assumptions("central")


# ---------------------------------------------------------------------------
# Actuals: reality overrides the model through 2026Q2
# ---------------------------------------------------------------------------
def test_supply_is_pinned_to_observed_data_through_2026q2(central, a):
    """Every quarter up to 2026Q2 must equal the observed number, not the model's guess.

    This is what makes a bug like "the power ceiling binds in 2026" impossible by
    construction: you cannot have a modelling error in a quarter you are not modelling.
    """
    for q, s in zip(central.quarters, central.supply):
        observed = actuals.dram_supply_bits(a, q)
        if observed is None:
            continue
        assert s.is_actual, f"{q.label} has observed data but was not pinned"
        assert abs(s.dram_total_bits - observed) < 1e-6 * observed, (
            f"{q.label}: model reported {units.bits_to_eb(s.dram_total_bits):.2f} EB "
            f"but the observed figure is {units.bits_to_eb(observed):.2f} EB"
        )


def test_nothing_after_2026q2_is_marked_actual(central, a):
    end = actuals.actuals_end(a)
    for q, s in zip(central.quarters, central.supply):
        if q > end:
            assert not s.is_actual, f"{q.label} is beyond the actuals cutoff but claims to be actual"


def test_the_2026q1_bit_dip_survives(central):
    """The single most informative data point: in 1Q26 DRAM revenue rose 81% while BITS
    FELL, because suppliers' inventories were depleted and they could no longer ship more
    than they made. If a later refactor smooths this away, the model has lost the
    signature of a supply wall."""
    g = {b.quarter_label: b.global_supply_bits for b in central.dram}
    assert g["2026Q1"] < g["2025Q4"], "the 1Q26 bit-shipment dip has been smoothed away"


# ---------------------------------------------------------------------------
# Datacentre pipeline
# ---------------------------------------------------------------------------
def test_delivered_power_is_less_than_announced(a):
    """Announced != built. If these are ever equal, the attrition model is inert."""
    tl = full_timeline()
    pw = datacenter.power_series(a, tl)
    for p in pw:
        if p.quarter.year >= 2027:
            assert p.delivered_gw < p.announced_gw, (
                f"{p.quarter.label}: delivering 100% of announced AI datacentre capacity "
                f"is not a thing that happens"
            )


def test_slipped_capacity_is_deferred_not_destroyed(a):
    """A delayed datacentre is late, not cancelled. Only `cancellation_asymmetry` of the
    shortfall is genuinely lost; the rest must reappear later."""
    tl = full_timeline()
    pw = datacenter.power_series(a, tl)
    total_announced = sum(p.announced_gw for p in pw) / 4
    total_delivered = sum(p.delivered_gw for p in pw) / 4
    # With ~15% true cancellation, delivery should land well above 50% of announced --
    # if it doesn't, slip is being silently treated as cancellation.
    assert total_delivered / total_announced > 0.55


# ---------------------------------------------------------------------------
# Fleet: shipments are an OUTPUT, and they must match the observed unit count
# ---------------------------------------------------------------------------
def test_fleet_reproduces_observed_accelerator_shipments(a):
    """The fleet derives shipments from power + retirements. It must land on the ~18M
    units the world actually bought in 2026 -- otherwise the datacentre pipeline is
    miscalibrated and every HBM number downstream is wrong."""
    tl = full_timeline()
    pw = datacenter.power_series(a, tl)
    fl = fleet.fleet_series(a, tl, pw)
    for year, target in ((2025, 14e6), (2026, 18e6)):
        got = sum(f.shipments for f in fl if f.quarter.year == year)
        assert abs(got / target - 1) < 0.20, (
            f"{year}: fleet ships {got/1e6:.1f}M accelerators, observed ~{target/1e6:.0f}M"
        )


def test_old_gpus_are_evicted_long_before_they_are_cash_unviable(a):
    """The whole point of the viability model.

    A 2020-vintage accelerator remains PROFITABLE to run for years after it stops being
    worth the watt it occupies. If those two dates ever coincide, the power-eviction
    mechanism has stopped doing anything and replacement demand will be badly understated.
    """
    rd = fleet.retirement_dates(a, full_timeline())
    d = rd[2020]
    assert d["power_evicted"] is not None, "the 2020 vintage is never evicted"
    evicted = Quarter.parse(d["power_evicted"])
    cash = Quarter.parse(d["cash_unviable"]) if d["cash_unviable"] else Quarter(2033, 4)
    assert evicted < cash, (
        "a GPU should stop being worth its watt BEFORE it stops paying its electricity "
        "bill. If not, power is not scarce in this model."
    )
    assert (cash - evicted) >= 8, (
        f"only {cash - evicted} quarters between eviction and cash-unviability -- the "
        f"'profitable but not worth keeping' effect has collapsed"
    )


def test_a100_class_hardware_is_still_running_in_2026(a):
    """Calibration against something we can just look at: people are still renting
    A100s. A model that retired them in 2024 is wrong about the present."""
    rd = fleet.retirement_dates(a, full_timeline())
    evicted = Quarter.parse(rd[2020]["power_evicted"])
    assert evicted >= Quarter(2025, 4), (
        f"model evicts the 2020 vintage at {evicted.label}, but A100s were demonstrably "
        f"still in profitable service through 2026"
    )


def test_replacement_demand_is_material(a):
    """Retiring an old GPU frees a watt, and the chip that refills it carries several
    times more memory. If replacement never shows up, an exogenous shipments series would
    have done just as well and this module is pointless."""
    tl = full_timeline()
    pw = datacenter.power_series(a, tl)
    fl = fleet.fleet_series(a, tl, pw)
    late = [f for f in fl if f.quarter.year >= 2028]
    peak = max(f.replacement_share for f in late)
    assert peak > 0.05, f"replacement never exceeds {peak:.1%} of shipments -- it is inert"


def test_memory_content_has_a_single_source_of_truth(a):
    """Memory content per accelerator lives in demand_ai.yaml and ONLY there.

    It used to be duplicated in gpu_fleet.yaml:vintages, and the two copies silently
    desynced the moment a scenario scaled one of them (the `tight` scenario multiplied
    demand_ai's HBM GB by 1.15 and left the vintage table behind). The duplication was
    removed; this guard keeps it from coming back. The vintage table owns power and
    performance; demand_ai.yaml owns memory content."""
    vintages = a.group("gpu_fleet.vintages")
    for year, spec in vintages.items():
        for banned in ("hbm_gb", "dram_gb"):
            assert banned not in spec, (
                f"gpu_fleet.yaml vintage {year} carries '{banned}' -- memory content "
                f"must live only in demand_ai.yaml, or the two will desync again"
            )
    # And the single source must actually exist and cover the vintage years.
    series = a.series("demand_ai.hbm_gb_per_accelerator")
    assert series, "demand_ai.hbm_gb_per_accelerator is missing"


# ---------------------------------------------------------------------------
# Uncertainty bands
# ---------------------------------------------------------------------------
def test_supply_band_has_zero_width_over_observed_data():
    """You cannot be uncertain about a quarter you have measured."""
    b = uncertainty.run_bands("central")
    i = b.quarters.index("2026Q1")
    assert abs(b.supply_p90[i] - b.supply_p10[i]) < 1e-9, (
        "the supply band has width over a quarter that is pinned to observed data"
    )


def test_demand_band_does_NOT_collapse_over_history():
    """The asymmetry that matters.

    Supply was measured. Demand-at-2025-prices never was -- it is a counterfactual, and
    it is inferred in 2019 exactly as much as in 2031. Collapsing its band over history
    would be claiming to have measured something that never happened.

    This test used to probe 2026Q1 only, and passed for the wrong reason: 2026Q1 sits
    next to the perturbed 2026 anchor and picks up a sliver of its width by interpolation.
    Every quarter from 2018 to 2025 was in fact a hairline, which is the exact error the
    report's own text was calling out. Probe DEEP history, and demand a real width.
    """
    b = uncertainty.run_bands("central")

    def rel_width(label):
        i = b.quarters.index(label)
        return b.demand_p90[i] / b.demand_p10[i] - 1.0

    for q in ("2019Q1", "2021Q3", "2023Q1", "2025Q2"):
        assert rel_width(q) > 0.05, (
            f"the demand band collapsed to a hairline at {q} -- but demand at constant "
            "2025 prices is never observed, so it cannot be near-certain anywhere"
        )

    # And it must be of the same ORDER as the near-term forecast band. The claim is not
    # "history is a bit uncertain", it is "history is inferred exactly as much as 2031".
    assert rel_width("2019Q1") > 0.5 * rel_width("2027Q4"), (
        "history is being treated as materially better known than the forecast, which is "
        "the collapse this test exists to prevent, just slower"
    )


def test_supply_band_still_collapses_over_history():
    """The counterfactual floor must not leak onto the measured side.

    Demand gets a floor because it was never observed. Supply was observed, and giving it
    an error bar over history would be the mirror-image bug.
    """
    b = uncertainty.run_bands("central")
    for q in ("2019Q1", "2023Q1", "2025Q2", "2026Q1"):
        i = b.quarters.index(q)
        assert abs(b.supply_p90[i] - b.supply_p10[i]) < 1e-9, (
            f"the supply band has width at {q}, which is pinned to observed data"
        )


def test_bands_widen_with_horizon():
    """A 2032 guess is worse than a 2027 guess, and the chart must say so."""
    b = uncertainty.run_bands("central")
    def width(label):
        i = b.quarters.index(label)
        return b.gap_p90[i] - b.gap_p10[i]
    assert width("2032Q4") > width("2027Q4") > 0, "bands do not widen with horizon"


# ---------------------------------------------------------------------------
# Tornado
# ---------------------------------------------------------------------------
def test_tornado_bars_and_baseline_come_from_the_same_run():
    """A bar drawn against a baseline its own run cannot reproduce is a lie about scale.

    The bars were computed on projection_timeline() while the baseline came from
    full_timeline(). Same scenario, same quarter, 0.43pp apart -- because a run starting
    in 2026Q1 gives the GPU fleet no 2018-2025 vintages to retire, and retirement is what
    drives replacement demand. The visible symptom: levers with NO effect rendered as
    small bars pointing the wrong way.

    So: any lever whose two arms agree must land exactly on the baseline.
    """
    tor = scenarios.tornado("2029Q4")
    assert tor, "the tornado produced no rows"
    baseline = tor[0][3]

    inert = [(label, lo) for label, lo, hi, _ in tor if abs(hi - lo) < 1e-12]
    assert inert, "expected at least one lever with no effect on the 2029Q4 gap"
    for label, lo in inert:
        assert abs(lo - baseline) < 1e-9, (
            f"'{label}' moves the gap by {(lo - baseline) * 100:+.3f}pp when swung both "
            "ways -- the bars and the baseline are not the same model run"
        )


def test_tornado_baseline_matches_the_charted_central_case():
    """The reference line has to be the number the reader sees in the gap chart."""
    tor = scenarios.tornado("2029Q4")
    charted = scenarios.run("central", full_timeline()).dram_gap_at("2029Q4")
    assert abs(tor[0][3] - charted) < 1e-9, (
        "the tornado's baseline is not the gap plotted in the headline chart"
    )
