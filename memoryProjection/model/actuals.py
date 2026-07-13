"""Observed data through 2026Q2. Reality overrides the model.

Every quarter up to `actuals_end` is pinned to what actually happened. The model still
computes those quarters -- that is the backcast, and it is how we find out whether the
machinery works -- but the reported lines use the observed values.

WHAT CAN AND CANNOT BE PINNED. This distinction is not a technicality:

  SUPPLY is observable. Bits were produced; the number exists. Pinned.
  DEMAND DRIVERS are observable. PC units, phone units, accelerator units. Pinned.
  DEMAND is NOT observable, and never will be.

"Bits the world would consume at constant 2025 prices" is a counterfactual. What was
observed in 2026 is what actually cleared -- at 2026's prices, after phone makers cut
memory content and PC OEMs killed low-end SKUs. That rationed outcome is not demand;
it is demand after the shortage got done with it. So the demand line stays a modelled
construct even in the past, built from actual unit drivers and trend content.

The practical consequence for the charts: the SUPPLY line has no uncertainty band
before 2026Q2, because it is measured. The DEMAND line has one everywhere, because it
is inferred everywhere.
"""

from __future__ import annotations

from .calendar import Quarter
from .config import Assumptions


def actuals_end(a: Assumptions) -> Quarter:
    return Quarter.parse(str(a.value("actuals.actuals_end")))


def is_actual(a: Assumptions, q: Quarter) -> bool:
    return q <= actuals_end(a)


def _lookup(a: Assumptions, path: str, q: Quarter) -> float | None:
    """Observed series are keyed by quarter label ('2026Q1'), not by year."""
    try:
        series = a.value(path)
    except KeyError:
        return None
    if not isinstance(series, dict):
        return None
    return series.get(q.label)


def dram_supply_bits(a: Assumptions, q: Quarter) -> float | None:
    from . import units

    eb = _lookup(a, "actuals.dram_supply_eb_per_quarter", q)
    return units.eb_to_bits(eb) if eb is not None else None


def nand_supply_bits(a: Assumptions, q: Quarter) -> float | None:
    from . import units

    eb = _lookup(a, "actuals.nand_supply_eb_per_quarter", q)
    return units.eb_to_bits(eb) if eb is not None else None


def accelerator_units(a: Assumptions, q: Quarter) -> float | None:
    m = _lookup(a, "actuals.accelerator_units_millions_per_quarter", q)
    return m * 1e6 if m is not None else None


def conventional_units(a: Assumptions, segment: str, q: Quarter) -> float | None:
    """PC / smartphone / traditional-server unit shipments, in units (not millions)."""
    path = {
        "pc": "actuals.pc_units_millions_per_quarter",
        "smartphone": "actuals.smartphone_units_millions_per_quarter",
        "servers_traditional": "actuals.server_units_millions_per_quarter",
    }.get(segment)
    if path is None:
        return None
    m = _lookup(a, path, q)
    return m * 1e6 if m is not None else None
