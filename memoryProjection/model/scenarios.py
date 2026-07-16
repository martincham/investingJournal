"""Scenarios, the sensitivity tornado, and the top-level run."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import china, config, demand, supply
from .calendar import Quarter, full_timeline
from .config import Assumptions


@dataclass
class RunResult:
    name: str
    quarters: list[Quarter]
    supply: list[supply.SupplyQuarter]
    demand: list[demand.DemandQuarter]
    dram: list[china.Balance]
    nand: list[china.Balance]
    assumptions: Assumptions = field(repr=False, default=None)  # type: ignore[assignment]

    def dram_gap_at(self, label: str) -> float:
        for b in self.dram:
            if b.quarter_label == label:
                return b.global_gap
        raise KeyError(label)

    def annual(self, year: int) -> dict[str, float]:
        """Roll the four quarters of a year up for readability."""
        idx = [i for i, q in enumerate(self.quarters) if q.year == year]
        if not idx:
            raise KeyError(year)
        ds = sum(self.dram[i].global_supply_bits for i in idx)
        dd = sum(self.dram[i].global_demand_bits for i in idx)
        das = sum(self.dram[i].addressable_supply_bits for i in idx)
        dad = sum(self.dram[i].addressable_demand_bits for i in idx)
        ns = sum(self.nand[i].global_supply_bits for i in idx)
        nd = sum(self.nand[i].global_demand_bits for i in idx)
        from . import units

        return {
            "dram_supply_eb": units.bits_to_eb(ds),
            "dram_demand_eb": units.bits_to_eb(dd),
            "dram_gap": dd / ds - 1.0 if ds else 0.0,
            "dram_addressable_gap": dad / das - 1.0 if das else 0.0,
            "hbm_supply_eb": units.bits_to_eb(sum(self.supply[i].dram_hbm_bits for i in idx)),
            "nand_supply_eb": units.bits_to_eb(ns),
            "nand_demand_eb": units.bits_to_eb(nd),
            "nand_gap": nd / ns - 1.0 if ns else 0.0,
            "binding": self.supply[idx[-1]].binding_wafer_constraint,
            "hbm_binding": self.supply[idx[-1]].binding_hbm_constraint,
        }


def _apply_override(a: Assumptions, path: str, op: dict[str, Any]) -> None:
    asm = a.get(path)
    if "set" in op:
        asm.value = op["set"]
        if isinstance(asm.value, dict):
            asm.value = {int(k): v for k, v in asm.value.items()}
        return
    if "mult" in op:
        m = float(op["mult"])
        if isinstance(asm.value, dict):
            asm.value = {k: v * m for k, v in asm.value.items()}
        else:
            asm.value = asm.value * m
        return
    raise ValueError(f"override for '{path}' must specify 'set' or 'mult', got {op}")


def build_assumptions(scenario: str = "central", sliders: dict[str, float] | None = None) -> Assumptions:
    """Fresh assumption set with a scenario, then any slider multipliers, applied."""
    a = config.load()  # already an independent copy; no second deep_copy needed

    spec = a.tree["scenarios"].get(scenario)
    if spec is None:
        raise KeyError(f"unknown scenario '{scenario}'")
    for path, op in (spec.get("overrides") or {}).items():
        _apply_override(a, path, op)

    for path, factor in (sliders or {}).items():
        _apply_override(a, path, {"mult": factor})

    return a


def run(scenario: str = "central", timeline: list[Quarter] | None = None,
        sliders: dict[str, float] | None = None) -> RunResult:
    a = build_assumptions(scenario, sliders)
    tl = timeline or full_timeline()

    ss = supply.supply_series(a, tl)
    dd = demand.demand_series(a, tl)
    dram = [china.balance_dram(a, s, d) for s, d in zip(ss, dd)]
    nand = [china.balance_nand(a, s, d) for s, d in zip(ss, dd)]

    return RunResult(name=scenario, quarters=tl, supply=ss, demand=dd,
                     dram=dram, nand=nand, assumptions=a)


def tornado(target_quarter: str = "2029Q4", swing: float = 0.25) -> list[tuple[str, float, float, float]]:
    """Sensitivity of the DRAM gap to each slider variable, +/- `swing`.

    Returns (label, gap_low, gap_high, baseline), sorted by how much each input moves the
    answer. Read it for the RANKING, and for the fact that no bar crosses zero: the sign
    of the result is not an input, it is the model's structure.

    The timeline must be the FULL one, 2018 onwards, even though only 2029Q4 is read out.
    The GPU fleet accumulates vintage cohorts as it goes, so a run starting at 2026Q1 has
    no 2018-2025 vintages left to retire -- and the retirement stream is exactly what
    drives replacement demand. Running the bars on a short timeline while drawing them
    against a full-timeline baseline put the two 0.43pp apart at 2029Q4, which made the
    four levers with no effect at all render as small bars pointing the wrong way.
    """
    base = config.load()
    sliders = base.tree["scenarios"]["sliders"]
    tl = full_timeline()

    baseline = run("central", tl).dram_gap_at(target_quarter)
    rows: list[tuple[str, float, float, float]] = []

    for s in sliders:
        path, label = s["path"], s["label"]
        # china.captive_share is a fraction, not a multiplier -- scaling it is
        # meaningless. Probe its actual range instead.
        if s.get("absolute"):
            lo_a = build_assumptions("central")
            lo_a.override(path, 0.0)
            hi_a = build_assumptions("central")
            hi_a.override(path, 1.0)
            gaps = []
            for a in (lo_a, hi_a):
                ss = supply.supply_series(a, tl)
                dq = demand.demand_series(a, tl)
                bal = [china.balance_dram(a, s_, d_) for s_, d_ in zip(ss, dq)]
                gaps.append(next(b.global_gap for b in bal if b.quarter_label == target_quarter))
            lo, hi = gaps
        else:
            lo = run("central", tl, sliders={path: 1.0 - swing}).dram_gap_at(target_quarter)
            hi = run("central", tl, sliders={path: 1.0 + swing}).dram_gap_at(target_quarter)

        rows.append((label, lo, hi, abs(hi - lo)))

    rows.sort(key=lambda r: r[3], reverse=True)
    return [(label, lo, hi, baseline) for label, lo, hi, _ in rows]
