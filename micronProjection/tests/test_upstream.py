"""The input contract.

These tests are not ceremony. This model's entire claim is "given memoryProjection's
bit lines, Micron earns X" -- which is worth nothing if we quietly reshape the bit
lines on the way in. So: the file is read-only, the segments are classified the way
upstream classifies them, and the premises we build on are re-checked against the file
we actually loaded rather than against a docstring someone wrote in 2026.
"""

from __future__ import annotations

import sqlite3

import pytest

from model import upstream
from model.conf import load
from model.vendor.calendar import Quarter


@pytest.fixture(scope="module")
def a():
    return load()


@pytest.fixture(scope="module")
def central(a):
    return upstream.load_baseline(a, "central")


def test_all_three_scenarios_load(a):
    """tight/central/loose are OUR scenarios too. We add no fourth."""
    bases = upstream.load_all(a)
    assert set(bases) == {"tight", "central", "loose"}
    for name, b in bases.items():
        assert len(b.quarters) == 60, f"{name}: expected 2018Q1..2032Q4"


def test_upstream_actuals_end_is_2026q2(central):
    """The ASP pin date and the EDGAR cutoff are both keyed to this."""
    assert central.actuals_end == Quarter(2026, 2)


def test_timeline_is_gapless_2018q1_to_2032q4(central):
    qs = [b.quarter for b in central.quarters]
    assert qs[0] == Quarter(2018, 1) and qs[-1] == Quarter(2032, 4)
    for prev, nxt in zip(qs, qs[1:]):
        assert nxt - prev == 1, f"gap between {prev} and {nxt}"


def test_sqlite_is_never_written(a):
    """mode=ro is the enforcement, so prove the connection actually rejects a write.

    If this ever fails, we are one stray statement away from corrupting another
    model's build artifact.
    """
    path = upstream.sqlite_path(a)
    conn = upstream._connect(path)
    with pytest.raises(sqlite3.OperationalError, match="readonly|read-only"):
        conn.execute("create table should_not_exist (x int)")
    conn.close()


def test_no_module_but_upstream_opens_the_sqlite():
    """Grep-level guard: one door to the input, and it is model/upstream.py.

    A second reader elsewhere would be a place for the "as given" rule to rot.
    """
    src = upstream.REPO_ROOT / "model"
    offenders = [
        p.name
        for p in src.rglob("*.py")
        if p.name != "upstream.py" and "memory_model.sqlite" in p.read_text()
    ]
    assert not offenders, f"these modules reach for the upstream sqlite directly: {offenders}"


def test_baseline_quarters_are_immutable(central):
    """The frozen dataclass IS the 'we never override supply' guarantee."""
    with pytest.raises(Exception):
        central.quarters[0].dram_supply_bits = 0.0  # type: ignore[misc]


def test_hbm_is_never_capped_upstream(central):
    """Our inelastic-core premise, re-checked against the file we loaded.

    AGENTS.md says HBM runs in slight surplus in every quarter. contested_supply_bits
    subtracts the inelastic core at FULL service on the strength of that. If upstream
    ever starts capping HBM, the premise dies and the tightness signal needs rework --
    so fail loudly here rather than silently mis-serve the core.
    """
    capped = [b.quarter.label for b in central.quarters if b.hbm_is_capped]
    assert not capped, f"HBM is capped in {capped}; contested_supply_bits assumes it never is"


def test_contested_pool_segments_match_agents_md(a):
    """Every DRAM segment upstream emits is classified. Unclassified ones raise on load."""
    contested = set(a.value("upstream.contested_segments"))
    inelastic = set(a.value("upstream.inelastic_segments"))
    assert contested == {"pc", "smartphone", "console", "graphics", "servers_traditional", "other"}
    assert inelastic == {"hbm", "ai_server_host", "kv_offload", "auto_industrial_iot"}
    assert not contested & inelastic


def test_unclassified_segment_raises(a, monkeypatch):
    """The load-time guard has teeth: a new upstream segment must not vanish silently
    into neither bucket, because that would bias the tightness denominator."""
    from model.conf import deep_copy

    b = deep_copy(a)
    b.override("upstream.contested_segments", ["pc"])  # drop the rest
    with pytest.raises(upstream.UpstreamMismatch, match="does not classify"):
        upstream.load_baseline(b, "central")


def test_segments_reconcile_to_total_demand(central):
    """contested + inelastic + inventory == the balance table's demand_eb.

    Proves our three buckets partition upstream's demand exactly -- no double-count,
    no dropped segment. If this drifts, the tightness signal is built on a subset.
    """
    for b in central.quarters:
        parts = b.contested_demand_bits + b.inelastic_demand_bits + b.inventory_bits
        assert parts == pytest.approx(b.dram_demand_bits, rel=1e-6), b.quarter


def test_gap_matches_supply_and_demand_as_given(central):
    """gap == demand/supply - 1, using the bits we converted. Guards the EB->bits
    conversion at the boundary and confirms we did not reshape either line."""
    for b in central.quarters:
        assert b.gap == pytest.approx(b.dram_demand_bits / b.dram_supply_bits - 1.0, rel=1e-4), b.quarter


def test_upstream_market_module_is_still_a_stub():
    """We are the price layer. If upstream grows one, these two models start
    disagreeing about ASP and somebody has to decide who wins -- loudly, not silently.
    """
    market = upstream.REPO_ROOT.parent / "memoryProjection" / "model" / "market.py"
    if not market.exists():
        pytest.skip("upstream not checked out alongside")
    assert "NotImplementedError" in market.read_text(), (
        "memoryProjection/model/market.py is no longer a stub -- upstream may now have "
        "its own price layer. Reconcile before trusting this model's ASP."
    )


def test_micron_wafer_capacity_is_readable(a):
    """The per-producer capacity that upstream pools away before emitting supply.
    It is the only route to a Micron bit share, so it must survive in `assumption`."""
    mu = upstream.wafer_capacity(a, "micron")
    assert mu[2025] == pytest.approx(385.0), "the 2025 anchor the share arithmetic keys on"
    assert min(mu) <= 2018 and max(mu) >= 2032


def test_inelastic_core_always_fits_under_supply(central):
    """The other half of the full-service premise: if the core ever exceeded supply,
    contested_supply_bits would go negative and the signal would be meaningless."""
    for b in central.quarters:
        assert b.contested_supply_bits > 0, f"{b.quarter}: inelastic core exceeds total supply"
