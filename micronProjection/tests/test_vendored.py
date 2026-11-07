"""Drift guard on model/vendor/.

units.py, calendar.py and config.py are copied verbatim from memoryProjection rather
than imported, so this repo stands alone at runtime (upstream has no pyproject.toml;
a sys.path shim would hardcode a sibling checkout and silently absorb upstream edits
to what a Quarter is).

The cost of vendoring is drift. This is the payment: standalone at runtime, detected
at test time. If upstream deliberately changes calendar.py, this fails and a human
decides -- which is the correct outcome, not an annoyance.
"""

from __future__ import annotations

from pathlib import Path

import pytest

VENDORED = Path(__file__).resolve().parent.parent / "model" / "vendor"
UPSTREAM = Path(__file__).resolve().parents[2] / "memoryProjection" / "model"

VENDORED_MODULES = ["units.py", "calendar.py", "config.py"]


@pytest.mark.parametrize("name", VENDORED_MODULES)
@pytest.mark.skipif(not UPSTREAM.exists(), reason="memoryProjection not checked out alongside")
def test_vendored_modules_are_byte_identical_to_upstream(name):
    ours, theirs = VENDORED / name, UPSTREAM / name
    assert ours.read_bytes() == theirs.read_bytes(), (
        f"model/vendor/{name} has drifted from memoryProjection/model/{name}.\n"
        f"Do not edit vendored files -- wrap them from model/ instead (see model/conf.py, "
        f"which redirects the assumptions dir without touching config.py).\n"
        f"If UPSTREAM changed on purpose, re-copy and re-run the backcast."
    )


def test_conf_shim_points_at_this_repos_assumptions():
    """Why the shim exists: vendored config.py resolves ASSUMPTIONS_DIR relative to its
    own parent, which lands in model/assumptions here. Editing it would break the
    byte-identity test above, so model/conf.py passes the directory explicitly."""
    from model.conf import ASSUMPTIONS_DIR
    from model.vendor.config import ASSUMPTIONS_DIR as VENDOR_DIR

    assert ASSUMPTIONS_DIR.name == "assumptions"
    assert ASSUMPTIONS_DIR.parent.name == "micronProjection"
    assert VENDOR_DIR != ASSUMPTIONS_DIR, "the shim is pointless if these agree"


def test_assumptions_load_through_the_shim():
    from model.conf import load

    a = load()
    assert a.value("upstream.expected_actuals_end") == "2026Q3"


def test_every_assumption_has_a_source_and_confidence():
    """Upstream's discipline, inherited: numbers live in YAML with provenance, and an
    UNSOURCED input should be visible rather than dressed as fact."""
    from model.conf import load

    a = load()
    walked = a.walk()
    assert walked, "no assumptions loaded"
    for x in walked:
        assert x.confidence in {"high", "medium", "low", "speculative"}, x.key
    # UNSOURCED is allowed but must be deliberate; this pins the current count so a
    # new unsourced number has to be acknowledged rather than slipped in.
    assert len(a.unsourced()) == 0, f"unsourced: {a.unsourced()}"
