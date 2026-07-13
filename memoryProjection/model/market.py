"""STUB. The seam where a price / elasticity layer plugs in later.

Deliberately empty of logic. Pricing is out of scope for this build: the model
produces the two physical lines and the gap between them, and nothing else.

If a price layer is ever added, this is where it goes, and it would do two things the
current model deliberately does NOT do:

1.  Map the gap to an ASP path via a convex tightness->price response. Memory ASPs
    have historically moved 50-100% on single-digit supply/demand imbalances, so the
    function is strongly non-linear and would need calibrating against the 2016-18,
    2021 and 2023-24 episodes.

2.  Feed price back into demand via segment elasticities, which would let the demand
    line self-correct. Consumer and PC content are elastic (OEMs cut GB/unit when
    memory gets expensive -- they are doing it right now). AI and automotive are close
    to inelastic. Adding this would make the gap SMALLER and more realistic as a
    physical forecast, at the cost of making it useless as a pressure measure -- the
    market always clears, so a fully-clearing model shows no gap by construction.

Until then, read the gap as: "how hard price and rationing have to work", not "how
many bits go missing".
"""

from __future__ import annotations


def clear(*_args, **_kwargs):  # pragma: no cover - intentional stub
    raise NotImplementedError(
        "Price layer is deliberately out of scope. See module docstring, and "
        "00-plan.md section 0, for what it would need to do."
    )
