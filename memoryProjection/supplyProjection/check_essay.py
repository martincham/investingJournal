#!/usr/bin/env python3
"""Staleness guard for supply-variables.md.

The essay quotes YAML anchors inline in prose, which drifts silently the moment
someone edits assumptions/*.yaml for an unrelated reason. Each essay section is
followed by an invisible `<!-- var: dotted.path key=value ... -->` comment; this
script is the only thing that reads those comments, so the essay's prose stays
human-first while the anchors it quotes stay checked.

Three checks, run against the live YAML (loaded the same way model/config.py loads
it, so this script cannot drift from what the model actually sees):

  1. coverage — every path in ALLOWLIST (the definition of "in scope for this
     essay") is tagged somewhere in the essay.
  2. orphan   — every tagged path still resolves in the YAML (catches a rename on
     the YAML side that the essay wasn't updated for).
  3. fresh    — every tagged value still matches what the YAML says today.

ALLOWLIST is deliberately explicit rather than a walk over all of assumptions/,
because assumptions/ also holds demand-side keys this essay does not cover.
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from model import config  # noqa: E402

ESSAY_PATH = Path(__file__).resolve().parent / "supply-variables.md"

ALLOWLIST = [
    "actuals.actuals_end",
    "actuals.dram_supply_eb_per_quarter",
    "china.captive_share",
    "china.policy_risk.export_control_tightening",
    "constraints.advanced_packaging.accelerators_per_cowos_wafer",
    "constraints.advanced_packaging.cowos_wafers_kwpm",
    "constraints.hbm_backend.max_hbm_bits_eb_per_year",
    "constraints.litho.euv_dependent_share_of_dram_wafers",
    "constraints.litho.euv_layers_per_dram_wafer",
    "constraints.litho.euv_scanners_available_to_memory",
    "constraints.litho.wafer_layers_per_scanner_month",
    "constraints.other_wfe.dram_supportable_kwspm",
    "constraints.other_wfe.nand_supportable_kwspm",
    "constraints.test.max_hbm_bits_eb_per_year",
    "demand_ai.hbm_gb_per_accelerator",
    "supply_capacity.disruption_haircut",
    "supply_capacity.dram_wafer_capacity_kwspm.cxmt",
    "supply_capacity.dram_wafer_capacity_kwspm.micron",
    "supply_capacity.dram_wafer_capacity_kwspm.other",
    "supply_capacity.dram_wafer_capacity_kwspm.samsung",
    "supply_capacity.dram_wafer_capacity_kwspm.sk_hynix",
    "supply_capacity.nand_wafer_capacity_kwspm.kioxia_sandisk",
    "supply_capacity.nand_wafer_capacity_kwspm.micron",
    "supply_capacity.nand_wafer_capacity_kwspm.samsung",
    "supply_capacity.nand_wafer_capacity_kwspm.sk_hynix_solidigm",
    "supply_capacity.nand_wafer_capacity_kwspm.ymtc",
    "supply_capacity.node_conversion_loss.dram",
    "supply_capacity.node_conversion_loss.nand",
    "supply_capacity.utilisation.dram",
    "supply_capacity.utilisation.nand",
    "tech_roadmap.cxmt_density_discount",
    "tech_roadmap.dram_gb_per_wafer",
    "tech_roadmap.hbm_trade_ratio",
    "tech_roadmap.hbm_wafer_share",
    "tech_roadmap.nand_tb_per_wafer",
    "tech_roadmap.three_d_dram.density_uplift",
    "tech_roadmap.three_d_dram.first_volume_year",
    "uncertainty.correlation.supply_cluster",
    "uncertainty.sigma_2027.tech_roadmap.dram_gb_per_wafer",
]

VAR_COMMENT_RE = re.compile(r"<!--\s*var:\s*(\S+)\s+(.*?)-->")
QUARTER_KEY_RE = re.compile(r"^\d{4}Q[1-4]$")
YEAR_KEY_RE = re.compile(r"^\d{4}$")


def resolve(tree: dict, path: str):
    """Walk `path` against `tree`, preferring the longest literal key at each level.

    Most assumption paths are genuinely nested (a.b.c -> tree[a][b][c]). But
    uncertainty.yaml's sigma_2027 block stores keys that are THEMSELVES dotted
    strings (e.g. the literal key "tech_roadmap.dram_gb_per_wafer" one level
    under sigma_2027, not a further nested dict) -- model/uncertainty.py reads
    this with `a.group("uncertainty.sigma_2027")[full_key]`, i.e. a flat lookup.
    Trying the longest remaining dotted string as a literal key before falling
    back to single-part traversal handles both shapes with one function.
    """
    parts = path.split(".")
    node = tree
    while parts:
        if not isinstance(node, dict):
            raise KeyError(path)
        full_key = ".".join(parts)
        if full_key in node:
            return node[full_key]
        if parts[0] in node:
            node = node[parts[0]]
            parts = parts[1:]
            continue
        raise KeyError(path)
    return node


def parse_value(token: str):
    try:
        return float(token)
    except ValueError:
        return token


def values_match(essay_val, yaml_val) -> bool:
    if isinstance(essay_val, float) and isinstance(yaml_val, (int, float)):
        return math.isclose(essay_val, float(yaml_val), rel_tol=1e-6, abs_tol=1e-9)
    return str(essay_val) == str(yaml_val)


def check_tagged_path(path: str, kv_text: str, tree: dict) -> list[str]:
    errors = []
    try:
        assumption = resolve(tree, path)
    except KeyError:
        return [f"ORPHAN  {path}: tagged in essay but no longer resolves in assumptions/*.yaml"]

    value = assumption.value if hasattr(assumption, "value") else assumption
    pairs = [tok.split("=", 1) for tok in kv_text.split() if "=" in tok]

    if isinstance(value, dict):
        for key, val_str in pairs:
            essay_val = parse_value(val_str)
            if YEAR_KEY_RE.match(key):
                lookup_key = int(key)
            elif QUARTER_KEY_RE.match(key):
                lookup_key = key
            else:
                errors.append(f"STALE   {path}: comment key '{key}' is not a year or quarter label")
                continue
            if lookup_key not in value:
                errors.append(f"STALE   {path}: no anchor at {key} in YAML (essay says {val_str})")
                continue
            if not values_match(essay_val, value[lookup_key]):
                errors.append(
                    f"STALE   {path} @ {key}: essay says {val_str}, YAML says {value[lookup_key]}"
                )
    else:
        for key, val_str in pairs:
            essay_val = parse_value(val_str)
            if not values_match(essay_val, value):
                errors.append(f"STALE   {path}: essay says {val_str}, YAML says {value} (scalar)")

    return errors


def main() -> int:
    text = ESSAY_PATH.read_text()
    tagged = {m.group(1): m.group(2) for m in VAR_COMMENT_RE.finditer(text)}

    errors: list[str] = []

    missing = sorted(set(ALLOWLIST) - set(tagged))
    for path in missing:
        errors.append(f"MISSING {path}: in ALLOWLIST but not tagged anywhere in the essay")

    extra = sorted(set(tagged) - set(ALLOWLIST))
    for path in extra:
        errors.append(f"EXTRA   {path}: tagged in essay but not in ALLOWLIST (typo, or allowlist is stale)")

    a = config.load()
    for path, kv_text in sorted(tagged.items()):
        errors.extend(check_tagged_path(path, kv_text, a.tree))

    if errors:
        print(f"{len(errors)} problem(s) found in {ESSAY_PATH.name}:\n")
        for e in errors:
            print(f"  {e}")
        return 1

    print(f"OK — {len(tagged)} tagged variables, all covered, all fresh, no orphans.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
