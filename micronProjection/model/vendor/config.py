"""Loader for the assumptions/*.yaml files.

Every number in this model lives in YAML, not in code, and every number carries a
source URL and a confidence tag. Two reasons:

1. The assumption files double as the research record. You can read them to see what
   the model believes and where it got it, without reading any Python.
2. Disagreeing with the model becomes a one-line edit, not a code change.

A leaf assumption is any mapping with a `value` key. The loader wraps those in
`Assumption` and leaves everything else as plain nested dicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ASSUMPTIONS_DIR = Path(__file__).resolve().parent.parent / "assumptions"

VALID_CONFIDENCE = {"high", "medium", "low", "speculative"}


def _is_year(k: Any) -> bool:
    try:
        return 1900 <= int(k) <= 2100
    except (TypeError, ValueError):
        return False


@dataclass
class Assumption:
    """A single model input, with its provenance."""

    value: Any
    source: str = "UNSOURCED"
    confidence: str = "low"
    notes: str = ""
    unit: str = ""
    key: str = ""

    def __post_init__(self) -> None:
        if self.confidence not in VALID_CONFIDENCE:
            raise ValueError(
                f"{self.key}: confidence '{self.confidence}' not in {sorted(VALID_CONFIDENCE)}"
            )
        # Two kinds of keyed series live here:
        #   YEAR-anchored ({2025: 39.0})    -- interpolated onto quarters
        #   QUARTER-keyed ({'2026Q1': 10})  -- observed data, looked up exactly
        # Coerce year keys to int (a stray quoted year would silently break
        # interpolation), and leave quarter labels alone.
        if isinstance(self.value, dict):
            keys = list(self.value)
            if keys and all(_is_year(k) for k in keys):
                self.value = {int(k): v for k, v in self.value.items()}

    def __float__(self) -> float:
        if isinstance(self.value, dict):
            raise TypeError(f"{self.key}: is a year-anchored series, not a scalar")
        return float(self.value)


@dataclass
class Assumptions:
    """The full assumption set, addressed by dotted path."""

    tree: dict[str, Any] = field(default_factory=dict)

    def get(self, path: str) -> Assumption:
        node: Any = self.tree
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                raise KeyError(f"no assumption at '{path}' (failed at '{part}')")
            node = node[part]
        if not isinstance(node, Assumption):
            raise KeyError(f"'{path}' is a group, not a leaf assumption")
        return node

    def value(self, path: str) -> Any:
        return self.get(path).value

    def scalar(self, path: str) -> float:
        return float(self.get(path))

    def series(self, path: str) -> dict[int, float]:
        v = self.get(path).value
        if not isinstance(v, dict):
            raise TypeError(f"'{path}' is a scalar, not a year-anchored series")
        return v

    def group(self, path: str) -> dict[str, Any]:
        node: Any = self.tree
        for part in path.split("."):
            node = node[part]
        if isinstance(node, Assumption):
            raise KeyError(f"'{path}' is a leaf, not a group")
        return node

    def override(self, path: str, value: Any) -> None:
        """Replace an assumption's value in place. Used by scenarios and the sliders."""
        self.get(path).value = value

    def walk(self) -> list[Assumption]:
        out: list[Assumption] = []

        def rec(node: Any) -> None:
            if isinstance(node, Assumption):
                out.append(node)
            elif isinstance(node, dict):
                for v in node.values():
                    rec(v)

        rec(self.tree)
        return out

    def audit(self) -> dict[str, int]:
        """Count assumptions by confidence. A model whose headline output rests on
        'speculative' inputs should say so out loud rather than imply false precision."""
        counts = dict.fromkeys(VALID_CONFIDENCE, 0)
        for a in self.walk():
            counts[a.confidence] += 1
        return counts

    def unsourced(self) -> list[str]:
        return [a.key for a in self.walk() if a.source == "UNSOURCED"]


def _wrap(node: Any, prefix: str = "") -> Any:
    if isinstance(node, dict):
        if "value" in node:
            return Assumption(
                value=node["value"],
                source=node.get("source", "UNSOURCED"),
                confidence=node.get("confidence", "low"),
                notes=node.get("notes", ""),
                unit=node.get("unit", ""),
                key=prefix,
            )
        return {k: _wrap(v, f"{prefix}.{k}" if prefix else k) for k, v in node.items()}
    return node


_CACHE: dict[Path, dict[str, Any]] = {}


def _parse(directory: Path) -> dict[str, Any]:
    tree: dict[str, Any] = {}
    for path in sorted(directory.glob("*.yaml")):
        with path.open() as fh:
            raw = yaml.safe_load(fh) or {}
        tree[path.stem] = _wrap(raw, path.stem)
    if not tree:
        raise FileNotFoundError(f"no assumption files found in {directory}")
    return tree


def load(directory: Path | None = None) -> Assumptions:
    """A fresh, independently-mutable assumption set.

    The YAML is parsed ONCE per directory and cached; each call deep-copies the cached
    tree. Callers mutate what they get back (that is how scenarios and sliders work), so
    handing out a shared tree would let one run's overrides leak into the next.

    The cache matters: `build_assumptions` is called once per Monte Carlo draw, so a
    400-draw run was re-parsing ten YAML files 400 times -- and then deep-copying the
    freshly-parsed tree a second time for good measure.
    """
    import copy

    directory = directory or ASSUMPTIONS_DIR
    if directory not in _CACHE:
        _CACHE[directory] = _parse(directory)
    return Assumptions(copy.deepcopy(_CACHE[directory]))


def deep_copy(a: Assumptions) -> Assumptions:
    """Fresh copy so a scenario's overrides don't leak into the next run.

    Note `load()` already returns an independent copy, so this is only needed when
    branching from an assumption set you have already modified.
    """
    import copy

    return Assumptions(copy.deepcopy(a.tree))
