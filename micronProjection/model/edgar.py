"""Micron's reported financials, from SEC EDGAR's XBRL companyfacts API.

This module has no free parameters and no judgement calls. It is reality, and it must
be exactly right before anything is calibrated against it.

Four traps live here, all verified against the real filings rather than assumed:

1.  **`fy`/`fp` are wrong for period assignment.** They label the FILING a fact appeared
    in, not the fact's own period. The quarter 2024-08-30..2024-11-28 (actually FQ1
    FY2025) carries fy=2026, fp=Q1 because it shows up as the prior-year comparative in
    the FY26 Q1 10-Q. Periods are assigned from `start`/`end` dates. Nothing else.

2.  **Q4 is never reported.** Only FY (10-K) and the 9-month YTD exist, so Q4 has to be
    backed out. For additive flows that is FY - 9M.

3.  **...but three quantities are not additive.** Weighted-average share count is a
    MEAN: FY25 diluted = 1,125M and 9M = 1,123M, so FY - 9M gives *2M shares*. The
    right answer is 4*FY - 3*9M = 1,131M. EPS inherits the problem. Inventory is an
    instant, not a duration, and must never be differenced at all.

4.  **Cash-flow tags are YTD-only in 10-Qs.** There are no native quarterly durations
    for capex/OCF/D&A after FQ1, so only chain-differencing recovers Q2 and Q3.

The unified algorithm that handles 2-4: group facts by `start`, sort by `end`, and walk
the chain. A YTD group (ends at ~91/182/273/365 days) yields all four quarters by
differencing; a native quarterly fact is just a group whose chain has one link. Same
code path, no special cases.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Literal

from model.fiscal import DAYS_PER_QUARTER, FiscalQuarter, build_calendar
from model.vendor.calendar import Quarter

CIK = "CIK0000723125"
COMPANYFACTS_URL = f"https://data.sec.gov/api/xbrl/companyfacts/{CIK}.json"

# SEC requires a real contact address in the User-Agent and throttles to 10 req/s. We
# cache, so this is one request a day at most. The address comes from SEC_USER_AGENT
# (environment, or micronProjection/.env) so it stays out of the source.
USER_AGENT_VAR = "SEC_USER_AGENT"
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

CACHE = Path(__file__).resolve().parent.parent / "data" / "edgar" / "companyfacts.json"

# A duration this close to a quarter IS a quarter. The window is wide enough for the
# 98-day FQ4 of a 53-week year and narrow enough to never admit a half-year.
QUARTER_DAYS_MIN = 80
QUARTER_DAYS_MAX = 100

Kind = Literal["flow", "mean", "native", "instant"]

# Tag preference order per field. Coalesced left to right: Micron used SalesRevenueNet
# before ASC 606, so the modern tag simply does not exist in the older filings.
TAGS: dict[str, tuple[Kind, list[str]]] = {
    "revenue": ("flow", [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ]),
    "cogs": ("flow", ["CostOfGoodsAndServicesSold", "CostOfRevenue", "CostOfGoodsSold"]),
    "gross_profit": ("flow", ["GrossProfit"]),
    "rnd": ("flow", ["ResearchAndDevelopmentExpense"]),
    "sga": ("flow", ["SellingGeneralAndAdministrativeExpense"]),
    "ebit": ("flow", ["OperatingIncomeLoss"]),
    "pretax_income": ("flow", ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"]),
    "tax": ("flow", ["IncomeTaxExpenseBenefit"]),
    "net_income": ("flow", ["NetIncomeLoss"]),
    "dna": ("flow", ["DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet"]),
    "capex": ("flow", ["PaymentsToAcquirePropertyPlantAndEquipment"]),
    "ocf": ("flow", ["NetCashProvidedByUsedInOperatingActivities"]),
    "buyback": ("flow", ["PaymentsForRepurchaseOfCommonStock"]),
    "dividend": ("flow", ["PaymentsOfDividendsCommonStock"]),
    "diluted_shares": ("mean", ["WeightedAverageNumberOfDilutedSharesOutstanding"]),
    "basic_shares": ("mean", ["WeightedAverageNumberOfSharesOutstandingBasic"]),
    "inventory": ("instant", ["InventoryNet"]),
    # NOT a flow and NOT a mean: YTD EPS is cumulative earnings over AVERAGE shares, so
    # it is neither additive nor a mean of the quarterly figures. Chain-differencing it
    # any which way invents numbers (an early cut produced $12.31 for FY21Q4 against a
    # real ~$2.42). It exists here only to cross-check our recomputed EPS, so we read it
    # exactly where the filings state it and nowhere else. Q4 is simply absent.
    "eps_reported": ("native", ["EarningsPerShareDiluted"]),
}


@dataclass(frozen=True)
class Fact:
    start: date | None
    end: date
    val: float
    form: str
    filed: date

    @property
    def days(self) -> int:
        assert self.start is not None
        return (self.end - self.start).days + 1


def _user_agent() -> str:
    """SEC_USER_AGENT from the environment, else from micronProjection/.env."""
    value = os.environ.get(USER_AGENT_VAR, "").strip()
    if not value and ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            key, sep, val = line.strip().partition("=")
            if sep and key.strip() == USER_AGENT_VAR:
                value = val.strip().strip("\"'")
                break
    if not value:
        raise RuntimeError(
            f"{USER_AGENT_VAR} is not set. SEC requires a contact address in the "
            f"User-Agent: set it in micronProjection/.env (see .env.example)."
        )
    return value


def fetch(force: bool = False, max_age_days: int = 1) -> dict:
    """companyfacts JSON, cached to data/edgar/.

    Cached because it is a 4MB request that changes four times a year, and because the
    tests must not depend on the network.
    """
    if CACHE.exists() and not force:
        age = (time.time() - CACHE.stat().st_mtime) / 86400
        if age <= max_age_days:
            return json.loads(CACHE.read_text())

    import requests

    resp = requests.get(COMPANYFACTS_URL, headers={"User-Agent": _user_agent()}, timeout=60)
    resp.raise_for_status()
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(resp.text)
    return resp.json()


def _d(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _facts(doc: dict, tags: Iterable[str]) -> list[Fact]:
    """All facts for the first tag that exists, deduped by period.

    Restatements mean the same (start, end) appears in several filings with different
    values -- keep the latest `filed`, which is the company's current view. 10-K and
    10-Q only: 8-K exhibits and S-1s carry unaudited or re-cut figures.
    """
    gaap = doc["facts"]["us-gaap"]
    for tag in tags:
        if tag not in gaap:
            continue
        rows: list[dict] = []
        for unit_rows in gaap[tag]["units"].values():
            rows.extend(unit_rows)

        best: dict[tuple[str | None, str], dict] = {}
        for r in rows:
            if r.get("form") not in ("10-K", "10-Q"):
                continue
            key = (r.get("start"), r["end"])
            if key not in best or r["filed"] > best[key]["filed"]:
                best[key] = r
        if best:
            return [
                Fact(
                    start=_d(r["start"]) if r.get("start") else None,
                    end=_d(r["end"]),
                    val=float(r["val"]),
                    form=r["form"],
                    filed=_d(r["filed"]),
                )
                for r in best.values()
            ]
    return []


def _n_quarters(days: int) -> int:
    """How many quarters a duration spans. 1..4; anything else is not a fiscal period."""
    return max(1, round(days / DAYS_PER_QUARTER))


def quarterly_flow(facts: list[Fact]) -> dict[tuple[date, date], float]:
    """Recover single quarters from a mix of native and YTD durations.

    Group by `start`, walk each chain, difference consecutive cumulative values. A
    native quarterly fact is a one-link chain, so it needs no special handling. A YTD
    group differenced along its chain yields Q1..Q4 -- and this is the ONLY route to
    Q2/Q3 for the cash-flow tags, which are never reported as native quarters.
    """
    groups: dict[date, list[Fact]] = {}
    for f in facts:
        if f.start is not None:
            groups.setdefault(f.start, []).append(f)

    out: dict[tuple[date, date], float] = {}
    for start, chain in groups.items():
        chain.sort(key=lambda f: f.end)
        prev_end, prev_val = start, 0.0
        for f in chain:
            span = (f.end - prev_end).days + (1 if prev_end == start else 0)
            if QUARTER_DAYS_MIN <= span <= QUARTER_DAYS_MAX:
                q_start = prev_end if prev_end == start else prev_end + _ONE_DAY
                out[(q_start, f.end)] = f.val - prev_val
            prev_end, prev_val = f.end, f.val
    return out


def quarterly_mean(facts: list[Fact]) -> dict[tuple[date, date], float]:
    """Recover single quarters from weighted-average (non-additive) quantities.

    A YTD weighted-average share count is a mean over n quarters, so the quarter's own
    value is  Qn = n*YTD_n - (n-1)*YTD_(n-1), NOT a subtraction. Getting this wrong is
    not subtle: for FY2025, naive subtraction gives a Q4 diluted share count of 2
    million against a real 1,131 million, and EPS explodes by ~500x.
    """
    groups: dict[date, list[Fact]] = {}
    for f in facts:
        if f.start is not None:
            groups.setdefault(f.start, []).append(f)

    out: dict[tuple[date, date], float] = {}
    for start, chain in groups.items():
        chain.sort(key=lambda f: f.end)
        prev_end, prev_val, prev_n = start, 0.0, 0
        for f in chain:
            n = _n_quarters(f.days)
            span = (f.end - prev_end).days + (1 if prev_end == start else 0)
            if QUARTER_DAYS_MIN <= span <= QUARTER_DAYS_MAX and n - prev_n == 1:
                q_start = prev_end if prev_end == start else prev_end + _ONE_DAY
                out[(q_start, f.end)] = n * f.val - prev_n * prev_val
            prev_end, prev_val, prev_n = f.end, f.val, n
    return out


def native_quarters(facts: list[Fact]) -> dict[tuple[date, date], float]:
    """Only facts the filings state as a single quarter. No derivation, no differencing.

    For quantities that are neither additive nor a mean -- reported EPS -- there is no
    valid way to back out Q4, so we don't. A missing Q4 is honest; a synthesised one
    would silently become the thing we validate ourselves against.
    """
    return {
        (f.start, f.end): f.val
        for f in facts
        if f.start is not None and QUARTER_DAYS_MIN <= f.days <= QUARTER_DAYS_MAX
    }


from datetime import timedelta as _timedelta  # noqa: E402

_ONE_DAY = _timedelta(days=1)


@dataclass(frozen=True)
class ReportedQuarter:
    """One Micron fiscal quarter as reported. Actuals -- never modelled, never adjusted."""

    fiscal: FiscalQuarter
    revenue: float
    cogs: float
    gross_profit: float
    rnd: float
    sga: float
    ebit: float
    tax: float
    net_income: float
    dna: float
    capex: float
    ocf: float
    buyback: float
    dividend: float
    diluted_shares: float
    inventory: float
    eps_reported: float

    @property
    def calendar(self) -> Quarter:
        return self.fiscal.calendar

    @property
    def gross_margin(self) -> float:
        return self.gross_profit / self.revenue

    @property
    def operating_margin(self) -> float:
        return self.ebit / self.revenue

    @property
    def eps(self) -> float:
        """Recomputed, not taken from the filing.

        Reported EPS is only available natively for Q1..Q3; Q4's has to be derived
        anyway. Recomputing everything keeps one definition across the series, and
        test_recomputed_eps_matches_reported holds it to the filings where they overlap.
        """
        return self.net_income / self.diluted_shares

    @property
    def fcf(self) -> float:
        return self.ocf - self.capex


def load(doc: dict | None = None) -> list[ReportedQuarter]:
    """Every Micron fiscal quarter EDGAR can support, oldest first."""
    doc = doc or fetch()

    series: dict[str, dict[tuple[date, date], float]] = {}
    instants: dict[str, dict[date, float]] = {}
    for field, (kind, tags) in TAGS.items():
        facts = _facts(doc, tags)
        if kind == "flow":
            series[field] = quarterly_flow(facts)
        elif kind == "mean":
            series[field] = quarterly_mean(facts)
        elif kind == "native":
            series[field] = native_quarters(facts)
        else:
            instants[field] = {f.end: f.val for f in facts if f.start is None}

    # Revenue is the spine: a quarter exists if and only if revenue does.
    periods = sorted(series["revenue"])
    calendar = {(fq.start, fq.end): fq for fq in build_calendar(periods)}

    out: list[ReportedQuarter] = []
    for period in periods:
        get = lambda f: series[f].get(period, float("nan"))  # noqa: E731
        gp = series["gross_profit"].get(period)
        if gp is None:
            gp = series["revenue"][period] - series["cogs"].get(period, float("nan"))
        out.append(
            ReportedQuarter(
                fiscal=calendar[period],
                revenue=series["revenue"][period],
                cogs=get("cogs"),
                gross_profit=gp,
                rnd=get("rnd"),
                sga=get("sga"),
                ebit=get("ebit"),
                tax=get("tax"),
                net_income=get("net_income"),
                dna=get("dna"),
                capex=get("capex"),
                ocf=get("ocf"),
                buyback=series["buyback"].get(period, 0.0),
                dividend=series["dividend"].get(period, 0.0),
                diluted_shares=get("diluted_shares"),
                inventory=instants["inventory"].get(period[1], float("nan")),
                eps_reported=get("eps_reported"),
            )
        )
    return out


def by_calendar(quarters: list[ReportedQuarter]) -> dict[Quarter, ReportedQuarter]:
    return {q.calendar: q for q in quarters}
