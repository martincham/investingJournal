"""Build report/micron_model.html -- the readable view of the model.

Self-contained: plotly is inlined, so the file opens from disk with no network.

Design rules this follows (see the dataviz skill):
  - NO dual-axis charts. Price and margin are different units, so they are different
    charts. An earlier plan had them sharing a figure with two y-scales, which is the
    single most common way to make two series look causally related when the
    relationship is an artifact of two arbitrary scales.
  - Actual vs projected is encoded by LINE STYLE (solid vs dashed), never by hue. Hue
    carries identity -- which series -- and nothing else.
  - Categorical hues in fixed slot order, validated. Table view ships because three
    palette slots sit below 3:1 on the light surface (the relief rule).
  - Light and dark are both selected, not an automatic flip.

Run:  ./.venv/bin/python -m report.build
"""

from __future__ import annotations

import json
from pathlib import Path

import plotly.graph_objects as go
from plotly.offline import get_plotlyjs

from model import pnl
from model.conf import load
from model.upstream import sha256, sqlite_path
from model.vendor.calendar import Quarter

HERE = Path(__file__).resolve().parent
OUT = HERE / "micron_model.html"

# Categorical slots 1,4,5,6 from the reference palette, validated as a 4-slot set:
# worst adjacent CVD dE 9.1, normal-vision 22.9. Light / dark steps.
C = {
    "blue": ("#2a78d6", "#3987e5"),
    "yellow": ("#eda100", "#c98500"),
    "aqua": ("#1baf7a", "#199e70"),
    "orange": ("#eb6834", "#d95926"),
    "red": ("#e34948", "#e66767"),
    "violet": ("#4a3aa7", "#9085e9"),
}
PIN = Quarter(2026, 2)


def _split(rows, attr, scale=1.0):
    """Split a series at the actuals boundary so solid/dashed can be drawn separately.

    The projected leg repeats the pin quarter so the two lines join rather than showing
    a one-quarter gap at the seam.
    """
    act_x, act_y, prj_x, prj_y = [], [], [], []
    for r in rows:
        v = getattr(r, attr)
        v = v * scale if v is not None else None
        if r.quarter <= PIN:
            act_x.append(r.quarter.label)
            act_y.append(v)
        else:
            prj_x.append(r.quarter.label)
            prj_y.append(v)
    if act_x and prj_x:
        prj_x.insert(0, act_x[-1])
        prj_y.insert(0, act_y[-1])
    return (act_x, act_y), (prj_x, prj_y)


EXTRAP_FROM = None  # set in build(): first quarter where the price fit extrapolates


def _fig(title, ytitle, order=None, seam=True):
    """`order` pins the x category order.

    Plotly infers category order from TRACE order, so adding the projected scenarios
    before the reported line put 2027..2032 to the left of 2020..2025 -- the axis read
    backwards. Categorical x needs its order stated, not inferred.
    """
    f = go.Figure()
    f.update_layout(
        title=dict(text=title, font=dict(size=15)),
        yaxis_title=ytitle,
        template="plotly_white",
        height=380,
        margin=dict(l=60, r=20, t=50, b=40),
        hovermode="x unified",
        legend=dict(orientation="h", y=-0.18, x=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    f.update_xaxes(showgrid=False, tickangle=-45, nticks=16)
    if order:
        f.update_xaxes(categoryorder="array", categoryarray=order)
    f.update_yaxes(gridcolor="rgba(128,128,128,0.18)", zeroline=True, zerolinecolor="rgba(128,128,128,0.45)")
    # The seam. Everything left of it is reported; everything right is modelled.
    # Charts that show only projected data have no seam and must not draw one.
    if seam:
        f.add_vline(x=PIN.label, line=dict(color="rgba(128,128,128,0.5)", width=1, dash="dot"))
        f.add_annotation(
            x=PIN.label, y=1.02, yref="paper", text="reported | projected",
            showarrow=False, font=dict(size=10, color="rgba(128,128,128,0.9)"), xanchor="right",
        )
        # Beyond here the price response is applied outside the tightness range it was
        # fitted on. Marked on every chart, because it is the model's largest caveat and
        # a reader should not have to go looking for it.
        if order and EXTRAP_FROM and EXTRAP_FROM in order:
            f.add_vrect(
                x0=EXTRAP_FROM, x1=order[-1], line_width=0,
                fillcolor="rgba(235,104,52,0.07)", layer="below",
            )
            f.add_annotation(
                x=EXTRAP_FROM, y=1.02, yref="paper",
                text="price response extrapolating &#8594;", showarrow=False,
                font=dict(size=10, color="#eb6834"), xanchor="left",
            )
    return f


def _pair(f, rows, attr, name, hue, scale=1.0, hover=""):
    (ax, ay), (px, py) = _split(rows, attr, scale)
    col = C[hue][0]
    f.add_trace(go.Scatter(
        x=ax, y=ay, name=name, mode="lines", legendgroup=name,
        line=dict(color=col, width=2), hovertemplate=hover or None,
    ))
    f.add_trace(go.Scatter(
        x=px, y=py, name=name, mode="lines", legendgroup=name, showlegend=False,
        line=dict(color=col, width=2, dash="dash"), hovertemplate=hover or None,
    ))


def build() -> Path:
    a = load()
    # TIGHT is deliberately absent. Its contested pool falls to ~20% served -- a
    # tightness ~7x the range the price response was fitted on -- where the fitted
    # exponential implies a 132x markup. That is not a projection; it is an exponential
    # evaluated far from its data. The model reports out-of-domain rather than printing
    # a number it cannot support. See asp.domain_limit_multiple.
    runs = {s: pnl.run(a, s) for s in ("central", "loose")}
    central = runs["central"]
    rows = [r for r in central.rows if r.quarter.year >= 2020]
    global EXTRAP_FROM
    ex = [r.quarter.label for r in central.rows if r.extrapolating]
    EXTRAP_FROM = ex[0] if ex else None
    ORDER = [r.quarter.label for r in rows]
    ORDER_FULL = [b.quarter.label for b in central.baseline.quarters]

    figs: list[tuple[str, go.Figure, str]] = []

    # --- 1. Revenue -------------------------------------------------------
    f = _fig("Revenue — reported through 2026Q2, projected after", "$bn per quarter", ORDER)
    for name, hue in (("central", "blue"), ("loose", "aqua")):
        rr = [r for r in runs[name].rows if r.quarter.year >= 2020]
        (ax, ay), (px, py) = _split(rr, "revenue", 1e-9)
        if name == "central":
            f.add_trace(go.Scatter(x=ax, y=ay, name="reported", mode="lines",
                                   line=dict(color=C["blue"][0], width=2.5)))
        f.add_trace(go.Scatter(x=px, y=py, name=f"{name} (projected)", mode="lines",
                               line=dict(color=C[hue][0], width=2, dash="dash")))
    figs.append((
        "Revenue",
        f,
        "Two of memoryProjection's three scenarios. They differ only in the bit lines; every "
        "financial assumption is identical. TIGHT is omitted: its contested pool falls to ~20% "
        "served, roughly 7\u00d7 beyond the range the price response was fitted on, where the "
        "fitted exponential implies a 132\u00d7 markup \u2014 an exponential evaluated far from "
        "its data, not a projection. The model declines to print it.",
    ))

    # --- 2. EPS -----------------------------------------------------------
    f = _fig("Diluted EPS", "$ per share per quarter", ORDER)
    for name, hue in (("central", "blue"), ("loose", "aqua")):
        rr = [r for r in runs[name].rows if r.quarter.year >= 2020]
        (ax, ay), (px, py) = _split(rr, "eps")
        if name == "central":
            f.add_trace(go.Scatter(x=ax, y=ay, name="reported", mode="lines",
                                   line=dict(color=C["blue"][0], width=2.5)))
        f.add_trace(go.Scatter(x=px, y=py, name=f"{name} (projected)", mode="lines",
                               line=dict(color=C[hue][0], width=2, dash="dash")))
    figs.append((
        "EPS",
        f,
        "FY23 is negative and is reported, not modelled. It is one of the four cycles the "
        "price response is fitted on \u2014 and the spread between central and loose out to 2032 "
        "is what bit-line uncertainty does once an exponential price response is applied to it.",
    ))

    # --- 3. Price vs cost (ONE axis -- both are $/GB) ----------------------
    f = _fig("Realised ASP vs cash cost per bit", "$ per GB (commodity-equivalent)", ORDER)
    _pair(f, rows, "commodity_asp_per_gb", "ASP", "blue")
    _pair(f, rows, "cash_cost_per_gb", "cash cost", "orange")
    figs.append((
        "The cycle",
        f,
        "The distance between these two lines IS the gross margin story. Both are $/GB, so "
        "they share an axis honestly. ASP is Micron's own realised revenue/bit through "
        "2026Q2, then endogenous; cost is (COGS + inventory build) / production bits through "
        "2026Q2, then a learning curve anchored on that last observed value.",
    ))

    # --- 4. Margin (separate chart -- different unit) ----------------------
    f = _fig("Gross margin", "%", ORDER)
    _pair(f, rows, "gross_margin", "gross margin", "violet", 100.0)
    figs.append((
        "Margin",
        f,
        "A separate chart from price on purpose: margin is a percentage and ASP is $/GB. "
        "Sharing an axis would be a dual-axis chart, which invents a visual relationship "
        "out of two arbitrary scales.",
    ))

    # --- 5. The signal ----------------------------------------------------
    f = _fig(
        "Contested-pool served fraction — why the inventory swing is in the price signal",
        "served fraction (1.0 = balanced)",
        ORDER_FULL,
    )
    sig_rows = [r for r in central.rows if r.quarter.year >= 2018]
    base = {b.quarter: b for b in central.baseline.quarters}
    from model import tightness as tmod
    sigs = tmod.series(a, central.baseline)
    xs = [s.quarter.label for s in sigs]
    f.add_trace(go.Scatter(
        x=xs, y=[s.served_fraction for s in sigs], name="including inventory (used)",
        mode="lines", line=dict(color=C["blue"][0], width=2.5),
    ))
    f.add_trace(go.Scatter(
        x=xs, y=[s.served_fraction_ex_inventory for s in sigs], name="excluding inventory (wrong)",
        mode="lines", line=dict(color=C["red"][0], width=2, dash="dot"),
    ))
    f.add_hline(y=1.0, line=dict(color="rgba(128,128,128,0.5)", width=1))
    for lbl, yr in (("2019 glut", "2019Q3"), ("2023 glut<br>MU GM −32.7%", "2023Q1")):
        f.add_annotation(x=yr, y=1.16, text=lbl, showarrow=True, arrowhead=0,
                         font=dict(size=10), ax=0, ay=-24)
    figs.append((
        "The signal",
        f,
        "The whole design rests on this. The red line — the obvious construction, excluding "
        "the inventory swing — says 2023 was TIGHTER than the 2021 boom. 2023 is the deepest "
        "glut in memory history: Micron ran a −32.7% gross margin. The destock IS the glut, "
        "and it lives entirely in the inventory segment. Feed the red line to a price response "
        "and it projects a price spike into that trough.",
    ))

    # --- 6. Revenue mix ---------------------------------------------------
    f = _fig("Projected revenue by product", "$bn per quarter",
             [r.quarter.label for r in central.rows if r.quarter > PIN], seam=False)
    prj = [r for r in rows if r.quarter > PIN]
    xs = [r.quarter.label for r in prj]
    for attr, name, hue in (
        ("dram_revenue", "commodity DRAM", "blue"),
        ("hbm_revenue", "HBM", "yellow"),
        ("nand_revenue", "NAND", "aqua"),
    ):
        f.add_trace(go.Scatter(
            x=xs, y=[getattr(r, attr) / 1e9 for r in prj], name=name, mode="lines",
            stackgroup="one", line=dict(width=0.5, color=C[hue][0]),
        ))
    figs.append((
        "Mix",
        f,
        "Projected only — Micron does not report this split, so showing it over the actuals "
        "window would be modelled numbers dressed as reported ones.",
    ))

    # --- table ------------------------------------------------------------
    fy_rows = []
    for fy in range(2020, 2034):
        rr = central.fiscal_year(fy)
        if len(rr) < 4:
            continue
        rev = sum(x.revenue for x in rr)
        gp = sum(x.gross_profit for x in rr)
        ni = sum(x.net_income for x in rr)
        eps = sum(x.eps for x in rr)
        fcf = sum(x.fcf for x in rr)
        capex = sum(x.capex for x in rr)
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
        fy_rows.append(dict(
            fy=f"FY{fy}", kind=kind, rev=rev / 1e9, gm=gp / rev * 100,
            ni=ni / 1e9, eps=eps, fcf=fcf / 1e9, capex=capex / 1e9,
            asp=sum(x.commodity_asp_per_gb for x in rr) / 4,
            cost=sum(x.cash_cost_per_gb for x in rr) / 4,
        ))

    thead = "".join(f"<th>{h}</th>" for h in (
        "fiscal year", "", "revenue $bn", "gross margin %", "net income $bn",
        "EPS $", "FCF $bn", "capex $bn", "ASP $/GB", "cash cost $/GB"))
    tbody = "".join(
        "<tr class='{cls}'><td class='fy'>{fy}</td><td class='kind'>{kind}</td>"
        "<td>{rev:,.1f}</td><td>{gm:,.1f}</td><td>{ni:,.1f}</td><td>{eps:,.2f}</td>"
        "<td>{fcf:,.1f}</td><td>{capex:,.1f}</td><td>{asp:,.2f}</td><td>{cost:,.2f}</td></tr>".format(
            cls="act" if r["kind"] == "reported" else "prj", **r)
        for r in fy_rows
    )

    body = "".join(
        f"<section><h2>{name}</h2><p class='note'>{note}</p>"
        f"<div class='fig'>{fig.to_html(full_html=False, include_plotlyjs=False, config={'displayModeBar': False})}</div></section>"
        for name, fig, note in figs
    )

    upstream = f"{a.value('upstream.sqlite_path')} (sha256 {sha256(sqlite_path(a))[:12]})"
    html = TEMPLATE.format(plotlyjs=get_plotlyjs(), body=body, thead=thead, tbody=tbody, upstream=upstream)
    OUT.write_text(html)
    return OUT


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Micron revenue & earnings, 2020–2032</title>
<script>{plotlyjs}</script>
<style>
  :root {{
    color-scheme: light dark;
    --surface-1: #fcfcfb; --surface-2: #f4f3f0;
    --text-primary: #0b0b0b; --text-secondary: #52514e; --text-muted: #78766f;
    --rule: #e2e1dc;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --surface-1: #1a1a19; --surface-2: #232322;
      --text-primary: #ffffff; --text-secondary: #c3c2b7; --text-muted: #97958c;
      --rule: #383835;
    }}
  }}
  body {{
    margin: 0; padding: 2rem 1.25rem 5rem; background: var(--surface-1);
    color: var(--text-primary); max-width: 1080px; margin-inline: auto;
    font: 15px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  }}
  h1 {{ font-size: 1.6rem; margin: 0 0 .3rem; letter-spacing: -0.01em; }}
  h2 {{ font-size: 1.05rem; margin: 0 0 .35rem; letter-spacing: -0.01em; }}
  .sub {{ color: var(--text-secondary); margin: 0 0 1.5rem; }}
  section {{ margin: 2.5rem 0; }}
  .note {{ color: var(--text-secondary); font-size: 13.5px; margin: 0 0 .75rem; max-width: 78ch; }}
  .fig {{ background: var(--surface-2); border: 1px solid var(--rule); border-radius: 10px;
          padding: .5rem; overflow-x: auto; }}
  .callout {{ background: var(--surface-2); border: 1px solid var(--rule);
              border-left: 3px solid #eb6834; border-radius: 8px; padding: 1rem 1.15rem;
              margin: 1.5rem 0; font-size: 13.5px; color: var(--text-secondary); }}
  .callout strong {{ color: var(--text-primary); }}
  .callout strong.warn {{ color: #c2410c; }}
  .sub .muted {{ color: var(--text-muted); font-size: 13px; }}
  @media (prefers-color-scheme: dark) {{ .callout strong.warn {{ color: #fb923c; }} }}
  .tablewrap {{ overflow-x: auto; border: 1px solid var(--rule); border-radius: 10px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px;
           font-variant-numeric: tabular-nums; }}
  th, td {{ padding: .5rem .7rem; text-align: right; border-bottom: 1px solid var(--rule);
            white-space: nowrap; }}
  th {{ color: var(--text-muted); font-weight: 600; text-align: right;
        position: sticky; top: 0; background: var(--surface-2); }}
  td.fy, th:first-child {{ text-align: left; font-weight: 600; }}
  td.kind {{ text-align: left; color: var(--text-muted); font-size: 11.5px; }}
  tr.prj td {{ color: var(--text-secondary); }}
  tr.act td.fy {{ color: var(--text-primary); }}
  footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--rule);
            color: var(--text-muted); font-size: 12.5px; }}
  code {{ background: var(--surface-2); padding: .1em .35em; border-radius: 4px; font-size: .9em; }}
</style></head><body>

<h1>Micron — revenue &amp; earnings, 2020–2032</h1>
<p class="sub">Reported through <strong>fiscal Q3 2026</strong> (quarter ended 28 May 2026,
$41.5bn) &middot; company-guided for <strong>FQ4&rsquo;26</strong> and <strong>FQ1&rsquo;27</strong>
&middot; modelled thereafter, to FY2033 Q1.<br>
<span class="muted">Charts are indexed by calendar quarter to line up with the bit model;
Micron&rsquo;s fiscal year runs one quarter ahead, so FQ3&rsquo;26 = calendar 2026Q2.</span></p>

<div class="callout">
<strong>What this is.</strong> A financial layer on top of <code>memoryProjection</code>,
which models global DRAM/NAND <em>bits</em>. That model's supply and demand are taken
<strong>as given</strong> — never recomputed, overlaid or perturbed. The scenarios shown
are its own <em>central</em> and <em>loose</em>; they differ only in the bit lines. Every
number here means: <strong>what Micron earns if those bit lines are right.</strong><br><br>

<strong>Three states, not two.</strong> Quarters are <em>reported</em> (through FQ3&rsquo;26,
Micron&rsquo;s filings verbatim), <em>guided</em> (FQ4&rsquo;26 and FQ1&rsquo;27 &mdash; the
company guided ~$50bn for FQ4; central uses $51bn because Micron has beaten its own guide
every quarter of this up-cycle, with 49&ndash;55 as the beat/miss range; then +17%/quarter
contract price rises per consensus), and <em>fitted</em> (FQ2&rsquo;27 onward). Guidance is
not reported data and is never counted as such.<br><br>

<strong>The price response is fitted, not chosen.</strong> Micron's realised markup over
cash cost is regressed on the tightness it actually faced across all 34 reported quarters
(2018Q1–2026Q2): <code>log(markup) = 0.85 + 0.08·T + 2.58·T̄₄</code>, R² = 0.53, with the
residual decaying at a fitted AR(1) ρ = 0.92. Two things fell out of it — price tracks
<em>sustained</em> tightness (the 4-quarter average carries the whole signal, the current
quarter ~none), and the fitted markup at zero tightness (2.33×) independently reproduces
the 2.39× measured from balanced quarters by a different method.<br><br>

<strong class="warn">Read this before the numbers: the projection extrapolates.</strong>
The fit spans tightness |T| ≤ 0.24. Upstream's central out-years reach +0.50 — about 2×
beyond any quarter on record — where the fitted response implies a markup around 11×
cash cost. The highest Micron has <em>ever</em> achieved is 8.58×, in 2026Q2, in the
tightest market in the industry's history. The shaded region on every chart marks where
this applies. Upstream's <em>tight</em> scenario is omitted entirely: it runs ~7× beyond
the fitted range, and the model reports out-of-domain rather than printing a number it
cannot support. These projections are the logical consequence of two inputs — upstream's
bit lines, and a response fitted to Micron's record. They are not evidence that either
holds that far.<br><br>

<strong>Also: R² = 0.53.</strong> Roughly half the quarter-to-quarter variation in
Micron's markup is <em>not</em> explained by tightness — utilisation, contract timing,
mix and execution live in the other half. And the out-years contain no down-cycle
because upstream's bit lines contain none. This model inherits that; it does not
independently confirm it.
</div>

{body}

<section>
<h2>Fiscal year summary</h2>
<p class="note">Micron's fiscal year ends in late August, so FY2026 spans calendar
2025Q4–2026Q3: three quarters reported (FQ1–FQ3) and one guided (FQ4, the ~$50bn guide,
carried at $51bn). FY2027 is part-guided — FQ1'27 carries the +17% consensus, the rest is
fitted. The table view is also the accessibility relief for the chart palette.</p>
<div class="tablewrap"><table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table></div>
</section>

<footer>
Built from SEC EDGAR XBRL (companyfacts, CIK 0000723125) and
{upstream}. Regenerate:
<code>./.venv/bin/python -m report.build</code>
</footer>
</body></html>
"""


if __name__ == "__main__":
    print(f"wrote {build()}")
