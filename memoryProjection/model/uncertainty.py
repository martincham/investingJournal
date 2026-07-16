"""Uncertainty windows: Monte Carlo over the load-bearing inputs.

Before 2026Q2 the SUPPLY line is observed and its band has zero width -- not because the
model is confident there, but because there is nothing to be uncertain about.

The DEMAND line is different, and the difference is the whole reason this module is
subtle. "Bits the world would consume at constant 2025 prices" was never observed and
never can be: what actually happened is that price rationed the market and buyers took
less. So demand is inferred in 2019 exactly as much as in 2031, and its band must not
collapse over history. See COUNTERFACTUAL below.

Three design choices worth knowing about:

1. SPREAD GROWS WITH HORIZON, as sigma * sqrt(years beyond 2026). A 2027 estimate is
   much better than a 2032 one, and a constant-width band would misrepresent that.

2. EXCEPT WHERE THE QUANTITY IS UNOBSERVABLE. The counterfactual content inputs carry a
   floor under that sqrt, so their spread never decays to nothing. Without it the horizon
   term quietly does the opposite of what this model claims to do: it collapses the
   demand band onto a number that was never measured, and draws it as if it were fact.

3. THE DRAWS ARE CORRELATED. Drawing 16 inputs independently understates the tails
   badly, because they average out. But the world where AI demand disappoints is the
   SAME world where the datacentre buildout stalls, compute gets cheap, and producers
   over-build. Everything going wrong at once is not a coincidence -- it is what a
   memory cycle IS. So the AI-facing inputs load on a common factor, the supply inputs
   load on another, and only the residual is idiosyncratic.

Read the bands as "roughly how wrong could this be", not as calibrated probabilities.
The sigmas are judgements, not fitted from data, and the model says so.

WHAT THE BANDS DO NOT COVER: every draw runs the same STRUCTURE, and that structure has
forward utilisation pinned near maximum and the inventory swing held at zero from 2028.
Those are the two mechanisms that produced every glut in the backcast. No draw can
therefore end the shortage, and P(gap closed) reads ~0 in the out-years. That number is a
property of the model's shape, not evidence about the world. See the report's
"What this model cannot show you".
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from . import china, config, demand, supply, units
from .actuals import actuals_end
from .calendar import Quarter
from .config import Assumptions
from .scenarios import build_assumptions

AI_CLUSTER = {
    "demand_ai.efficiency_deflator_annual",
    "demand_ai.hbm_gb_per_accelerator",
    "datacenter.realisation_rate",
    "datacenter.announced_gw_per_year",
    "gpu_fleet.economics.revenue_per_tflop_year_usd",
    "gpu_fleet.power_eviction.efficiency_threshold",
}
SUPPLY_CLUSTER = {
    "tech_roadmap.dram_gb_per_wafer",
    "tech_roadmap.hbm_trade_ratio",
    "tech_roadmap.hbm_wafer_share",
    "supply_capacity.dram_wafer_capacity_kwspm.samsung",
    "supply_capacity.dram_wafer_capacity_kwspm.sk_hynix",
    "supply_capacity.dram_wafer_capacity_kwspm.micron",
    "supply_capacity.dram_wafer_capacity_kwspm.cxmt",
}

# The inputs that define the COUNTERFACTUAL: how much memory a buyer would have put in a
# server, a PC, a phone or an accelerator if memory still cost 2025 money. These were
# never observed -- what was observed is what shipped after price did its rationing -- so
# their uncertainty does not go to zero as you walk backwards. Everything NOT in this set
# keeps the honest zero over history: wafers were built and bits were counted.
#
# This set is the difference between a demand band and a demand line pretending to be one.
COUNTERFACTUAL = {
    "demand_conventional.servers_traditional.dram_gb_per_unit",
    "demand_conventional.pc.dram_gb_per_unit",
    "demand_conventional.smartphone.dram_gb_per_unit",
    "demand_ai.hbm_gb_per_accelerator",
}


@dataclass
class Band:
    quarters: list[str]
    supply_p10: list[float]
    supply_p50: list[float]
    supply_p90: list[float]
    demand_p10: list[float]
    demand_p50: list[float]
    demand_p90: list[float]
    gap_p10: list[float]
    gap_p50: list[float]
    gap_p90: list[float]
    p_gap_closed: list[float]   # P(gap <= 0) -- i.e. the shortage is over


def _horizon_scale(q: Quarter, base_year: int = 2026, floor_years: float = 0.0) -> float:
    """Random-walk widening. Errors accumulate but partially cancel, hence sqrt.

    `floor_years` is the irreducible width carried by the counterfactual inputs, which
    never had a measured value to collapse onto. For everything else it is zero and this
    returns zero over history, which is the point: you do not get an error bar on a
    quarter you have already counted.
    """
    years = max(q.fractional_year - (base_year + 0.5), 0.0)
    return math.sqrt(max(years, floor_years))


def _draw_shocks(a: Assumptions, rng: random.Random) -> dict[str, tuple[float, float]]:
    """One Monte Carlo draw: a (sigma, z) pair per input, correlated within clusters.

    Returns the SHOCK, not the multiplier. The multiplier is built per-year in
    `_multiplier` as exp(sigma * sqrt(horizon) * z), which is strictly positive.

    That matters. An earlier version amplified the horizon in LINEAR space --
    `1 + (m - 1) * sqrt(horizon)` -- and a low draw on a wide input could push the
    multiplier straight through zero and out the other side. The model duly produced a
    datacentre pipeline delivering NEGATIVE gigawatts, and then a complex number when
    something took a fractional power of it. A multiplicative quantity has to be
    perturbed multiplicatively.
    """
    sig_group = a.group("uncertainty.sigma_2027")
    rho_ai = a.scalar("uncertainty.correlation.ai_demand_cluster")
    rho_sup = a.scalar("uncertainty.correlation.supply_cluster")

    z_ai = rng.gauss(0, 1)
    z_sup = rng.gauss(0, 1)

    out: dict[str, tuple[float, float]] = {}
    for path, asm in sig_group.items():
        sigma = float(asm)
        if path in AI_CLUSTER:
            rho, common = rho_ai, z_ai
        elif path in SUPPLY_CLUSTER:
            rho, common = rho_sup, z_sup
        else:
            rho, common = 0.0, 0.0
        z = math.sqrt(rho) * common + math.sqrt(1.0 - rho) * rng.gauss(0, 1)
        out[path] = (sigma, z)
    return out


def _multiplier(sigma: float, z: float, year: int, floor_years: float = 0.0) -> float:
    """Lognormal, mean ~1, spread widening as sqrt(years beyond 2026). Always > 0."""
    s = sigma * _horizon_scale(Quarter(year, 3), floor_years=floor_years)
    if s <= 0:
        return 1.0
    return math.exp(s * z - 0.5 * s * s)


def run_bands(scenario: str = "central", timeline: list[Quarter] | None = None,
              seed: int = 7) -> Band:
    from .calendar import full_timeline

    tl = timeline or full_timeline()
    base = build_assumptions(scenario)
    n = int(base.scalar("uncertainty.draws"))
    cutoff = actuals_end(base)
    floor = base.scalar("uncertainty.counterfactual_floor_years")
    rng = random.Random(seed)

    sup: list[list[float]] = [[] for _ in tl]
    dem: list[list[float]] = [[] for _ in tl]
    gap: list[list[float]] = [[] for _ in tl]

    for _ in range(n):
        shocks = _draw_shocks(base, rng)
        a = build_assumptions(scenario)
        for path, (sigma, z) in shocks.items():
            asm = a.get(path)
            # Counterfactual inputs keep a floor under their spread over history; measured
            # ones do not. See COUNTERFACTUAL above -- this one line is what stops the
            # demand band collapsing onto a number nobody ever observed.
            fl = floor if path in COUNTERFACTUAL else 0.0
            if isinstance(asm.value, dict):
                # Perturb each ANCHOR YEAR by its own horizon-scaled multiplier: 2026 is
                # nearly known, 2032 is not. For measured inputs history is untouched (the
                # multiplier is exactly 1 before 2026), because being uncertain about a
                # quarter you have already counted is not humility, it is a bug.
                asm.value = {y: v * _multiplier(sigma, z, y, fl) for y, v in asm.value.items()}
            else:
                asm.value = asm.value * _multiplier(sigma, z, 2029, fl)

            # A few inputs are fractions and must stay inside their natural bounds no
            # matter what the draw says. You cannot deliver 120% of the datacentres you
            # announced, and an annual efficiency gain cannot exceed 100% -- a tail draw
            # pushing the deflator past 1.0 sends (1 - rate) negative, and a fractional
            # power of a negative float is a complex number (the same failure class as
            # the linear-space amplification that once delivered negative gigawatts).
            if path == "datacenter.realisation_rate" and isinstance(asm.value, dict):
                asm.value = {y: min(v, 0.98) for y, v in asm.value.items()}
            if path == "demand_ai.efficiency_deflator_annual" and isinstance(asm.value, dict):
                asm.value = {y: min(v, 0.95) for y, v in asm.value.items()}

        ss = supply.supply_series(a, tl)
        dd = demand.demand_series(a, tl)
        bal = [china.balance_dram(a, s, d) for s, d in zip(ss, dd)]

        for i, b in enumerate(bal):
            sup[i].append(units.bits_to_eb(b.global_supply_bits) * 4)
            dem[i].append(units.bits_to_eb(b.global_demand_bits) * 4)
            gap[i].append(b.global_gap * 100)

    def pct(rows: list[float], p: float) -> float:
        r = sorted(rows)
        k = (len(r) - 1) * p
        lo, hi = int(math.floor(k)), int(math.ceil(k))
        return r[lo] if lo == hi else r[lo] * (hi - k) + r[hi] * (k - lo)

    # Collapse the band to zero width wherever the data is observed. The model may
    # disagree with reality in those quarters; reality wins, and it has no error bar.
    band = Band(
        quarters=[q.label for q in tl],
        supply_p10=[], supply_p50=[], supply_p90=[],
        demand_p10=[], demand_p50=[], demand_p90=[],
        gap_p10=[], gap_p50=[], gap_p90=[], p_gap_closed=[],
    )
    for i, q in enumerate(tl):
        observed = q <= cutoff

        # SUPPLY collapses to a point over observed quarters -- the bits were produced,
        # the number exists, there is nothing to be uncertain about.
        s50 = pct(sup[i], 0.5)
        band.supply_p50.append(s50)
        band.supply_p10.append(s50 if observed else pct(sup[i], 0.10))
        band.supply_p90.append(s50 if observed else pct(sup[i], 0.90))

        # DEMAND does NOT collapse, even in the past. "Bits the world would consume at
        # 2025 prices" is a counterfactual: it was never observed and never can be. It is
        # inferred everywhere, so it carries a band everywhere. Collapsing it over
        # history would be claiming to have measured something that never happened.
        band.demand_p50.append(pct(dem[i], 0.5))
        band.demand_p10.append(pct(dem[i], 0.10))
        band.demand_p90.append(pct(dem[i], 0.90))

        # The gap inherits demand's irreducible uncertainty, so it is banded throughout
        # too -- narrower over history (supply is known) but never zero.
        band.gap_p50.append(pct(gap[i], 0.5))
        band.gap_p10.append(pct(gap[i], 0.10))
        band.gap_p90.append(pct(gap[i], 0.90))

        band.p_gap_closed.append(sum(1 for g in gap[i] if g <= 0) / len(gap[i]))

    return band
