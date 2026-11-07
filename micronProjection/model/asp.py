"""ASP: pinned to reality through 2026Q2, fitted after.

This is the layer memoryProjection deliberately left out -- its model/market.py is a stub
whose docstring is, in effect, this file's specification.

    q <= pin_end:       ASP = Micron's own realised revenue / shipped bits. REPORTED.
    q <= guidance_end:  ASP = solved from company guidance / analyst consensus. GUIDED.
    q >  guidance_end:  markup(q) = exp(a + b*T(q) + d*T_ma4(q) + residual(q))
                        residual(q) = rho * residual(q-1)
                        ASP(q) = markup(q) * cash_cost(q)      FITTED.

The middle state is not a rounding of the other two. A guide from the company, two months
into the quarter, is better information about that quarter than a response fitted at
R2 = 0.53 and extrapolating 2x beyond its range -- which, left alone, projects ASP roughly
FLAT across the next two quarters against a consensus of +17% each. But guidance is not
reported data either: `is_actual` stays false for these quarters and they are marked
separately everywhere.

**Every coefficient here is fitted.** a, b, d and rho come out of model/calibrate.py,
which regresses Micron's realised markup on the tightness it actually faced across all 34
reported quarters (2018Q1..2026Q2). Nothing in this file is chosen to make the answer come
out a particular way, and `python -m model.calibrate` regenerates the YAML values.

WHAT THIS REPLACED, and why it matters. The first version was a convex push toward
tightness minus a "cost anchor" pulling ASP back toward mu * cash_cost, with four
hand-set parameters. It was wrong in a way worth remembering: the anchor PRESUPPOSED ITS
ANSWER. Asking "what fixed multiple of cost does price revert to" assumes price reverts
to a multiple of cost, and in a market 40% short there is no reason it would return to a
balanced-market markup. The data agreed: fitting kappa gives a NEGATIVE coefficient over
2020-2026 and +0.004 (a 40-year half-life) over the full window. There is no mean
reversion to mu*cost in Micron's record. It was my invention, and because it was set too
low and on the wrong cost basis it was suppressing projected margins by ~25pp.

TWO FINDINGS THAT FELL OUT OF FITTING IT PROPERLY:

  1. Price tracks SUSTAINED tightness. b (current quarter) fits to ~0; d (the 4-quarter
     average) carries everything. This is the hysteresis the anchor could never fit --
     T=+0.215 gave markup 2.54 in 2021Q2 but T=+0.225 gave 8.58 in 2026Q2, because by
     2026Q2 the market had been tight for four straight quarters. Memory pricing has
     memory.
  2. exp(a) = 2.33x is the fitted markup at T=0, which independently reproduces the 2.39x
     measured from the seven balanced quarters by a completely different route. Two
     methods, 2% apart.

THE ONE THING STILL NOT KNOWN. The fit spans |T| <= 0.27. Upstream's out-years run
T = +0.30 to +0.65, so the projection extrapolates 2.4x beyond any quarter on record, and
the markup it implies (5-11x) is outside anything Micron has sustained. That is a real
limitation and it is reported rather than suppressed. An earlier cut "solved" it with a
saturation term at a cap picked out of the air, which had the effect of making a market
getting 2.6x tighter barely move price -- i.e. quietly overriding the input this model
exists to take as given. If the extrapolation is wrong, the honest fix is upstream's bit
lines, not a damping term here.
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
    extrapolating: bool          # True when T is outside the fitted range


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
) -> list[AspQuarter]:
    """The full ASP path: reported through pin_end, fitted after.

    The residual carries across the seam and decays at the fitted rho, so the projection
    starts from Micron's ACTUAL markup (8.58x at 2026Q2, against a fitted 4.18x) and
    converges to the fitted level over ~8 quarters rather than stepping to it. Without
    this the seam would show a 2x discontinuity in price that no quarter ever contained.
    """
    guided = guided or {}
    pin_end = Quarter.parse(str(a.value("asp.pin_end")))
    rho = a.scalar("asp.response_rho")
    t_max = a.scalar("asp.fitted_tightness_max")

    ordered = sorted(signals, key=lambda s: s.quarter.index)
    t_by_q = {s.quarter: s.tightness for s in ordered}

    def ma4(q: Quarter) -> float:
        """Trailing mean over the same window the fit used. Built from the same
        quarters, or the coefficient means something different at run time."""
        window = [t_by_q[q - i] for i in range(MA_WINDOW) if (q - i) in t_by_q]
        return sum(window) / len(window)

    out: list[AspQuarter] = []
    residual = 0.0
    for s in ordered:
        q = s.quarter
        cost_here = costs.get(q)
        if cost_here is None or cost_here <= 0:
            continue

        t, t_ma = s.tightness, ma4(q)
        fitted = fitted_log_markup(a, t, t_ma)

        is_pinned = is_guided = False
        if q <= pin_end:
            asp = pinned.get(q)
            if asp is None:
                continue
            # Carry the live residual forward: this is Micron's real markup against the
            # fit, and it is what the projection eventually decays from.
            residual = math.log(asp / cost_here) - fitted
            is_pinned = True
        elif q in guided:
            asp = guided[q]
            # Guidance re-bases the residual exactly as reality does. The fitted response
            # then decays from where guidance leaves off, not from the last reported
            # quarter -- otherwise the two guided quarters would be overwritten the moment
            # the fit took over.
            residual = math.log(asp / cost_here) - fitted
            is_guided = True
        else:
            residual *= rho
            asp = math.exp(fitted + residual) * cost_here

        hbm_prem = interpolate_annual(a.series("asp.hbm_asp_premium"), q)
        nand_ratio = interpolate_annual(a.series("asp.nand_asp_ratio"), q)
        per_gb = units.GIGA * units.BITS_PER_BYTE

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
                extrapolating=(not is_pinned) and (not is_guided) and abs(t_ma) > t_max,
            )
        )
    return out
