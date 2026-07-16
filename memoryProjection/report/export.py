"""Export every model output to a single SQLite file: report/memory_model.sqlite.

The HTML report is for reading; this file is for querying. Same runs, same numbers,
but in relational form so anything downstream (pandas, DuckDB, Excel, Datasette, a
notebook) can get at them without re-running the model or scraping JSON out of HTML.

Layout mirrors the model's own structure:

    run_meta            when/what was exported, actuals cutoff, assumption audit
    balance             the headline: supply/demand/gap per scenario x quarter x product
    supply_detail       DRAM/NAND composition + which of C1-C6 binds, per quarter
    demand_segment      the demand build-up, one row per segment (long format)
    fleet               GPU fleet: shipments, retirements, replacement share, power
    power_pipeline      announced vs delivered datacentre GW
    vintage_viability   when each GPU vintage dies, by each retirement rule
    capex_crosscheck    bottom-up vs top-down accelerator counts
    uncertainty_band    P10/P50/P90 Monte Carlo bands (central scenario)
    annual_summary      year rollups, 2018-2032, per scenario
    tornado             sensitivity of the 2029Q4 DRAM gap to each slider
    assumption          every input, flattened: value JSON + source + confidence

Conventions: quantities are EB per quarter unless the column says otherwise
(_eb_yr = annualised, _gw = gigawatts, gap columns are fractions, not %).
Run:  ./.venv/bin/python -m report.export
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from model import config, scenarios, units, uncertainty
from model.actuals import actuals_end
from model.calendar import full_timeline
from model.datacenter import power_series
from model.fleet import retirement_dates

HERE = Path(__file__).resolve().parent
DB = HERE / "memory_model.sqlite"

SCENARIOS = ("tight", "central", "loose")

SCHEMA = """
CREATE TABLE run_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE balance (
    scenario  TEXT NOT NULL,
    quarter   TEXT NOT NULL,
    year      INTEGER NOT NULL,
    q         INTEGER NOT NULL,
    product   TEXT NOT NULL,              -- 'dram' | 'nand'  (never sum the two)
    is_actual INTEGER NOT NULL,           -- 1 = pinned to observed data
    supply_eb  REAL NOT NULL,             -- per quarter
    demand_eb  REAL NOT NULL,             -- unrationed, at constant 2025 prices
    gap        REAL NOT NULL,             -- demand/supply - 1 (global scope)
    addressable_gap REAL NOT NULL,        -- ex-captive-China merchant scope
    deficit_eb REAL NOT NULL,             -- demand - supply, scope-invariant
    captive_eb REAL NOT NULL,             -- Chinese bits absorbed domestically
    PRIMARY KEY (scenario, quarter, product)
);

CREATE TABLE supply_detail (
    scenario  TEXT NOT NULL,
    quarter   TEXT NOT NULL,
    is_actual INTEGER NOT NULL,
    dram_total_eb     REAL NOT NULL,
    dram_commodity_eb REAL NOT NULL,
    dram_hbm_eb       REAL NOT NULL,
    dram_china_eb     REAL NOT NULL,
    nand_total_eb     REAL NOT NULL,
    nand_china_eb     REAL NOT NULL,
    installed_kwspm   REAL NOT NULL,
    hbm_wafer_share   REAL NOT NULL,
    binding_wafer_constraint TEXT NOT NULL,   -- C1/C2/C3, the one that bound
    wafer_margin_to_next     REAL NOT NULL,   -- slack behind it, fraction
    binding_hbm_constraint   TEXT NOT NULL,   -- C4/C5/C6, '' when HBM is uncapped
    hbm_is_capped            INTEGER NOT NULL,
    PRIMARY KEY (scenario, quarter)
);

CREATE TABLE demand_segment (
    scenario TEXT NOT NULL,
    quarter  TEXT NOT NULL,
    product  TEXT NOT NULL,               -- 'dram' | 'nand'
    segment  TEXT NOT NULL,               -- hbm, ai_server_host, pc, inventory, ...
    demand_eb REAL NOT NULL,              -- per quarter; inventory can be negative
    PRIMARY KEY (scenario, quarter, product, segment)
);

CREATE TABLE fleet (
    scenario TEXT NOT NULL,
    quarter  TEXT NOT NULL,
    shipments_units    REAL NOT NULL,     -- accelerators shipped this quarter
    retirements_units  REAL NOT NULL,
    replacement_share  REAL NOT NULL,     -- fraction of shipments refilling freed watts
    fleet_units        REAL NOT NULL,
    fleet_power_gw     REAL NOT NULL,
    available_power_gw REAL NOT NULL,
    power_scarce       INTEGER NOT NULL,
    binding_demand_constraint TEXT NOT NULL,  -- capex | power | packaging
    efficiency_multiplier REAL NOT NULL,
    kv_working_set_eb  REAL NOT NULL,
    capex_implied_accelerators REAL NOT NULL,
    PRIMARY KEY (scenario, quarter)
);

CREATE TABLE power_pipeline (
    scenario TEXT NOT NULL,
    quarter  TEXT NOT NULL,
    announced_gw_yr REAL NOT NULL,        -- gross announcements, annualised
    delivered_gw_yr REAL NOT NULL,        -- net of attrition, annualised
    cancelled_gw    REAL NOT NULL,        -- never built
    slipped_gw      REAL NOT NULL,        -- late, rolls forward
    cumulative_gw   REAL NOT NULL,        -- installed AI DC power available
    PRIMARY KEY (scenario, quarter)
);

CREATE TABLE vintage_viability (
    scenario TEXT NOT NULL,
    vintage_year INTEGER NOT NULL,
    tflops_per_watt REAL NOT NULL,
    hbm_gb REAL NOT NULL,
    cash_unviable TEXT,                   -- quarter label, NULL if never
    power_evicted TEXT,                   -- quarter label, NULL if never
    PRIMARY KEY (scenario, vintage_year)
);

CREATE TABLE capex_crosscheck (
    scenario TEXT NOT NULL,
    year INTEGER NOT NULL,
    bottom_up_millions REAL NOT NULL,     -- effective accelerators (post power cap)
    top_down_millions  REAL NOT NULL,     -- capex / ASP
    divergence         REAL NOT NULL,     -- fraction
    power_capped       INTEGER NOT NULL,
    PRIMARY KEY (scenario, year)
);

CREATE TABLE uncertainty_band (
    scenario TEXT NOT NULL,               -- bands are run for 'central' only
    quarter  TEXT NOT NULL,
    supply_p10 REAL, supply_p50 REAL, supply_p90 REAL,   -- EB/yr, annualised
    demand_p10 REAL, demand_p50 REAL, demand_p90 REAL,   -- EB/yr, annualised
    gap_p10 REAL, gap_p50 REAL, gap_p90 REAL,            -- percent (as emitted)
    p_gap_closed REAL,                    -- P(gap <= 0) across draws
    PRIMARY KEY (scenario, quarter)
);

CREATE TABLE annual_summary (
    scenario TEXT NOT NULL,
    year INTEGER NOT NULL,
    dram_supply_eb REAL, dram_demand_eb REAL, dram_gap REAL,
    dram_addressable_gap REAL, hbm_supply_eb REAL,
    nand_supply_eb REAL, nand_demand_eb REAL, nand_gap REAL,
    binding TEXT, hbm_binding TEXT,
    PRIMARY KEY (scenario, year)
);

CREATE TABLE tornado (
    scenario TEXT NOT NULL,
    rank INTEGER NOT NULL,                -- 1 = most sensitive
    slider TEXT NOT NULL,
    gap_low REAL NOT NULL,                -- gap at the low end of the slider's swing
    gap_high REAL NOT NULL,
    gap_baseline REAL NOT NULL,
    target_quarter TEXT NOT NULL,
    PRIMARY KEY (scenario, rank)
);

CREATE TABLE assumption (
    key TEXT PRIMARY KEY,                 -- dotted path
    value_json TEXT NOT NULL,             -- scalar or {year: value} series, as JSON
    unit TEXT,
    source TEXT,
    confidence TEXT,
    notes TEXT
);
"""


def export(db_path: Path = DB) -> Path:
    tl = full_timeline()
    runs = {s: scenarios.run(s, tl) for s in SCENARIOS}
    a_central = runs["central"].assumptions

    db_path.unlink(missing_ok=True)
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)

    audit = config.load().audit()
    con.executemany(
        "INSERT INTO run_meta VALUES (?, ?)",
        [
            ("generated_utc", datetime.now(timezone.utc).isoformat(timespec="seconds")),
            ("actuals_end", actuals_end(a_central).label),
            ("timeline", f"{tl[0].label}..{tl[-1].label}"),
            ("scenarios", ",".join(SCENARIOS)),
            ("confidence_audit", json.dumps(audit)),
            ("units_note", "EB per quarter unless column name says _yr/_gw; gaps are fractions"),
            ("demand_definition", "unrationed demand at constant 2025 real prices -- "
                                  "the gap is a pressure index, not a physical shortfall"),
        ],
    )

    for name, run in runs.items():
        # balance -- one row per quarter per product
        rows = []
        for q, s, dbal, nbal in zip(run.quarters, run.supply, run.dram, run.nand):
            for product, b in (("dram", dbal), ("nand", nbal)):
                rows.append((
                    name, q.label, q.year, q.q, product, int(s.is_actual),
                    b.global_supply_eb, b.global_demand_eb,
                    b.global_gap, b.addressable_gap,
                    b.deficit_eb, units.bits_to_eb(b.captive_bits),
                ))
        con.executemany(f"INSERT INTO balance VALUES ({','.join('?' * 12)})", rows)

        con.executemany(
            f"INSERT INTO supply_detail VALUES ({','.join('?' * 15)})",
            [(name, s.quarter.label, int(s.is_actual),
              s.dram_eb, units.bits_to_eb(s.dram_commodity_bits), s.hbm_eb,
              units.bits_to_eb(s.dram_china_bits),
              s.nand_eb, units.bits_to_eb(s.nand_china_bits),
              s.installed_kwspm, s.hbm_wafer_share,
              s.binding_wafer_constraint, s.wafer_margin_to_next,
              s.binding_hbm_constraint, int(s.hbm_is_capped))
             for s in run.supply],
        )

        seg_rows = []
        for d in run.demand:
            for product, segs in (("dram", d.dram_by_segment), ("nand", d.nand_by_segment)):
                for seg, bits in segs.items():
                    seg_rows.append((name, d.quarter.label, product, seg,
                                     units.bits_to_eb(bits)))
        con.executemany("INSERT INTO demand_segment VALUES (?,?,?,?,?)", seg_rows)

        con.executemany(
            f"INSERT INTO fleet VALUES ({','.join('?' * 13)})",
            [(name, d.quarter.label, d.accelerators, d.retirements,
              d.replacement_share, d.fleet_units, d.fleet_power_gw,
              d.available_power_gw, int(d.power_capped), d.binding_demand_constraint,
              d.efficiency_multiplier, units.bits_to_eb(d.kv_working_set_bits),
              d.capex_implied_accelerators)
             for d in run.demand],
        )

        pw = power_series(run.assumptions, tl)
        con.executemany(
            "INSERT INTO power_pipeline VALUES (?,?,?,?,?,?,?)",
            [(name, p.quarter.label, p.announced_gw, p.delivered_gw,
              p.cancelled_gw, p.slipped_gw, p.cumulative_gw) for p in pw],
        )

        rd = retirement_dates(run.assumptions, tl)
        con.executemany(
            "INSERT INTO vintage_viability VALUES (?,?,?,?,?,?)",
            [(name, vy, d["tflops_per_watt"], d["hbm_gb"],
              d["cash_unviable"], d["power_evicted"]) for vy, d in sorted(rd.items())],
        )

        cx_rows = []
        for q, d in zip(run.quarters, run.demand):
            if q.q != 4 or q.year < 2024:
                continue
            top_down = d.capex_implied_accelerators * 4 / 1e6
            bottom_up = d.accelerators * 4 / 1e6
            div = (bottom_up / top_down - 1) if top_down else 0.0
            cx_rows.append((name, q.year, bottom_up, top_down, div, int(d.power_capped)))
        con.executemany("INSERT INTO capex_crosscheck VALUES (?,?,?,?,?,?)", cx_rows)

        con.executemany(
            f"INSERT INTO annual_summary VALUES ({','.join('?' * 12)})",
            [(name, y, *(run.annual(y)[k] for k in (
                "dram_supply_eb", "dram_demand_eb", "dram_gap", "dram_addressable_gap",
                "hbm_supply_eb", "nand_supply_eb", "nand_demand_eb", "nand_gap",
                "binding", "hbm_binding")))
             for y in range(tl[0].year, tl[-1].year + 1)],
        )

    band = uncertainty.run_bands("central", tl)
    con.executemany(
        f"INSERT INTO uncertainty_band VALUES ({','.join('?' * 12)})",
        [("central", band.quarters[i],
          band.supply_p10[i], band.supply_p50[i], band.supply_p90[i],
          band.demand_p10[i], band.demand_p50[i], band.demand_p90[i],
          band.gap_p10[i], band.gap_p50[i], band.gap_p90[i],
          band.p_gap_closed[i])
         for i in range(len(band.quarters))],
    )

    target = "2029Q4"
    tor = scenarios.tornado(target)
    baseline = runs["central"].dram_gap_at(target)
    con.executemany(
        "INSERT INTO tornado VALUES (?,?,?,?,?,?,?)",
        [("central", i + 1, label, lo, hi, baseline, target)
         for i, (label, lo, hi, _) in enumerate(tor)],
    )

    con.executemany(
        "INSERT INTO assumption VALUES (?,?,?,?,?,?)",
        [(asm.key, json.dumps(asm.value), asm.unit, asm.source, asm.confidence,
          asm.notes.strip()) for asm in config.load().walk()],
    )

    con.commit()
    con.close()
    return db_path


def main() -> None:
    path = export()
    con = sqlite3.connect(path)
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    counts = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables}
    con.close()
    print(f"wrote {path}  ({path.stat().st_size / 1e6:.1f} MB)")
    for t, n in counts.items():
        print(f"  {t:<20} {n:>6} rows")


if __name__ == "__main__":
    main()
