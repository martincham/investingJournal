"""Export Micron's reported quarterly GAAP financials to data/reported/quarterly_gaap.csv.

Reads the cached SEC companyfacts file (data/edgar/companyfacts.json) through
model.edgar.load, so FQ4 is backed out as FY - 9M exactly as the model does it. Never
touches the network: refresh the cache separately with `edgar.fetch(force=True)`.

    ./.venv/bin/python data/export_reported.py
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from model import edgar  # noqa: E402

OUT = ROOT / "data" / "reported" / "quarterly_gaap.csv"

USD_FIELDS = [
    "revenue", "cogs", "gross_profit", "rnd", "sga", "ebit", "tax", "net_income",
    "dna", "capex", "ocf", "buyback", "dividend", "inventory",
]


def main() -> Path:
    doc = edgar.fetch(max_age_days=3650)  # cache only; never refetch from here
    quarters = edgar.load(doc)

    cols = (
        ["fiscal_label", "calendar_quarter", "start", "end", "days"]
        + [f"{f}_usd_m" for f in USD_FIELDS]
        + ["diluted_shares_m", "eps_diluted_recomputed", "eps_diluted_reported",
           "gross_margin", "operating_margin", "fcf_usd_m"]
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for q in quarters:
            m = lambda v: "" if math.isnan(v) else round(v / 1e6, 1)  # noqa: E731
            r = lambda v, n: "" if math.isnan(v) else round(v, n)  # noqa: E731
            w.writerow(
                [q.fiscal.label, str(q.calendar), q.fiscal.start, q.fiscal.end, q.fiscal.days]
                + [m(getattr(q, f)) for f in USD_FIELDS]
                + [m(q.diluted_shares), r(q.eps, 2), r(q.eps_reported, 2),
                   r(q.gross_margin, 4), r(q.operating_margin, 4), m(q.fcf)]
            )
    return OUT


if __name__ == "__main__":
    out = main()
    print(f"wrote {out}")
