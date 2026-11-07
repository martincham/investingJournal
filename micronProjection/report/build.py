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
from report import summary

HERE = Path(__file__).resolve().parent
OUT = HERE / "micron_model.html"
PREV_VINTAGE = HERE.parent / "vintages" / "2026-07" / "fy_summary.csv"

# Categorical slots from the reference palette. Every set of hues that shares a chart is
# validated (scripts/validate_palette.js): scenarios and the price chart both use
# blue/orange/aqua -- worst adjacent CVD dE 9.2, normal-vision 27.6 (light); aqua is
# below 3:1 on the light surface, so the table view is the required relief. Orange next
# to yellow FAILS the normal-vision floor (13.7) and is never paired. Light / dark steps.
C = {
    "blue": ("#2a78d6", "#3987e5"),
    "yellow": ("#eda100", "#c98500"),
    "aqua": ("#1baf7a", "#199e70"),
    "orange": ("#eb6834", "#d95926"),
    "red": ("#e34948", "#e66767"),
    "violet": ("#4a3aa7", "#9085e9"),
}
PIN = Quarter(2026, 3)  # replaced from asp.pin_end in build()
GREY = "rgba(120,118,111,0.85)"
SCEN = (("central", "blue"), ("tight", "orange"), ("loose", "aqua"))


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


EXTRAP_FROM = None  # set in build(): first quarter where the P&L price extrapolates a fit


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
        # Only when the P&L price itself is a fitted response applied outside its range
        # (asp.price_source: fitted). The market path never sets this.
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


def _scenario_chart(runs, attr, title, ytitle, order, scale=1.0):
    f = _fig(title, ytitle, order)
    for name, hue in SCEN:
        rr = [r for r in runs[name].rows if r.quarter.year >= 2020]
        (ax, ay), (px, py) = _split(rr, attr, scale)
        if name == "central":
            f.add_trace(go.Scatter(x=ax, y=ay, name="reported", mode="lines",
                                   line=dict(color=C["blue"][0], width=2.5)))
        f.add_trace(go.Scatter(x=px, y=py, name=f"{name} (projected)", mode="lines",
                               line=dict(color=C[hue][0], width=2, dash="dash")))
    return f


def _guide_checks(a, central) -> list[tuple[str, bool, str]]:
    """Central against what Micron said. Diagnostics, not constraints: the guide
    calibrates the first projected quarter and is checked, never imposed, after it."""
    g = central.at((PIN + 1).label)
    rng = a.value("guidance.eps_diluted")
    fy27 = central.fiscal_year(2027)
    revs = [r.revenue / 1e9 for r in fy27]
    gms = [r.gross_margin for r in fy27]
    seq = all(b > x for x, b in zip(revs, revs[1:]))
    floor = min(gms[1:]) >= gms[0] - 1e-9
    return [
        (f"FQ1'27 GAAP EPS inside the ${rng['low']:.2f}&ndash;${rng['high']:.2f} guide "
         f"(model ${g.eps:.2f}; revenue, margin, opex and tax are pinned, the rest is modelled)",
         rng["low"] <= g.eps <= rng["high"], ""),
        ("FY27 revenue grows every quarter (&ldquo;sequential revenue growth each quarter&rdquo;)",
         seq, " &rarr; ".join(f"${v:.1f}bn" for v in revs)),
        ("FQ1'27 is the FY27 gross-margin floor",
         floor, " &rarr; ".join(f"{v:.2%}" for v in gms)),
    ]


def build() -> Path:
    a = load()
    global PIN, EXTRAP_FROM
    PIN = Quarter.parse(str(a.value("asp.pin_end")))
    runs = {s: pnl.run(a, s) for s, _ in SCEN}
    central = runs["central"]
    rows = [r for r in central.rows if r.quarter.year >= 2020]
    ex = [r.quarter.label for r in central.rows if r.extrapolating]
    EXTRAP_FROM = ex[0] if ex else None
    ORDER = [r.quarter.label for r in rows]
    ORDER_FULL = [b.quarter.label for b in central.baseline.quarters]
    source = str(a.value("asp.price_source"))

    figs: list[tuple[str, go.Figure, str]] = []

    # --- 1. Revenue -------------------------------------------------------
    figs.append((
        "Revenue",
        _scenario_chart(runs, "revenue", f"Revenue — reported through {PIN.label}, projected after",
                        "$bn per quarter", ORDER, 1e-9),
        "memoryProjection's three scenarios. They differ only in the bit lines and the industry "
        "price path that follows from them; every Micron-specific assumption is identical. "
        "Loose collapses because upstream's loose supply jumps above demand right after the "
        "observed data and that model has nothing that cuts supply to end a glut: read it as "
        "&ldquo;a glut is possible&rdquo;, not as a path. It bottoms on Micron's own 2023 "
        "trough markup.",
    ))

    # --- 2. EPS -----------------------------------------------------------
    figs.append((
        "EPS",
        _scenario_chart(runs, "eps", "Diluted EPS (GAAP)", "$ per share per quarter", ORDER),
        "FY23 is negative and is reported, not modelled. Tight sits below central through much "
        "of 2029&ndash;2031: fewer bits, and upstream caps the industry price at what cloud "
        "providers' budgets can pay, so scarcity stops raising price before it stops cutting "
        "volume. Central's 2032 drop is upstream's price path falling as its gap turns negative.",
    ))

    # --- 3. Price vs cost (ONE axis -- all $/GB) ---------------------------
    f = _fig("Commodity ASP vs cash cost per bit", "$ per GB (commodity-equivalent)", ORDER)
    _pair(f, rows, "commodity_asp_per_gb", "ASP (used)", "blue")
    _pair(f, rows, "cash_cost_per_gb", "cash cost", "orange")
    prj = [r for r in rows if r.quarter > PIN]
    f.add_trace(go.Scatter(
        x=[r.quarter.label for r in prj], y=[r.fitted_asp_per_gb for r in prj],
        name="fitted response (cross-check)", mode="lines",
        line=dict(color=C["aqua"][0], width=2, dash="dot"),
    ))
    figs.append((
        "The cycle",
        f,
        "The distance between ASP and cost IS the gross margin story; all three lines are $/GB, so "
        "they share an axis honestly. ASP is Micron's own realised revenue/bit through "
        f"{PIN.label}, solved from the FQ1'27 revenue guide in {(PIN + 1).label}, then "
        + ("Micron's guided price moved by memoryProjection's industry DRAM price path "
           "(real, converted to nominal). " if source == "market" else "the fitted response. ")
        + "The dotted line is what the fitted tightness response says instead: it decays from the "
        "guided ~11&times; markup toward a fitted ~7&ndash;8&times;, which is why it was retired as "
        "the default. Cost is derived from the filings, backed out of the GAAP margin guide in "
        "FQ1'27, then a learning curve from there.",
    ))

    # --- 4. Margin (separate chart -- different unit) ----------------------
    figs.append((
        "Margin",
        _scenario_chart(runs, "gross_margin", "Gross margin (GAAP)", "%", ORDER, 100.0),
        "A separate chart from price on purpose: margin is a percentage and ASP is $/GB. "
        "Sharing an axis would be a dual-axis chart, which invents a visual relationship "
        "out of two arbitrary scales. The FY27 dip in central is D&A rising with the "
        "doubled capex plan while upstream's industry price eases 5% in 2027Q2.",
    ))

    # --- 5. July vs November ---------------------------------------------
    if PREV_VINTAGE.exists():
        from model.conf import deep_copy
        fa = deep_copy(a)
        fa.override("asp.price_source", "fitted")
        lines = (
            ("July 2026 (fitted price)", [r for r in summary.read(PREV_VINTAGE) if r["scenario"] == "central"],
             dict(color=GREY, width=2, dash="dot")),
            ("November, fitted price (cross-check)", summary.fy_rows(pnl.run(fa, "central")),
             dict(color=C["aqua"][0], width=2, dash="dot")),
            ("November 2026 (used)", summary.fy_rows(central), dict(color=C["blue"][0], width=2.5)),
        )
        f = _fig("FY revenue, central: July vs November projection", "$bn per fiscal year", seam=False)
        for name, rr, line in lines:
            rr = [r for r in rr if r["fy"] >= 2026]
            f.add_trace(go.Scatter(x=[f"FY{int(r['fy'])}" for r in rr], y=[r["revenue_usd_bn"] for r in rr],
                                   name=name, mode="lines+markers", line=line, marker=dict(size=8)))
        fit30 = next(r["revenue_usd_bn"] for r in lines[1][1] if r["fy"] == 2030)
        jul30 = next(r["revenue_usd_bn"] for r in lines[0][1] if r["fy"] == 2030)
        now30 = next(r["revenue_usd_bn"] for r in lines[2][1] if r["fy"] == 2030)
        figs.append((
            "What moved since July",
            f,
            "July: memory vintage 2026-07, data through FY26Q3, fitted price response. November: "
            "memory vintage 2026-11, data through FY26Q4, upstream's price path. The middle line "
            "separates the two changes. New bits with the OLD price engine would have LOWERED the "
            f"projection (FY30 ${fit30:,.0f}bn against July's ${jul30:,.0f}bn): November's "
            "tightness plateaus near +0.35 instead of climbing to +0.50, and the fitted markup "
            "decays from the guided ~11&times; toward ~7&ndash;8&times;. The rise to "
            f"${now30:,.0f}bn is the price engine: upstream's industry price keeps rising into 2029 "
            "while Micron's cost keeps falling, so the markup holds at 11&ndash;14&times;. "
            "That is the single largest judgement in this revision.",
        ))

    # --- 6. The signal ----------------------------------------------------
    f = _fig(
        "Contested-pool served fraction — why the inventory swing is in the price signal",
        "served fraction (1.0 = balanced)",
        ORDER_FULL,
    )
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
        "Feeds the fitted response (now the cross-check). The red line — the obvious "
        "construction, excluding the inventory swing — says 2023 was TIGHTER than the 2021 "
        "boom. 2023 is the deepest glut in memory history: Micron ran a −32.7% gross margin. "
        "The destock IS the glut, and it lives entirely in the inventory segment.",
    ))

    # --- 7. Revenue mix ---------------------------------------------------
    f = _fig("Projected revenue by product", "$bn per quarter",
             [r.quarter.label for r in central.rows if r.quarter > PIN], seam=False)
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
        "Projected only. Micron reports DRAM and NAND revenue (73% / 26% in FQ4'26, which the "
        "model's price ratios reproduce) but not commodity DRAM vs HBM.",
    ))

    # --- table ------------------------------------------------------------
    prev_c = {}
    if PREV_VINTAGE.exists():
        prev_c = {int(r["fy"]): r for r in summary.read(PREV_VINTAGE) if r["scenario"] == "central"}
    fy_rows = []
    for r in summary.fy_rows(central, 2020, 2033):
        rr = central.fiscal_year(r["fy"])
        p = prev_c.get(r["fy"])
        fy_rows.append(dict(
            fy=f"FY{r['fy']}", kind=r["kind"], rev=r["revenue_usd_bn"], gm=r["gross_margin"] * 100,
            ni=r["net_income_usd_bn"], eps=r["eps"], fcf=r["fcf_usd_bn"], capex=r["capex_usd_bn"],
            asp=sum(x.commodity_asp_per_gb for x in rr) / 4,
            cost=sum(x.cash_cost_per_gb for x in rr) / 4,
            jrev=f"{p['revenue_usd_bn']:,.1f}" if p and r["fy"] >= 2026 else "",
            jeps=f"{p['eps']:,.2f}" if p and r["fy"] >= 2026 else "",
        ))

    thead = "".join(f"<th>{h}</th>" for h in (
        "fiscal year", "", "revenue $bn", "gross margin %", "net income $bn",
        "EPS $", "FCF $bn", "capex $bn", "ASP $/GB", "cash cost $/GB", "July rev $bn", "July EPS $"))
    tbody = "".join(
        "<tr class='{cls}'><td class='fy'>{fy}</td><td class='kind'>{kind}</td>"
        "<td>{rev:,.1f}</td><td>{gm:,.1f}</td><td>{ni:,.1f}</td><td>{eps:,.2f}</td>"
        "<td>{fcf:,.1f}</td><td>{capex:,.1f}</td><td>{asp:,.2f}</td><td>{cost:,.2f}</td>"
        "<td class='prev'>{jrev}</td><td class='prev'>{jeps}</td></tr>".format(
            cls="act" if r["kind"] == "reported" else "prj", **r)
        for r in fy_rows
    )

    scen_rows = ""
    for name, _ in SCEN:
        fy = {x["fy"]: x for x in summary.fy_rows(runs[name])}
        scen_rows += (
            f"<tr><td class='fy'>{name}</td><td>{fy[2027]['revenue_usd_bn']:,.1f}</td>"
            f"<td>{fy[2027]['gross_margin'] * 100:,.1f}</td><td>{fy[2027]['eps']:,.2f}</td>"
            f"<td>{fy[2028]['revenue_usd_bn']:,.1f}</td><td>{fy[2028]['eps']:,.2f}</td></tr>"
        )

    checks = ""
    for text, ok, detail in _guide_checks(a, central):
        cls, mark = ("ok", "&#10003; consistent") if ok else ("miss", "&#10007; not consistent")
        extra = f"<br><span class='detail'>{detail}</span>" if detail else ""
        checks += f"<li class='{cls}'><span class='mark'>{mark}</span> {text}{extra}</li>"

    body = "".join(
        f"<section><h2>{name}</h2><p class='note'>{note}</p>"
        f"<div class='fig'>{fig.to_html(full_html=False, include_plotlyjs=False, config={'displayModeBar': False})}</div></section>"
        for name, fig, note in figs
    )

    fy27 = summary.fy_rows(central)
    f27 = next(x for x in fy27 if x["fy"] == 2027)
    upstream_ref = f"{a.value('upstream.sqlite_path')} (sha256 {sha256(sqlite_path(a))[:12]})"
    html = TEMPLATE.format(
        plotlyjs=get_plotlyjs(), body=body, thead=thead, tbody=tbody, upstream=upstream_ref,
        scen_rows=scen_rows, checks=checks,
        r2=a.scalar("asp.response_r2"), n_fit=35,
        fy27_rev=f27["revenue_usd_bn"], fy27_eps=f27["eps"],
    )
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
  table {{ border-collapse: collapse; width: 100%; font-size: 12.5px;
           font-variant-numeric: tabular-nums; }}
  th, td {{ padding: .5rem .5rem; text-align: right; border-bottom: 1px solid var(--rule);
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
  td.prev {{ color: var(--text-muted); }}
  ul.checks {{ list-style: none; padding: 0; margin: .5rem 0 0; font-size: 13.5px; }}
  ul.checks li {{ padding: .55rem .8rem; border: 1px solid var(--rule); border-radius: 8px;
                  margin: .4rem 0; background: var(--surface-2); color: var(--text-secondary); }}
  ul.checks .mark {{ font-weight: 600; color: var(--text-primary); margin-right: .35rem; }}
  ul.checks li.miss {{ border-left: 3px solid #eb6834; }}
  ul.checks li.ok {{ border-left: 3px solid #1baf7a; }}
  ul.checks .detail {{ color: var(--text-muted); font-size: 12.5px; font-variant-numeric: tabular-nums; }}
  .small {{ max-width: 820px; }}
</style></head><body>

<h1>Micron — revenue &amp; earnings, 2020–2032</h1>
<p class="sub">November 2026 projection. Reported through <strong>fiscal Q4 2026</strong>
(quarter ended 3 Sep 2026, $54.2bn, a 14-week quarter) &middot; company-guided for
<strong>FQ1&rsquo;27</strong> ($61.5bn &plusmn; $1.5bn) &middot; projected thereafter.
Central FY27: <strong>${fy27_rev:,.0f}bn revenue, ${fy27_eps:,.2f} GAAP EPS</strong>.<br>
<span class="muted">Charts are indexed by calendar quarter to line up with the bit model;
Micron&rsquo;s fiscal year runs one quarter ahead, so FQ4&rsquo;26 = calendar 2026Q3.</span></p>

<div class="callout">
<strong>What this is.</strong> A financial layer on top of <code>memoryProjection</code>,
which models global DRAM/NAND <em>bits</em> and, since November, the industry DRAM
<em>price</em>. Its supply, demand and price path are taken <strong>as given</strong> &mdash;
never recomputed, overlaid or perturbed. The scenarios are its <em>tight</em>, <em>central</em>
and <em>loose</em>. Every number here means: <strong>what Micron earns if those lines are
right.</strong><br><br>

<strong>Three states.</strong> Quarters are <em>reported</em> (through FQ4&rsquo;26, Micron&rsquo;s
GAAP filings verbatim), <em>guided</em> (FQ1&rsquo;27: revenue at the guide midpoint, GAAP gross
margin 85.95%, opex $2.31bn and tax 15.5% pinned; D&amp;A, other income and share count
modelled), and <em>projected</em>. Micron beat its revenue guide by 24% in FQ3&rsquo;26 and
8.5% in FQ4&rsquo;26; that record is upside to central, not built into it.<br><br>

<strong>Price after FQ1&rsquo;27 follows upstream&rsquo;s industry path.</strong> Micron&rsquo;s
guided price is moved by memoryProjection&rsquo;s industry DRAM price (real 2025 $/GB, indexed
to 2026Q4 and converted to nominal at 2.5%/yr), with a floor at Micron&rsquo;s lowest observed
markup over cash cost (1.17&times;, 2023Q1). Until November the model set price itself from a
response fitted to Micron&rsquo;s record (refit now: n = {n_fit}, R&sup2; = {r2:.2f}). On the
November bit lines that response has central revenue falling every quarter after the guide,
against both Micron&rsquo;s outlook and upstream&rsquo;s price layer, so it is now shown as a
dotted cross-check rather than used.<br><br>

<strong class="warn">Read this before the numbers.</strong> Upstream&rsquo;s price path is a
<em>path</em>, not a clearing price: its own docs say the level cannot be identified from
quantities that carry 5&ndash;15% error. Loose is a glut that nothing in either model ends.
And the out-years inherit upstream&rsquo;s view that AI demand stays inelastic and cloud budgets
cap price &mdash; this model does not independently confirm either.
</div>

<section>
<h2>Against Micron&rsquo;s guide (central)</h2>
<p class="note">Guidance calibrates the first projected quarter and is <em>checked</em>, never
imposed, after it. Where central disagrees with what Micron said, the disagreement comes from
upstream&rsquo;s price path or the cost and D&amp;A assumptions, and is shown rather than tuned away.</p>
<ul class="checks">{checks}</ul>
</section>

<section>
<h2>Scenarios</h2>
<p class="note">Fiscal years. FY27 includes the guided FQ1, whose revenue spans the guide
range across scenarios ($60.0bn loose, $63.0bn tight).</p>
<div class="tablewrap small"><table><thead><tr><th>scenario</th><th>FY27 revenue $bn</th>
<th>FY27 gross margin %</th><th>FY27 EPS $</th><th>FY28 revenue $bn</th><th>FY28 EPS $</th></tr></thead>
<tbody>{scen_rows}</tbody></table></div>
</section>

{body}

<section>
<h2>Fiscal year summary (central)</h2>
<p class="note">Micron's fiscal year ends in late August or early September, so FY2027 spans
calendar 2026Q4&ndash;2027Q3: FQ1 guided, the rest projected. The last two columns are the
July 2026 projection (<code>vintages/2026-07/fy_summary.csv</code>). The table view is also
the accessibility relief for the chart palette.</p>
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
