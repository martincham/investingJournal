"""Build report/vintages.html: every frozen projection on one page, with a slider.

Reads vintages/*/memory_model.sqlite (read-only) and nothing else. It never re-runs the
model: each vintage is shown exactly as it was frozen.

The selected vintage is drawn solid. The newest vintage is drawn faint underneath it,
and the newest vintage's OBSERVED quarters are drawn as dots, so an old projection can be
read against what actually happened after it was made.

Run:  ./.venv/bin/python -m report.compare
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from report.build import plotly_js

ROOT = Path(__file__).resolve().parent.parent
VINTAGES = ROOT / "vintages"
OUT = ROOT / "report" / "vintages.html"

YEARS = range(2024, 2033)


def _rows(c: sqlite3.Connection, sql: str, *args) -> list[dict]:
    c.row_factory = sqlite3.Row
    return [dict(r) for r in c.execute(sql, args)]


def load_vintage(d: Path) -> dict:
    with sqlite3.connect(f"file:{d / 'memory_model.sqlite'}?mode=ro", uri=True) as c:
        meta = {r["key"]: r["value"] for r in _rows(c, "select key, value from run_meta")}
        bal = _rows(
            c,
            "select quarter, product, is_actual, supply_eb, demand_eb, gap from balance "
            "where scenario = 'central' order by year, q",
        )
        band = _rows(
            c,
            "select quarter, gap_p10, gap_p90 from uncertainty_band where scenario = 'central'",
        )
        annual = _rows(
            c,
            "select scenario, year, dram_supply_eb, dram_demand_eb, dram_gap, nand_gap "
            f"from annual_summary where year between {min(YEARS)} and {max(YEARS)}",
        )
    # uncertainty_band stores the gap in PERCENT (export.py: "percent (as emitted)"),
    # unlike balance.gap, which is a fraction.
    p10 = {r["quarter"]: r["gap_p10"] / 100 for r in band}
    p90 = {r["quarter"]: r["gap_p90"] / 100 for r in band}

    def product(p: str) -> dict:
        rs = [r for r in bal if r["product"] == p]
        return {
            "q": [r["quarter"] for r in rs],
            "actual": [bool(r["is_actual"]) for r in rs],
            "supply": [r["supply_eb"] for r in rs],
            "demand": [r["demand_eb"] for r in rs],
            "gap": [r["gap"] for r in rs],
        }

    dram = product("dram")
    # The band only exists for DRAM; NAND has no Monte Carlo run.
    dram["p10"] = [p10.get(q) for q in dram["q"]]
    dram["p90"] = [p90.get(q) for q in dram["q"]]
    return {
        "id": d.name,
        "actuals_end": meta.get("actuals_end"),
        "generated": meta.get("generated_utc", "")[:10],
        "dram": dram,
        "nand": product("nand"),
        "annual": annual,
    }


def main() -> Path:
    dirs = sorted(p for p in VINTAGES.iterdir() if (p / "memory_model.sqlite").exists())
    if not dirs:
        raise SystemExit("no vintages/*/memory_model.sqlite found; run report.freeze first")
    data = [load_vintage(d) for d in dirs]
    html = (
        TEMPLATE.replace("/*__PLOTLY__*/", plotly_js())
        .replace("/*__DATA__*/", json.dumps(data))
    )
    OUT.write_text(html)
    print(f"wrote {OUT} ({len(data)} vintages: {', '.join(v['id'] for v in data)})")
    return OUT


TEMPLATE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Memory Projection Vintages</title>
<script>/*__PLOTLY__*/</script>
<style>
:root {
  --plane: #f9f9f7; --surface-1: #fcfcfb; --text-primary: #0b0b0b; --text-secondary: #52514e;
  --muted: #898781; --grid: #e1e0d9; --axis: #c3c2b7; --border: rgba(11,11,11,0.1);
  --supply: #2a78d6; --demand: #eb6834; --gap: #4a3aa7; --actual-shade: rgba(11,11,11,0.05);
}
@media (prefers-color-scheme: dark) {
  :root {
    --plane: #0d0d0d; --surface-1: #1a1a19; --text-primary: #ffffff; --text-secondary: #c3c2b7;
    --muted: #898781; --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.1);
    --supply: #3987e5; --demand: #d95926; --gap: #9085e9; --actual-shade: rgba(255,255,255,0.06);
  }
}
* { box-sizing: border-box; }
body { margin: 0; padding: 32px 16px 80px; background: var(--plane); color: var(--text-primary);
  font: 15px/1.6 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
.wrap { max-width: 1060px; margin: 0 auto; }
h1 { font-size: 26px; line-height: 1.25; margin: 0 0 6px; }
h2 { font-size: 17px; margin: 0 0 4px; }
p.sub, p.note { color: var(--text-secondary); margin: 0 0 14px; }
.card { background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px;
  padding: 18px 18px 10px; margin: 18px 0; }
.picker { position: sticky; top: 0; z-index: 5; background: var(--surface-1);
  border: 1px solid var(--border); border-radius: 10px; padding: 14px 18px; margin: 18px 0; }
.picker input { width: 100%; }
.ticks { display: flex; justify-content: space-between; font-size: 13px; color: var(--muted); }
.ticks span.on { color: var(--text-primary); font-weight: 600; }
#meta { font-size: 13px; color: var(--text-secondary); margin-top: 6px; }
.fig { width: 100%; height: 380px; }
.tablewrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 14px; font-variant-numeric: tabular-nums; }
th, td { padding: 6px 10px; text-align: right; border-bottom: 1px solid var(--border); white-space: nowrap; }
th:first-child, td:first-child { text-align: left; }
th { color: var(--text-secondary); font-weight: 500; }
td.up { color: var(--demand); } td.down { color: var(--supply); }
</style></head>
<body><div class="wrap">
<h1>Memory projection vintages</h1>
<p class="sub">Each vintage is a frozen run of the model, shown exactly as it was produced.
Pick one with the slider. The newest vintage is drawn faintly behind it, and dots mark
quarters the newest vintage has as observed data, so you can see where an old projection
met reality. Central scenario throughout. The gap is a pressure index (demand ÷ supply − 1),
not a forecast of missing bits.</p>

<div class="picker">
  <input type="range" id="slider" min="0" step="1">
  <div class="ticks" id="ticks"></div>
  <div id="meta"></div>
</div>

<div class="card"><h2>DRAM supply and demand</h2>
<p class="note">EB per quarter. Shaded area: quarters the selected vintage had as observed data.</p>
<div class="fig" id="f-dram"></div></div>

<div class="card"><h2>DRAM gap</h2>
<p class="note">Demand ÷ supply − 1, with the P10–P90 band of the selected vintage.</p>
<div class="fig" id="f-gap"></div></div>

<div class="card"><h2>NAND gap</h2>
<p class="note">The model's NAND line is the less reliable one. Its backcast test covers DRAM only.</p>
<div class="fig" id="f-nand"></div></div>

<div class="card"><h2>Annual figures, selected vintage vs newest</h2>
<p class="note" id="tnote"></p>
<div class="tablewrap"><table id="tbl"></table></div></div>
</div>

<script>
const V = /*__DATA__*/;
const css = k => getComputedStyle(document.documentElement).getPropertyValue(k).trim();
const newest = V[V.length - 1];
const slider = document.getElementById('slider');
slider.max = V.length - 1; slider.value = V.length - 1;
slider.disabled = V.length < 2;

function layout(yfmt, ytitle, shadeEnd) {
  const shapes = shadeEnd ? [{type: 'rect', xref: 'x', yref: 'paper', x0: '2018Q1', x1: shadeEnd,
    y0: 0, y1: 1, fillcolor: css('--actual-shade'), line: {width: 0}, layer: 'below'}] : [];
  return {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: {color: css('--text-secondary'), size: 12},
    margin: {l: 56, r: 12, t: 8, b: 40}, showlegend: true,
    legend: {orientation: 'h', y: -0.15},
    xaxis: {type: 'category', gridcolor: css('--grid'), linecolor: css('--axis'), nticks: 10},
    yaxis: {gridcolor: css('--grid'), zerolinecolor: css('--axis'), tickformat: yfmt, title: ytitle},
    shapes, hovermode: 'x unified',
  };
}
const line = (x, y, name, color, extra = {}) =>
  ({x, y, name, type: 'scatter', mode: 'lines', line: {color, width: 2}, ...extra});
const faint = (x, y, name, color) =>
  line(x, y, name, color, {opacity: 0.35, line: {color, width: 1.5, dash: 'dot'}});
const observed = (p, key, name, color) => {
  const idx = p.actual.map((a, i) => a ? i : -1).filter(i => i >= 0);
  return {x: idx.map(i => p.q[i]), y: idx.map(i => p[key][i]), name, type: 'scatter',
    mode: 'markers', marker: {color, size: 5}};
};
const cfg = {displayModeBar: false, responsive: true};

function draw() {
  const v = V[+slider.value];
  const isNewest = v === newest;
  document.getElementById('ticks').innerHTML =
    V.map((x, i) => `<span class="${i == slider.value ? 'on' : ''}">${x.id}</span>`).join('');
  document.getElementById('meta').textContent =
    `Vintage ${v.id}: observed data through ${v.actuals_end}, generated ${v.generated}.`;

  const d = v.dram, nd = newest.dram;
  const tr1 = [line(d.q, d.supply, `Supply (${v.id})`, css('--supply')),
               line(d.q, d.demand, `Demand (${v.id})`, css('--demand'))];
  if (!isNewest) tr1.push(faint(nd.q, nd.supply, `Supply (${newest.id})`, css('--supply')),
                         faint(nd.q, nd.demand, `Demand (${newest.id})`, css('--demand')));
  tr1.push(observed(nd, 'supply', `Observed supply (as of ${newest.id})`, css('--text-primary')));
  Plotly.react('f-dram', tr1, layout('.0f', 'EB / quarter', v.actuals_end), cfg);

  const tr2 = [
    {x: d.q, y: d.p90, type: 'scatter', mode: 'lines', line: {width: 0}, showlegend: false, hoverinfo: 'skip'},
    {x: d.q, y: d.p10, type: 'scatter', mode: 'lines', line: {width: 0}, fill: 'tonexty',
     fillcolor: css('--gap') + '33', name: 'P10–P90'},
    line(d.q, d.gap, `Gap (${v.id})`, css('--gap'))];
  if (!isNewest) tr2.push(faint(nd.q, nd.gap, `Gap (${newest.id})`, css('--gap')));
  Plotly.react('f-gap', tr2, layout('.0%', null, v.actuals_end), cfg);

  const tr3 = [line(v.nand.q, v.nand.gap, `NAND gap (${v.id})`, css('--gap'))];
  if (!isNewest) tr3.push(faint(newest.nand.q, newest.nand.gap, `NAND gap (${newest.id})`, css('--gap')));
  Plotly.react('f-nand', tr3, layout('.0%', null, v.actuals_end), cfg);

  table(v);
}

function table(v) {
  const pick = (vv, y) => vv.annual.find(r => r.scenario === 'central' && r.year === y) || {};
  const years = [...new Set(v.annual.map(r => r.year))].sort();
  const pct = x => x == null ? '' : (x * 100).toFixed(1) + '%';
  const num = x => x == null ? '' : x.toFixed(1);
  const delta = (a, b, f) => {
    if (a == null || b == null) return '<td></td>';
    const d = b - a, cls = Math.abs(d) < 1e-9 ? '' : d > 0 ? 'up' : 'down';
    return `<td class="${cls}">${d > 0 ? '+' : ''}${f(d)}</td>`;
  };
  const same = v === newest;
  document.getElementById('tnote').textContent = same
    ? `Central scenario, vintage ${v.id}. Pick an older vintage to see what changed.`
    : `Central scenario. Change = ${newest.id} minus ${v.id}.`;
  let h = '<thead><tr><th>year</th><th>DRAM supply EB</th><th>DRAM demand EB</th><th>DRAM gap</th>';
  if (!same) h += `<th>supply change</th><th>demand change</th><th>gap change</th>`;
  h += '</tr></thead><tbody>';
  for (const y of years) {
    const a = pick(v, y), b = pick(newest, y);
    h += `<tr><td>${y}</td><td>${num(a.dram_supply_eb)}</td><td>${num(a.dram_demand_eb)}</td><td>${pct(a.dram_gap)}</td>`;
    if (!same) h += delta(a.dram_supply_eb, b.dram_supply_eb, num) +
                    delta(a.dram_demand_eb, b.dram_demand_eb, num) +
                    delta(a.dram_gap, b.dram_gap, d => (d * 100).toFixed(1) + ' pt');
    h += '</tr>';
  }
  document.getElementById('tbl').innerHTML = h + '</tbody>';
}

slider.addEventListener('input', draw);
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', draw);
draw();
</script>
</body></html>
"""


if __name__ == "__main__":
    main()
