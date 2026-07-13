"""AI datacentre pipeline: announced capacity minus the part that never gets built.

Announced GW and delivered GW are very different numbers, and the difference is one of
the largest swing factors in AI memory demand. Projects die in grid-interconnect queues
(4-7 years in PJM/ERCOT), for want of transformers and turbines, on local opposition,
on water, on financing, or because the anchor tenant walks. The further a project is
from a shovel, the more of it evaporates.

Output is a quarterly series of CUMULATIVE available AI datacentre power. That is the
ration card the fleet model spends: every accelerator needs a watt, and when watts are
scarce, an old GPU is not merely idle capital -- it is blocking a new one.
"""

from __future__ import annotations

from dataclasses import dataclass

from .calendar import Quarter, interpolate_annual, s_curve
from .config import Assumptions


@dataclass
class PowerQuarter:
    quarter: Quarter
    announced_gw: float        # gross, annualised
    delivered_gw: float        # net of attrition, annualised
    cancelled_gw: float        # never built at all
    slipped_gw: float          # late, not lost -- rolls forward
    cumulative_gw: float       # installed AI DC power available now


def power_series(a: Assumptions, timeline: list[Quarter]) -> list[PowerQuarter]:
    slip = int(a.scalar("datacenter.slip_quarters"))
    cancel_share = a.scalar("datacenter.cancellation_asymmetry")

    out: list[PowerQuarter] = []
    cumulative = 0.0
    # Capacity that slipped and is still owed to us. Delayed projects are not lost --
    # they arrive late, which is a completely different thing and the model must not
    # confuse the two.
    backlog = 0.0

    for q in timeline:
        announced = interpolate_annual(a.series("datacenter.announced_gw_per_year"), q)
        rate = interpolate_annual(a.series("datacenter.realisation_rate"), q)

        on_time = announced * rate
        shortfall = announced - on_time
        cancelled = shortfall * cancel_share
        slipped = shortfall - cancelled
        backlog += slipped / 4.0

        # Work off the backlog: slipped capacity arrives, spread over the slip window.
        from_backlog = backlog / max(slip, 1)
        backlog -= from_backlog

        delivered = on_time / 4.0 + from_backlog

        # Hard physical ceiling: interconnect queues, transformers, turbines. No amount
        # of money moves this in the short run.
        ceiling_q = interpolate_annual(
            a.series("datacenter.grid_interconnect_gw_ceiling"), q
        ) / 4.0
        if delivered > ceiling_q:
            backlog += delivered - ceiling_q   # the excess is deferred, not destroyed
            delivered = ceiling_q

        cumulative += delivered
        out.append(PowerQuarter(
            quarter=q,
            announced_gw=announced,
            delivered_gw=delivered * 4.0,
            cancelled_gw=cancelled,
            slipped_gw=slipped,
            cumulative_gw=cumulative,
        ))

    return out
