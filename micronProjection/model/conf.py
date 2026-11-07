"""Assumption loading, pointed at THIS repo's assumptions/ directory.

The vendored `config.py` computes its default directory as `<parent>/../assumptions`,
which resolves to `model/assumptions` under our layout rather than the repo root's.
Rather than edit the vendored file -- which would break the byte-identity drift test
in tests/test_vendored.py -- pass the directory explicitly. Everything else about the
loader is used unchanged.
"""

from __future__ import annotations

from pathlib import Path

from model.vendor.config import Assumption, Assumptions, deep_copy
from model.vendor import config as _config

ASSUMPTIONS_DIR = Path(__file__).resolve().parent.parent / "assumptions"

__all__ = ["Assumption", "Assumptions", "deep_copy", "load", "ASSUMPTIONS_DIR"]


def load(directory: Path | None = None) -> Assumptions:
    """A fresh, independently-mutable assumption set from assumptions/*.yaml."""
    return _config.load(directory or ASSUMPTIONS_DIR)
