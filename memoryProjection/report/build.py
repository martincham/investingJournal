"""Build the self-contained interactive HTML report.

Runs the model across scenarios and slider positions, then emits a single HTML file
with everything embedded -- no CDN, no network, opens from disk.

The slider explorer is ONE-FACTOR-AT-A-TIME: each slider moves its own variable away
from Central while everything else is held. Combined moves are covered by the three
preset scenarios rather than faked by superposing single-factor deltas, which would
quietly assume the model is linear when it is not.
"""

from __future__ import annotations

import json
from pathlib import Path

from model import config, scenarios, units
from model.calendar import Quarter, full_timeline

HERE = Path(__file__).resolve().parent
OUT = HERE / "memory_model.html"

SLIDER_POSITIONS = [0.5, 0.7, 0.85, 1.0, 1.15, 1.3, 1.5]

# Fold the model's demand segments into <= 8 stack bands. A 9th series is never a
# generated hue -- it folds into "Other".
DEMAND_BANDS = {
    "HBM (AI accelerators)": ["hbm"],
    "AI server host DRAM": ["ai_server_host", "kv_offload"],
    "Servers (traditional)": ["servers_traditional"],
    "Smartphone": ["smartphone"],
    "PC": ["pc"],
    "Graphics + console": ["graphics", "console"],
    "Auto / industrial / other": ["auto_industrial_iot", "other"],
    "Inventory swing": ["inventory"],
}

CONSTRAINT_LABEL = {
    "C1_wafer_capacity": "C1 Cleanroom / wafer capacity",
    "C2_lithography": "C2 Lithography (EUV)",
    "C3_other_wfe": "C3 Other WFE (etch/depo)",
}


def series(run) -> dict:
    q = [x.label for x in run.quarters]
    return {
        "quarters": q,
        "dram_supply": [b.global_supply_eb * 4 for b in run.dram],   # annualised EB/yr
        "dram_demand": [b.global_demand_eb * 4 for b in run.dram],
        "dram_gap": [b.global_gap * 100 for b in run.dram],
        "dram_merchant_gap": [b.addressable_gap * 100 for b in run.dram],
        "dram_deficit": [b.deficit_eb * 4 for b in run.dram],
        "nand_supply": [b.global_supply_eb * 4 for b in run.nand],
        "nand_demand": [b.global_demand_eb * 4 for b in run.nand],
        "nand_gap": [b.global_gap * 100 for b in run.nand],
        "binding": [s.binding_wafer_constraint for s in run.supply],
        "binding_margin": [s.wafer_margin_to_next * 100 for s in run.supply],
        "hbm_supply": [units.bits_to_eb(s.dram_hbm_bits) * 4 for s in run.supply],
    }


def demand_stack(run) -> dict:
    out: dict[str, list[float]] = {}
    for band, keys in DEMAND_BANDS.items():
        out[band] = [
            sum(units.bits_to_eb(d.dram_by_segment.get(k, 0.0)) * 4 for k in keys)
            for d in run.demand
        ]
    return out


def capex_crosscheck(run) -> list[dict]:
    rows = []
    for q, d in zip(run.quarters, run.demand):
        if q.year >= 2025 and q.q == 4:
            # Compare the EFFECTIVE accelerator count -- what the model actually feeds
            # into demand after the power ceiling -- against the capex-implied number.
            # Comparing the pre-cap figure would flag a divergence the model does not
            # actually have.
            effective = d.accelerators * 4 / 1e6
            top_down = d.capex_implied_accelerators * 4 / 1e6
            div = (effective / top_down - 1) * 100 if top_down else 0.0
            rows.append({
                "year": q.year,
                "bottom_up_m": round(effective, 1),
                "top_down_m": round(top_down, 1),
                "divergence_pct": round(div, 1),
                "power_capped": d.power_capped,
            })
    return rows


def fleet_payload(run) -> dict:
    return {
        "quarters": [q.label for q in run.quarters],
        "shipments": [d.accelerators * 4 / 1e6 for d in run.demand],
        "retirements": [d.retirements * 4 / 1e6 for d in run.demand],
        "replacement_share": [d.replacement_share * 100 for d in run.demand],
        "fleet_units": [d.fleet_units / 1e6 for d in run.demand],
        "fleet_power_gw": [d.fleet_power_gw for d in run.demand],
        "available_power_gw": [d.available_power_gw for d in run.demand],
    }


def pipeline_payload(a) -> dict:
    from model.datacenter import power_series

    tl = full_timeline()
    pw = power_series(a, tl)
    return {
        "quarters": [p.quarter.label for p in pw],
        "announced": [p.announced_gw for p in pw],
        "delivered": [p.delivered_gw for p in pw],
        "cumulative": [p.cumulative_gw for p in pw],
    }


def viability_payload(a) -> list[dict]:
    from model.fleet import retirement_dates

    rd = retirement_dates(a, full_timeline())
    return [
        {
            "vintage": vy,
            "tflops_per_watt": d["tflops_per_watt"],
            "hbm_gb": d["hbm_gb"],
            "cash_unviable": d["cash_unviable"] or "—",
            "power_evicted": d["power_evicted"] or "—",
        }
        for vy, d in sorted(rd.items())
        if vy <= 2029
    ]


def build_payload() -> dict:
    runs = {s: scenarios.run(s, full_timeline()) for s in ("tight", "central", "loose")}
    central = runs["central"]

    sliders_meta = config.load().tree["scenarios"]["sliders"]
    slider_data = []
    for s in sliders_meta:
        path, label = s["path"], s["label"]
        if s.get("absolute"):
            positions, gaps = [], []
            for v in (0.0, 0.25, 0.5, 0.75, 1.0):
                a = scenarios.build_assumptions("central")
                a.override(path, v)
                from model import china as ch
                from model import demand as dm
                from model import supply as sp
                tl = full_timeline()
                ss, dd = sp.supply_series(a, tl), dm.demand_series(a, tl)
                bal = [ch.balance_dram(a, x, y) for x, y in zip(ss, dd)]
                positions.append(v)
                gaps.append([b.global_gap * 100 for b in bal])
            slider_data.append({
                "path": path, "label": label, "help": s.get("help", ""),
                "absolute": True, "positions": positions, "gaps": gaps, "default_index": 4,
            })
        else:
            gaps = [
                [b.global_gap * 100 for b in scenarios.run("central", full_timeline(),
                                                           sliders={path: p}).dram]
                for p in SLIDER_POSITIONS
            ]
            slider_data.append({
                "path": path, "label": label, "help": s.get("help", ""),
                "absolute": False, "positions": SLIDER_POSITIONS, "gaps": gaps,
                "default_index": SLIDER_POSITIONS.index(1.0),
            })

    tor = scenarios.tornado("2029Q4")
    # Take the reference line from the tornado's OWN run, not from `central`. Both are the
    # central case on the full timeline and they now agree -- but deriving the baseline
    # from the same call that produced the bars is what makes them unable to drift apart
    # again, which is precisely how they drifted apart last time.
    baseline = tor[0][3] * 100 if tor else 0.0

    annual = {
        y: {k: (round(v, 2) if isinstance(v, float) else v)
            for k, v in central.annual(y).items()}
        for y in range(2018, 2033)
    }

    audit = config.load().audit()

    from model import uncertainty
    from model.actuals import actuals_end

    a_central = scenarios.build_assumptions("central")
    band = uncertainty.run_bands("central", full_timeline())

    return {
        "actuals_end": actuals_end(a_central).label,
        "band": {
            "supply_p10": band.supply_p10, "supply_p90": band.supply_p90,
            "demand_p10": band.demand_p10, "demand_p90": band.demand_p90,
            "gap_p10": band.gap_p10, "gap_p90": band.gap_p90,
            "p_closed": band.p_gap_closed,
        },
        "fleet": fleet_payload(central),
        "pipeline": pipeline_payload(a_central),
        "viability": viability_payload(a_central),
        "scenarios": {k: series(v) for k, v in runs.items()},
        "scenario_desc": {
            k: (config.load().tree["scenarios"][k].get("description") or "").strip()
            for k in ("tight", "central", "loose")
        },
        "demand_stack": demand_stack(central),
        "sliders": slider_data,
        "tornado": [
            {"label": l, "low": lo * 100, "high": hi * 100} for l, lo, hi, _ in tor
        ],
        "tornado_baseline": baseline,
        "constraint_label": CONSTRAINT_LABEL,
        "capex": capex_crosscheck(central),
        "annual": annual,
        "audit": audit,
        "history_end": "2025Q4",
        "headline": headline(runs, band, central),
    }


def headline(runs: dict, band, central) -> dict:
    """The numbers the lede quotes.

    Derived, never typed by hand. A summary card with hardcoded figures is a summary card
    that silently stops being true the first time an assumption moves, and it is the part
    of the page most likely to be read and least likely to be re-checked.
    """
    i29 = band.quarters.index("2029Q4")
    fl = fleet_payload(central)
    gw_now = fl["fleet_power_gw"][fl["quarters"].index("2026Q1")]
    gw_end = fl["fleet_power_gw"][-1]
    # Same accessor as the charted `dram_deficit` series -- quarterly EB, annualised.
    deficit = next(b.deficit_eb * 4 for b in central.dram if b.quarter_label == "2029Q4")
    return {
        "gap_2026q4": runs["central"].dram_gap_at("2026Q4") * 100,
        "gap_2029q4": runs["central"].dram_gap_at("2029Q4") * 100,
        "gap_tight": runs["tight"].dram_gap_at("2029Q4") * 100,
        "gap_loose": runs["loose"].dram_gap_at("2029Q4") * 100,
        "gap_p10": band.gap_p10[i29],
        "gap_p90": band.gap_p90[i29],
        "deficit_2029q4_eb": deficit,
        "fleet_gw_2032": gw_end,
        "fleet_multiple": gw_end / gw_now if gw_now else 0.0,
        "p_closed_max_outyear": max(
            band.p_gap_closed[band.quarters.index("2028Q1"):]) * 100,
        "draws": int(config.load().scalar("uncertainty.draws")),
    }


def plotly_js() -> str:
    import plotly

    p = Path(plotly.__file__).parent / "package_data" / "plotly.min.js"
    return p.read_text()


def main() -> None:
    payload = build_payload()
    tpl = (HERE / "template.html").read_text()
    html = tpl.replace("/*__PLOTLY__*/", plotly_js())
    html = html.replace("/*__DATA__*/", json.dumps(payload))
    OUT.write_text(html)
    print(f"wrote {OUT}  ({OUT.stat().st_size / 1e6:.1f} MB, self-contained)")


if __name__ == "__main__":
    main()
