"""Fit the price response to Micron's actual record. Run:  python -m model.calibrate

Every coefficient in assumptions/asp.yaml's response block comes out of here. Nothing in
that block is chosen, and this module exists so that claim is checkable rather than
asserted -- re-run it and the YAML values must reappear.

WHAT WAS WRONG BEFORE. The first cut modelled price as a convex push toward tightness
minus a "cost anchor" pulling ASP back to mu * cash_cost, with beta/gamma/kappa/mu all
set by hand. Three problems, in ascending order of seriousness:

  1. The numbers were guesses wearing a "calibrated against the backcast" comment.
  2. The anchor presupposes its own answer: it asks what fixed multiple of cost price
     returns to, when nothing says price returns to a multiple of cost at all. In a
     market 40% short there is no reason it would revert to a BALANCED-market markup.
  3. The data rejects it. Fitting the anchor over 2020-2026 gives kappa NEGATIVE for
     every gamma -- ASP diverged from mu*cost rather than reverting. Adding 2018-2019
     (the one completed boom-bust in the window, which the 2020 start had thrown away)
     flips it positive but to +0.004: a 40-year half-life, i.e. indistinguishable from
     no reversion at all.

WHAT THE DATA SUPPORTS. A level relationship between markup and SUSTAINED tightness:

    log(markup) = a + b * T + d * T_ma4        (R2 = 0.53, n = 34)

with the residual decaying at a fitted AR(1) rho. Two findings fell out of it:

  - b is ~0 and d carries everything. Price responds to the 4-quarter AVERAGE of
    tightness, not the current quarter. That is the hysteresis the anchor could not fit:
    T = +0.215 gave markup 2.54 in 2021Q2 but T = +0.225 gave 8.58 in 2026Q2, because
    2026Q2 was the fourth consecutive tight quarter and 2021Q2 was the first.
  - exp(a) = 2.33x is the fitted markup at T = 0, which independently reproduces the
    2.39x measured from the seven balanced quarters by a different method. Two routes,
    2% apart. That agreement is the main reason to trust the intercept.

WHAT IS STILL NOT KNOWN, and no amount of fitting will fix it: the observed window spans
|T| <= 0.27. Upstream's out-years run T = +0.30 to +0.65. Applying the fit there is an
extrapolation to 2.4x beyond any quarter on record, and the model says so rather than
hiding it behind a saturation term (which the earlier cut invented, at a cap picked out
of the air, and which had the effect of making a market getting 2.6x tighter barely move
price at all).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from model import cost as cost_mod
from model import edgar, micron, tightness, upstream
from model.conf import Assumptions, load
from model.fiscal import normalise_flow
from model.vendor.calendar import Quarter

MA_WINDOW = 4


@dataclass(frozen=True)
class Observation:
    quarter: Quarter
    asp_per_bit: float
    cash_cost_per_bit: float
    tightness: float

    @property
    def markup(self) -> float:
        return self.asp_per_bit / self.cash_cost_per_bit


@dataclass(frozen=True)
class Fit:
    a: float
    b: float
    d: float
    rho: float
    r2: float
    n: int
    t_min: float
    t_max: float
    markup_at_zero: float


def observations(a: Assumptions, scenario: str = "central") -> list[Observation]:
    """Micron's realised markup and the tightness it faced, every reported quarter.

    Uses the FULL available window (2018Q1 on), not the 2020 start the report uses. The
    2018 boom and 2019 glut are the only completed cycle in the record; excluding them
    was what made the anchor un-fittable.

    Ends at asp.pin_end. EDGAR keeps filing past the seam, but upstream's tightness after
    its actuals_end is PROJECTED, so a later quarter would fit real revenue against a
    modelled market.
    """
    pin_end = Quarter.parse(str(a.value("asp.pin_end")))
    base = upstream.load_baseline(a, scenario)
    mu = {m.quarter: m for m in micron.series(a, base)}
    rep = edgar.load()
    reported = {r.calendar: r for r in rep}
    bridge = {s.quarter: s for s in cost_mod.bridge(a, rep, mu)}
    sig = {s.quarter: s for s in tightness.series(a, base)}

    out: list[Observation] = []
    for q in sorted(bridge):
        if q > pin_end or q not in sig or q not in reported:
            continue
        s, r, m = bridge[q], reported[q], mu[q]
        price_eq = cost_mod.commodity_equivalent_bits(a, m, q) * (s.shipped_bits / s.produced_bits)
        if price_eq <= 0 or s.cash_cost_per_bit <= 0:
            continue
        out.append(
            Observation(
                quarter=q,
                asp_per_bit=normalise_flow(r.revenue, r.fiscal.days) / price_eq,
                cash_cost_per_bit=s.cash_cost_per_bit,
                tightness=sig[q].tightness,
            )
        )
    return out


def moving_average(values: list[float] | np.ndarray, window: int = MA_WINDOW) -> np.ndarray:
    """Trailing mean, back-filled at the start with whatever history exists.

    The projection must build this the same way, from the same quarters, or the fitted
    coefficient means something different at run time than it did at fit time.
    """
    v = np.asarray(values, dtype=float)
    return np.array([v[max(0, i - window + 1) : i + 1].mean() for i in range(len(v))])


def fit(obs: list[Observation]) -> Fit:
    t = np.array([o.tightness for o in obs])
    ma = moving_average(t)
    y = np.log([o.markup for o in obs])
    X = np.c_[np.ones(len(obs)), t, ma]

    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    r2 = 1.0 - float((resid**2).sum()) / float(((y - y.mean()) ** 2).sum())

    # AR(1) on the residual: how long a deviation from the fitted level persists. This is
    # the ONLY dynamics in the model, and it is measured rather than posited.
    rho = float(np.linalg.lstsq(resid[:-1, None], resid[1:], rcond=None)[0][0])

    return Fit(
        a=float(coef[0]),
        b=float(coef[1]),
        d=float(coef[2]),
        rho=rho,
        r2=r2,
        n=len(obs),
        t_min=float(t.min()),
        t_max=float(t.max()),
        markup_at_zero=float(math.exp(coef[0])),
    )


def main() -> None:
    a = load()
    obs = observations(a)
    f = fit(obs)
    print(f"n = {f.n}   {obs[0].quarter} .. {obs[-1].quarter}")
    print(f"observed tightness range: {f.t_min:+.3f} .. {f.t_max:+.3f}")
    print()
    print("log(markup) = a + b*T + d*T_ma4")
    print(f"  a     {f.a:+.4f}     (markup at T=0: {f.markup_at_zero:.3f}x)")
    print(f"  b     {f.b:+.4f}     (current-quarter tightness: ~0, price tracks the average)")
    print(f"  d     {f.d:+.4f}     (4-quarter average tightness: carries the signal)")
    print(f"  rho   {f.rho:+.4f}     (residual AR(1); half-life "
          f"{math.log(0.5) / math.log(abs(f.rho)):.1f} quarters)")
    print(f"  R2    {f.r2:.4f}      n={f.n}")
    print()
    print("Paste into assumptions/asp.yaml (response block). Extrapolation, for the record:")
    for t in (f.t_max, 0.40, 0.50, 0.60):
        mk = math.exp(f.a + f.b * t + f.d * t)
        tag = "  <- max observed; beyond here the fit is extrapolating" if t == f.t_max else ""
        print(f"   sustained T={t:+.2f} -> markup {mk:6.2f}x cash cost{tag}")


if __name__ == "__main__":
    main()
