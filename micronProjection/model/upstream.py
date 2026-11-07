"""The input contract against memoryProjection's memory_model.sqlite.

This is the ONLY module in the repo that touches that file, and it opens it read-only.
Everything downstream sees `BaselineQuarter` objects and never the database.

The rule this module exists to enforce: **supply and demand are taken as given.** Not
adjusted, not overlaid, not perturbed, not "corrected". memoryProjection owns the
physical lines; this repo owns price, cost and the P&L. If the bit lines look wrong,
the fix belongs upstream, in YAML, where it can be argued with -- not in a coefficient
buried here.

Consequence, stated rather than buried: every number this model emits is conditional on
those bit lines. Supply/demand uncertainty is spanned by running inside upstream's own
tight/central/loose scenarios.
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from model.conf import Assumptions
from model.vendor import units
from model.vendor.calendar import Quarter

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class BaselineQuarter:
    """One quarter of upstream's DRAM world. Every field is upstream's, verbatim.

    Frozen on purpose. The immutability is the contract: nothing downstream can
    reach in and nudge a supply number, so the "we never override the input" claim
    is enforced by the type rather than by discipline.

    Bits, not EB -- converted at this boundary via the vendored units module, so the
    Gb/GB/EB 8x footgun stays in one place.
    """

    quarter: Quarter
    is_actual: bool

    # --- supply side, as given -------------------------------------------------
    dram_supply_bits: float
    dram_commodity_bits: float
    dram_hbm_bits: float
    dram_china_bits: float

    # --- demand side, as given -------------------------------------------------
    dram_demand_bits: float          # unrationed, at constant 2025 real prices
    contested_demand_bits: float     # pc, smartphone, console, graphics, servers_trad, other
    inelastic_demand_bits: float     # hbm, ai_server_host, kv_offload, auto_industrial_iot
    inventory_bits: float            # the swing; negative = destock. Needed for the price signal.

    # --- NAND, as given --------------------------------------------------------
    # Carried at lower resolution than DRAM on purpose: upstream's README calls its own
    # NAND line the unreliable one (its backcast gate is DRAM-only), and NAND is a
    # minority of Micron's revenue. Enough to build the segment, not enough to imply
    # precision upstream does not claim.
    nand_supply_bits: float
    nand_demand_bits: float
    nand_gap: float

    # --- headline, as given ----------------------------------------------------
    gap: float                       # demand/supply - 1, a fraction
    addressable_gap: float

    # --- capacity, for the Micron bit split ------------------------------------
    installed_kwspm: float           # global DRAM wafer starts per month, thousands
    hbm_wafer_share: float
    hbm_is_capped: bool
    binding_wafer_constraint: str

    @property
    def contested_supply_bits(self) -> float:
        """Bits left for the contested pool after the inelastic core is served in full.

        The full-service assumption is upstream's own finding, not ours: AGENTS.md
        states the inelastic core "always fits under supply" and that HBM runs in
        slight surplus in every quarter. test_hbm_is_never_capped_upstream verifies
        that still holds in the file we actually loaded.
        """
        return self.dram_supply_bits - self.inelastic_demand_bits


@dataclass(frozen=True)
class Baseline:
    """A full scenario run of upstream's output, plus the provenance to reproduce it."""

    scenario: str
    quarters: list[BaselineQuarter]
    sha256: str
    generated_utc: str
    actuals_end: Quarter

    def at(self, label: str) -> BaselineQuarter:
        for b in self.quarters:
            if b.quarter.label == label:
                return b
        raise KeyError(f"{label} not in baseline (have {self.quarters[0].quarter}..{self.quarters[-1].quarter})")

    @property
    def projected(self) -> list[BaselineQuarter]:
        return [b for b in self.quarters if not b.is_actual]


class UpstreamMismatch(RuntimeError):
    """The input is not the file this model was calibrated against."""


def sqlite_path(a: Assumptions) -> Path:
    p = Path(a.value("upstream.sqlite_path"))
    return p if p.is_absolute() else (REPO_ROOT / p).resolve()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _connect(path: Path) -> sqlite3.Connection:
    """Read-only, and provably so.

    `mode=ro` is not politeness -- it means a stray INSERT raises instead of quietly
    mutating the other model's build artifact. test_sqlite_is_never_written leans on it.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"upstream sqlite not found at {path}. Regenerate it with:\n"
            f"    cd ../memoryProjection && ./.venv/bin/python -m report.export"
        )
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _run_meta(conn: sqlite3.Connection) -> dict[str, str]:
    return {r["key"]: r["value"] for r in conn.execute("select key, value from run_meta")}


def load_baseline(a: Assumptions, scenario: str = "central", *, strict_hash: bool = False) -> Baseline:
    """Read one scenario of upstream's DRAM output. Read-only; never writes.

    `strict_hash` raises if the input has been regenerated since calibration. Off by
    default -- upstream is allowed to re-run, and blocking on that would make this repo
    hostage to the other one. The hash always lands in run_meta either way, so any
    output traces back to the exact input that produced it.
    """
    path = sqlite_path(a)
    digest = sha256(path)
    expected = str(a.value("upstream.expected_sha256"))
    if strict_hash and digest != expected:
        raise UpstreamMismatch(
            f"upstream sqlite has changed (sha256 {digest[:12]} != expected {expected[:12]}).\n"
            f"That is allowed -- but the ASP response is calibrated against the previous bit "
            f"series, so re-run tests/test_backcast.py before trusting any projection."
        )

    contested = set(a.value("upstream.contested_segments"))
    inelastic = set(a.value("upstream.inelastic_segments"))
    inventory_seg = str(a.value("upstream.inventory_segment"))

    with _connect(path) as conn:
        meta = _run_meta(conn)
        scenarios = [s.strip() for s in meta["scenarios"].split(",")]
        if scenario not in scenarios:
            raise UpstreamMismatch(f"scenario '{scenario}' not in upstream {scenarios}")

        actuals_end = Quarter.parse(meta["actuals_end"])
        expected_end = Quarter.parse(str(a.value("upstream.expected_actuals_end")))
        if actuals_end != expected_end:
            raise UpstreamMismatch(
                f"upstream actuals_end is {actuals_end}, expected {expected_end}. The ASP pin "
                f"date and the EDGAR cutoff are both keyed to it -- reconcile before running."
            )

        balance = {
            r["quarter"]: r
            for r in conn.execute(
                "select * from balance where scenario = ? and product = 'dram'", (scenario,)
            )
        }
        nand = {
            r["quarter"]: r
            for r in conn.execute(
                "select * from balance where scenario = ? and product = 'nand'", (scenario,)
            )
        }
        detail = {
            r["quarter"]: r
            for r in conn.execute("select * from supply_detail where scenario = ?", (scenario,))
        }

        # Long -> wide, bucketing by the AGENTS.md classification. Anything upstream adds
        # that we have not classified must surface loudly rather than vanish from the
        # denominator of the price signal.
        seg: dict[str, dict[str, float]] = {}
        seen: set[str] = set()
        for r in conn.execute(
            "select quarter, segment, demand_eb from demand_segment "
            "where scenario = ? and product = 'dram'",
            (scenario,),
        ):
            seg.setdefault(r["quarter"], {})[r["segment"]] = r["demand_eb"]
            seen.add(r["segment"])

    unclassified = seen - contested - inelastic - {inventory_seg}
    if unclassified:
        raise UpstreamMismatch(
            f"upstream has DRAM segments this model does not classify: {sorted(unclassified)}. "
            f"Add them to contested_segments or inelastic_segments in assumptions/upstream.yaml "
            f"-- silently dropping a segment would bias the tightness signal."
        )

    quarters: list[BaselineQuarter] = []
    for label in sorted(balance, key=lambda s: Quarter.parse(s).index):
        b, d, s, n = balance[label], detail[label], seg.get(label, {}), nand[label]
        quarters.append(
            BaselineQuarter(
                quarter=Quarter.parse(label),
                is_actual=bool(b["is_actual"]),
                dram_supply_bits=units.eb_to_bits(b["supply_eb"]),
                dram_commodity_bits=units.eb_to_bits(d["dram_commodity_eb"]),
                dram_hbm_bits=units.eb_to_bits(d["dram_hbm_eb"]),
                dram_china_bits=units.eb_to_bits(d["dram_china_eb"]),
                dram_demand_bits=units.eb_to_bits(b["demand_eb"]),
                contested_demand_bits=units.eb_to_bits(sum(s.get(k, 0.0) for k in contested)),
                inelastic_demand_bits=units.eb_to_bits(sum(s.get(k, 0.0) for k in inelastic)),
                inventory_bits=units.eb_to_bits(s.get(inventory_seg, 0.0)),
                nand_supply_bits=units.eb_to_bits(n["supply_eb"]),
                nand_demand_bits=units.eb_to_bits(n["demand_eb"]),
                nand_gap=n["gap"],
                gap=b["gap"],
                addressable_gap=b["addressable_gap"],
                installed_kwspm=d["installed_kwspm"],
                hbm_wafer_share=d["hbm_wafer_share"],
                hbm_is_capped=bool(d["hbm_is_capped"]),
                binding_wafer_constraint=d["binding_wafer_constraint"],
            )
        )

    return Baseline(
        scenario=scenario,
        quarters=quarters,
        sha256=digest,
        generated_utc=meta["generated_utc"],
        actuals_end=actuals_end,
    )


def load_all(a: Assumptions) -> dict[str, Baseline]:
    """All three upstream scenarios. These ARE our scenarios -- we add no fourth."""
    return {s: load_baseline(a, s) for s in a.value("upstream.expected_scenarios")}


def assumption_series(a: Assumptions, key: str) -> dict[int, float]:
    """A year-anchored input from upstream's flattened `assumption` table.

    Upstream's own inputs, read verbatim. Reaching for these is not a licence to
    recompute upstream's outputs from them -- it is how we get at inputs the model pools
    away before it emits anything (per-producer capacity) or that it never emits at all
    (the CXMT density discount).
    """
    import json

    with _connect(sqlite_path(a)) as conn:
        row = conn.execute("select value_json from assumption where key = ?", (key,)).fetchone()
    if row is None:
        raise KeyError(f"no upstream assumption '{key}'")
    value = json.loads(row["value_json"])
    if not isinstance(value, dict):
        raise TypeError(f"upstream assumption '{key}' is a scalar, not a year-anchored series")
    return {int(k): float(v) for k, v in value.items()}


def wafer_capacity(a: Assumptions, producer: str) -> dict[int, float]:
    """Per-producer DRAM wafer capacity (kwspm).

    Upstream pools all producers into `installed_kwspm` on the first line of
    supply_quarter() -- there is no `micron_bits` column anywhere in that model. So
    Micron's share has to be rebuilt from these capacity inputs, which do survive in the
    flattened assumption table.
    """
    return assumption_series(a, f"supply_capacity.dram_wafer_capacity_kwspm.{producer}")
