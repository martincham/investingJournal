"""Fiscal-year summary of a model run, as rows and as CSV.

Each frozen vintage carries one (`vintages/<YYYY-MM>/fy_summary.csv`) so the report can
show how the projection moved between vintages without re-running old code.

    ./.venv/bin/python -m report.summary vintages/2026-11/fy_summary.csv
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from model import pnl
from model.conf import load

SCENARIOS = ("central", "tight", "loose")
FIELDS = ["scenario", "fy", "kind", "revenue_usd_bn", "gross_margin", "net_income_usd_bn",
          "eps", "fcf_usd_bn", "capex_usd_bn"]


def fy_rows(run: pnl.Run, first: int = 2020, last: int = 2033) -> list[dict]:
    out = []
    for fy in range(first, last + 1):
        rr = run.fiscal_year(fy)
        if len(rr) < 4:
            continue
        rev = sum(x.revenue for x in rr)
        # Three states, so three labels. A fiscal year straddling the seams gets the
        # honest mixed one rather than being rounded to whichever end it mostly is.
        if all(x.is_actual for x in rr):
            kind = "reported"
        elif any(x.is_actual for x in rr):
            kind = "part-reported"
        elif any(x.is_guided for x in rr):
            kind = "part-guided"
        else:
            kind = "projected"
        out.append(dict(
            scenario=run.scenario, fy=fy, kind=kind,
            revenue_usd_bn=rev / 1e9,
            gross_margin=sum(x.gross_profit for x in rr) / rev if rev else 0.0,
            net_income_usd_bn=sum(x.net_income for x in rr) / 1e9,
            eps=sum(x.eps for x in rr),
            fcf_usd_bn=sum(x.fcf for x in rr) / 1e9,
            capex_usd_bn=sum(x.capex for x in rr) / 1e9,
        ))
    return out


def write(path: Path) -> Path:
    a = load()
    rows = [r for s in SCENARIOS for r in fy_rows(pnl.run(a, s))]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})
    return path


def read(path: Path) -> list[dict]:
    with path.open() as fh:
        return [
            {k: (v if k in ("scenario", "kind") else float(v)) for k, v in r.items()}
            for r in csv.DictReader(fh)
        ]


if __name__ == "__main__":
    print(f"wrote {write(Path(sys.argv[1]))}")
