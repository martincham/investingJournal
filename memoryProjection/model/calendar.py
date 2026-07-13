"""Quarterly time base for the model: 2018Q1 .. 2032Q4.

Quarterly resolution is load-bearing rather than cosmetic. Fab ramps are S-curves
measured in quarters, tool lead times are quoted in quarters, inventory swings and
consumer seasonality only exist at this resolution, and node transitions land
mid-year. An annual model cannot express any of that.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

HISTORY_START = (2018, 1)
PROJECTION_START = (2026, 1)
HORIZON_END = (2032, 4)


@dataclass(frozen=True, order=True)
class Quarter:
    year: int
    q: int

    def __post_init__(self) -> None:
        if not 1 <= self.q <= 4:
            raise ValueError(f"quarter must be 1..4, got {self.q}")

    @property
    def index(self) -> int:
        """Absolute quarter count, for arithmetic and S-curve positioning."""
        return self.year * 4 + (self.q - 1)

    def __add__(self, n: int) -> "Quarter":
        total = self.index + n
        return Quarter(total // 4, total % 4 + 1)

    def __sub__(self, other: "Quarter | int") -> "Quarter | int":
        if isinstance(other, Quarter):
            return self.index - other.index
        return self.__add__(-other)

    @property
    def label(self) -> str:
        return f"{self.year}Q{self.q}"

    @property
    def fractional_year(self) -> float:
        """Decimal year at the quarter midpoint, for continuous-time rates."""
        return self.year + (self.q - 0.5) / 4

    @classmethod
    def parse(cls, s: str) -> "Quarter":
        year, q = s.upper().split("Q")
        return cls(int(year), int(q))

    def __repr__(self) -> str:
        return self.label


def quarter_range(start: tuple[int, int], end: tuple[int, int]) -> list[Quarter]:
    a, b = Quarter(*start), Quarter(*end)
    return [a + i for i in range(b.index - a.index + 1)]


def full_timeline() -> list[Quarter]:
    """Backcast + projection: 2018Q1 .. 2032Q4."""
    return quarter_range(HISTORY_START, HORIZON_END)


def projection_timeline() -> list[Quarter]:
    """The two lines the model exists to draw: 2026Q1 .. 2032Q4."""
    return quarter_range(PROJECTION_START, HORIZON_END)


def history_timeline() -> list[Quarter]:
    """Calibration window: 2018Q1 .. 2025Q4."""
    return quarter_range(HISTORY_START, (2025, 4))


def s_curve(q: Quarter, start: Quarter, ramp_quarters: int, steepness: float = 5.0) -> float:
    """Fraction of full output a facility is producing in quarter `q`, in [0, 1].

    A fab does not switch on. It goes shell -> tool-in -> qualification -> volume over
    roughly 12-16 quarters, and output during that period follows an S, not a line:
    slow while tools are being installed and yields are terrible, fast through
    qualification, asymptotic as the last tools land.

    `start` is first-output quarter; `ramp_quarters` is the span to ~full output.
    """
    if ramp_quarters <= 0:
        return 1.0 if q >= start else 0.0

    elapsed = q - start
    if elapsed < 0:
        return 0.0
    if elapsed >= ramp_quarters:
        return 1.0

    # Logistic centred at the ramp midpoint, rescaled so f(0)=0 and f(ramp)=1 exactly.
    def logistic(x: float) -> float:
        return 1.0 / (1.0 + math.exp(-steepness * (x - 0.5)))

    x = elapsed / ramp_quarters
    lo, hi = logistic(0.0), logistic(1.0)
    return (logistic(x) - lo) / (hi - lo)


def annual_to_quarterly_rate(annual_rate: float) -> float:
    """Convert an annual growth rate (0.15 = +15%/yr) to its compounding quarterly rate."""
    return (1.0 + annual_rate) ** 0.25 - 1.0


def interpolate_annual(anchors: dict[int, float], q: Quarter) -> float:
    """Linearly interpolate a series given only at year anchors onto a quarter.

    Most public data (fab capacity, roadmap milestones, capex guides) is annual. This
    spreads it across quarters instead of stair-stepping, which would put artificial
    cliffs into the model every Q1.

    An annual anchor is treated as the value at the MIDDLE of that year, not on 1 Jan.
    That matters: these series are overwhelmingly flows ("units per year", "EB per
    year"), and an annual flow figure is the year's average, not its opening value.
    Anchoring at 1 Jan instead pulls every series about half a year early and visibly
    damps any sharp move -- it was quietly halving the amplitude of the inventory
    swings that drive the memory cycle, which showed up as a backcast that couldn't
    reproduce the 2023 glut.
    """
    if not anchors:
        raise ValueError("no anchors given")
    years = sorted(anchors)
    t = q.fractional_year - 0.5  # shift to compare against year midpoints

    if t <= years[0]:
        return anchors[years[0]]
    if t >= years[-1]:
        # Extrapolate at the trailing CAGR rather than flat-lining, which would
        # understate out-year supply.
        if len(years) >= 2:
            y0, y1 = years[-2], years[-1]
            v0, v1 = anchors[y0], anchors[y1]
            if v0 > 0 and y1 > y0:
                cagr = (v1 / v0) ** (1.0 / (y1 - y0)) - 1.0
                return v1 * (1.0 + cagr) ** (t - y1)
        return anchors[years[-1]]

    for y0, y1 in zip(years, years[1:]):
        if y0 <= t <= y1:
            v0, v1 = anchors[y0], anchors[y1]
            w = (t - y0) / (y1 - y0)
            return v0 + w * (v1 - v0)

    return anchors[years[-1]]
