"""The export runs end to end and every table micronProjection or the vintage page reads
is populated. Added after a column-count mismatch in the market table shipped unnoticed."""

import sqlite3

from report.export import export


def test_export_writes_every_table(tmp_path):
    db = export(tmp_path / "m.sqlite")
    c = sqlite3.connect(db)
    for table in ("balance", "demand_segment", "demand_segment_at_price", "supply_detail",
                  "annual_summary", "uncertainty_band", "market", "run_meta"):
        assert c.execute(f"select count(*) from {table}").fetchone()[0] > 0, table
    assert c.execute("select value from run_meta where key='market_kappa'").fetchone()
