"""Freeze the current report outputs as a named vintage: vintages/<id>/.

A vintage is what this model believed at a point in time, kept exactly as it was
produced. It is NOT re-run on later code. Re-running July's assumptions through
November's model would give a third thing that nobody ever believed. The git commit
in VINTAGE.md is enough to rebuild it if that is ever needed.

Copies:
    report/memory_model.sqlite  -> vintages/<id>/memory_model.sqlite
    report/memory_model.html    -> vintages/<id>/memory_model.html
    assumptions/*.yaml          -> vintages/<id>/assumptions/
and writes vintages/<id>/VINTAGE.md (commit, actuals cutoff, sqlite sha256).

Run:  ./.venv/bin/python -m report.freeze 2026-11 [--commit <sha>] [--note "..."]

Refuses to overwrite an existing vintage. A frozen vintage is a record, and
micronProjection pins one by sha256.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "report"
VINTAGES = ROOT / "vintages"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _run_meta(db: Path) -> dict[str, str]:
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as c:
        return dict(c.execute("select key, value from run_meta").fetchall())


def freeze(vid: str, commit: str | None, note: str) -> Path:
    if not re.fullmatch(r"\d{4}-\d{2}", vid):
        sys.exit(f"vintage id must be YYYY-MM, got {vid!r}")
    dest = VINTAGES / vid
    if dest.exists():
        sys.exit(f"{dest} already exists; vintages are never overwritten")

    db, html = REPORT / "memory_model.sqlite", REPORT / "memory_model.html"
    for p in (db, html):
        if not p.exists():
            sys.exit(f"missing {p}; run report.build and report.export first")

    if commit is None:
        dirty = _git("status", "--porcelain", "--", "model", "assumptions")
        if dirty:
            sys.exit(
                "model/ or assumptions/ has uncommitted changes, so no commit can "
                "reproduce this run. Commit first, or pass --commit explicitly.\n" + dirty
            )
        commit = _git("rev-parse", "--short", "HEAD")

    meta = _run_meta(db)
    digest = hashlib.sha256(db.read_bytes()).hexdigest()

    dest.mkdir(parents=True)
    shutil.copy2(db, dest / db.name)
    shutil.copy2(html, dest / html.name)
    shutil.copytree(ROOT / "assumptions", dest / "assumptions")

    (dest / "VINTAGE.md").write_text(
        f"# Memory projection vintage {vid}\n\n"
        f"| | |\n|---|---|\n"
        f"| Source commit | `{commit}` |\n"
        f"| Observed data through | {meta.get('actuals_end', '?')} |\n"
        f"| Generated (UTC) | {meta.get('generated_utc', '?')} |\n"
        f"| Scenarios | {meta.get('scenarios', '?')} |\n"
        f"| memory_model.sqlite sha256 | `{digest}` |\n\n"
        f"{note.strip()}\n\n"
        "Frozen output. Do not edit or re-run. `assumptions/` is a copy of the inputs\n"
        "that produced it, so `diff -r vintages/<old>/assumptions vintages/<new>/assumptions`\n"
        "shows what changed between projections.\n"
    )
    print(f"froze {vid}: sha256 {digest[:12]}, actuals through {meta.get('actuals_end')}")
    return dest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("vintage", help="YYYY-MM")
    ap.add_argument("--commit", help="commit that produced the outputs (default: HEAD, must be clean)")
    ap.add_argument("--note", default="", help="one paragraph on what this vintage is")
    a = ap.parse_args()
    freeze(a.vintage, a.commit, a.note)


if __name__ == "__main__":
    main()
