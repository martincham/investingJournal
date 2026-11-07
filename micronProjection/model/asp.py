"""ASP: pinned to reality, then guided, then upstream's market path (or the fitted response).

    q <= pin_end:       ASP = Micron's own realised revenue / shipped bits. REPORTED.
    q <= guidance_end:  ASP = solved from Micron's revenue guide. GUIDED.
    q >  guidance_end:  price_source = market (default since Nov 2026):
                          ASP(q) = ASP(anchor) x P_mkt(q) / P_mkt(anchor) x (1+infl)^years
                        price_source = fitted (the July engine):
                          markup(q) = exp(a + b*T(q) + d*T_ma4(q) + residual(q))
                          residual(q) = rho * residual(q-1);  ASP = markup x cash_cost
                        Either way ASP >= price_floor_markup x cash cost (Micron's own
                        observed trough).

`anchor` is the last pinned or guided quarter. P_mkt is memoryProjection's industry DRAM
price (table `market`, real 2025 $/GB) -- a PATH taken as given. Micron's LEVEL is its own:
the index only says how much the industry price moves from the anchor, and Micron's
guided price is what moves with it.

WHY THE MARKET PATH IS THE DEFAULT (Nov 2026). On the November vintage the fitted engine
has Micron's price falling ~25% through FY27: the FQ1'27 guide puts the markup at ~11x
cash cost against a fitted ~7.5x, and the residual decays at rho. Revenue would fall
every quarter after the guide, against Micron's "sequential revenue growth each quarter"
and against upstream's own price layer, which has the industry price up 15% in 2026Q4 and
flat-to-rising after. Upstream owns the market; this model owns Micron. So the fitted
path is still computed for every quarter (`fitted_commodity_per_gb`) and shown as a
cross-check, but it no longer sets the P&L unless price_source says so.

THE FITTED RESPONSE, for the record. a, b, d and rho come out of model/calibrate.py, which
regresses Micron's realised markup on the tightness it actually faced across all 35
reported quarters (2018Q1..2026Q3, R2 0.64). Price tracks SUSTAINED tightness (d, the
4-quarter average, carries most of it) and, since the November refit, the current
quarter too (b 0.08 -> 0.43). exp(a) = 2.37x at zero tightness independently reproduces
the 2.39x measured in balanced quarters. The fit spans |T| <= 0.37; central's out-years
sit inside that, tight's do not (`extrapolating` / `fitted_extrapolating`).

WHAT THE FITTED ENGINE REPLACED in July, and why it matters: a convex push toward
tightness minus a "cost anchor" pulling ASP back toward mu * cash_cost, with four
hand-set parameters. The anchor PRESUPPOSED ITS ANSWER, and the data rejected it (kappa
fits negative over 2020-2026, +0.004 over the full window). There is no mean reversion
to mu*cost in Micron's record.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from model.calibrate import MA_WINDOW
from model.conf import Assumptions
from model.tightness import Signal
from model.vendor import units
from model.vendor.calendar import Quarter, interpolate_annual


@dataclass(frozen=True)
class AspQuarter:
    """Prices for one quarter. All $/GB."""

    quarter: Quarter
    commodity_per_gb: float
    hbm_per_gb: float
    nand_per_gb: float
    is_pinned: bool
    is_guided: bool
    markup_over_cash_cost: float
    tightness: float
    tightness_ma4: float
    extrapolating: bool          # the P&L price is the fitted response, outside its range
    fitted_commodity_per_gb: float = 0.0   # cross-check: the fitted response's price
    fitted_extrapolating: bool = False     # ...and whether IT is outside its range
    market_index: float = 0.0    # nominal P_mkt(q)/P_mkt(anchor); 0 when not used
    is_floored: bool = False     # price_floor_markup bound this quarter


def fitted_log_markup(a: Assumptions, t: float, t_ma4: float) -> float:
    return (
        a.scalar("asp.response_a")
        + a.scalar("asp.response_b") * t
        + a.scalar("asp.response_d") * t_ma4
    )


def series(
    a: Assumptions,
    signals: list[Signal],
    costs: dict[Quarter, float],          # CASH cost per bit, commodity-equivalent
    pinned: dict[Quarter, float],         # realised commodity ASP per bit, from the filings
    guided: dict[Quarter, float] | None = None,   # ASP per bit implied by guidance
    market: dict[Quarter, float] | None = None,   # upstream industry price, real $/GB
) -> list[AspQuarter]:
    """The full ASP path: reported, guided, then market-indexed (or fitted).

    The fitted residual carries across the seam and decays at rho, so the fitted
    cross-check starts from Micron's ACTUAL markup and converges to the fitted level
    rather than stepping to it. The market path needs no such device: it is an index on
    Micron's own last price, so it is continuous at the seam by construction.
    """
    guided = guided or {}
    source = str(a.value("asp.price_source"))
    if source not in ("market", "fitted"):
        raise ValueError(f"asp.price_source must be market or fitted, not {source!r}")
    if source == "market" and not market:
        raise ValueError("asp.price_source is market but no market path was supplied")
    pin_end = Quarter.parse(str(a.value("asp.pin_end")))
    rho = a.scalar("asp.response_rho")
    t_max = a.scalar("asp.fitted_tightness_max")
    infl = a.scalar("asp.market_inflation_annual")
    floor = a.scalar("asp.price_floor_markup")

    ordered = sorted(signals, key=lambda s: s.quarter.index)
    t_by_q = {s.quarter: s.tightness for s in ordered}

    def ma4(q: Quarter) -> float:
        """Trailing mean over the same window the fit used. Built from the same
        quarters, or the coefficient means something different at run time."""
        window = [t_by_q[q - i] for i in range(MA_WINDOW) if (q - i) in t_by_q]
        return sum(window) / len(window)

    out: list[AspQuarter] = []
    residual = 0.0
    anchor: tuple[Quarter, float] | None = None   # last pinned/guided quarter and its ASP
    for s in ordered:
        q = s.quarter
        cost_here = costs.get(q)
        if cost_here is None or cost_here <= 0:
            continue

        t, t_ma = s.tightness, ma4(q)
        fitted = fitted_log_markup(a, t, t_ma)
        fitted_extrap = abs(t_ma) > t_max

        is_pinned = is_guided = is_floored = False
        index = 0.0
        if q <= pin_end:
            asp = pinned.get(q)
            if asp is None:
                continue
            # Carry the live residual forward: this is Micron's real markup against the
            # fit, and it is what the fitted cross-check eventually decays from.
            residual = math.log(asp / cost_here) - fitted
            fitted_asp = asp
            is_pinned = True
            anchor = (q, asp)
        elif q in guided:
            asp = guided[q]
            # Guidance re-bases the residual exactly as reality does.
            residual = math.log(asp / cost_here) - fitted
            fitted_asp = asp
            is_guided = True
            anchor = (q, asp)
        else:
            residual *= rho
            fitted_asp = math.exp(fitted + residual) * cost_here
            if source == "fitted":
                asp = fitted_asp
            else:
                if anchor is None or anchor[0] not in market or q not in market:
                    raise KeyError(f"market path has no price for {q} or its anchor")
                years = (q.index - anchor[0].index) / 4.0
                index = market[q] / market[anchor[0]] * (1.0 + infl) ** years
                asp = anchor[1] * index
            if asp < floor * cost_here:
                asp = floor * cost_here
                is_floored = True

        hbm_prem = interpolate_annual(a.series("asp.hbm_asp_premium"), q)
        nand_ratio = interpolate_annual(a.series("asp.nand_asp_ratio"), q)
        per_gb = units.GIGA * units.BITS_PER_BYTE
        projected = not (is_pinned or is_guided)

        out.append(
            AspQuarter(
                quarter=q,
                commodity_per_gb=asp * per_gb,
                hbm_per_gb=asp * hbm_prem * per_gb,
                nand_per_gb=asp * nand_ratio * per_gb,
                is_pinned=is_pinned,
                is_guided=is_guided,
                markup_over_cash_cost=asp / cost_here,
                tightness=t,
                tightness_ma4=t_ma,
                extrapolating=projected and source == "fitted" and fitted_extrap,
                fitted_commodity_per_gb=fitted_asp * per_gb,
                fitted_extrapolating=projected and fitted_extrap,
                market_index=index,
                is_floored=is_floored,
            )
        )
    return out
