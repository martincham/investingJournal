"""The income statement, cash flow and EPS. The whole model assembled.

**The rule this file exists to honour: real numbers through 2026Q3, projection after.**
There is exactly one boundary, and all three of its definitions coincide -- upstream's
`actuals_end`, Micron's last reported quarter (FQ4'26), and `asp.pin_end`. Before it,
every line is Micron's reported figure, verbatim, with no modelling of any kind. After
it, every line is modelled. `is_actual` says which, on every row.

One quarter sits between: the GUIDED quarter (FQ1'27, calendar 2026Q4). Its revenue,
GAAP gross margin, opex and tax rate are Micron's guide (assumptions/guidance.yaml); its
D&A, other income and share count are modelled, so its EPS landing inside the guided
range is a test of the parts that are not pinned. `is_guided` marks it.

The chain, per projected quarter:

    shipments      = production +/- inventory drawdown        (bits)
    revenue        = shipments x ASP, per pool (commodity / HBM / NAND)
    COGS           = shipments x cash cost + D&A
    gross profit   -> R&D, SG&A -> EBIT -> other -> tax -> net income
    diluted shares  = prior - buybacks + dilution
    EPS            = net income / diluted shares
"""

from __future__ import annotations

from dataclasses import dataclass

from model import asp as asp_mod
from model import cost as cost_mod
from model import micron as micron_mod
from model import tightness as tight_mod
from model import upstream
from model.conf import Assumptions
from model.edgar import ReportedQuarter
from model.fiscal import FiscalQuarter, normalise_flow
from model.vendor import units
from model.vendor.calendar import Quarter, interpolate_annual

BN = 1e9


@dataclass
class Row:
    """One quarter of Micron. Reported or modelled -- `is_actual` says which."""

    quarter: Quarter
    fiscal: FiscalQuarter | None
    is_actual: bool

    revenue: float = 0.0
    dram_revenue: float = 0.0
    hbm_revenue: float = 0.0
    nand_revenue: float = 0.0
    cogs: float = 0.0
    gross_profit: float = 0.0
    rnd: float = 0.0
    sga: float = 0.0
    ebit: float = 0.0
    other_income: float = 0.0
    tax: float = 0.0
    net_income: float = 0.0
    diluted_shares: float = 0.0
    eps: float = 0.0

    dna: float = 0.0
    capex: float = 0.0
    ocf: float = 0.0
    fcf: float = 0.0
    buyback: float = 0.0
    dividend: float = 0.0

    # bits & price
    shipped_bits: float = 0.0
    produced_bits: float = 0.0
    dram_bits: float = 0.0
    hbm_bits: float = 0.0
    nand_bits: float = 0.0
    commodity_asp_per_gb: float = 0.0
    hbm_asp_per_gb: float = 0.0
    cash_cost_per_gb: float = 0.0
    markup: float = 0.0
    tightness: float = 0.0
    tightness_ma4: float = 0.0
    extrapolating: bool = False   # P&L price is the fitted response, beyond its fitted range
    is_guided: bool = False       # company guidance, not reported and not modelled
    fitted_asp_per_gb: float = 0.0   # cross-check: what the fitted response says
    is_floored: bool = False      # price sat on Micron's own trough markup

    @property
    def gross_margin(self) -> float:
        return self.gross_profit / self.revenue if self.revenue else 0.0

    @property
    def operating_margin(self) -> float:
        return self.ebit / self.revenue if self.revenue else 0.0

    @property
    def fiscal_label(self) -> str:
        if self.fiscal:
            return self.fiscal.label
        from model.fiscal import fiscal_year_and_quarter

        fy, fq = fiscal_year_and_quarter(self.quarter)
        return f"FY{fy % 100:02d}Q{fq}"


@dataclass(frozen=True)
class Run:
    scenario: str
    rows: list[Row]
    baseline: upstream.Baseline

    def at(self, label: str) -> Row:
        for r in self.rows:
            if r.quarter.label == label:
                return r
        raise KeyError(label)

    def fiscal_year(self, fy: int) -> list[Row]:
        """FY_n = calendar (n-1)Q4 .. nQ3."""
        want = [Quarter(fy - 1, 4), Quarter(fy, 1), Quarter(fy, 2), Quarter(fy, 3)]
        return [r for r in self.rows if r.quarter in want]


def _pinned_asp_per_bit(
    a: Assumptions,
    reported: dict[Quarter, ReportedQuarter],
    bridge: dict[Quarter, cost_mod.Shipments],
    mu: dict[Quarter, micron_mod.MicronBits],
) -> dict[Quarter, float]:
    """Micron's OWN realised commodity ASP, from the filings.

    revenue / (shipped bits, weighted into commodity-price-equivalents). Not an industry
    blend and not a model output -- this is what Micron actually got per gigabyte.

    The price weighting differs from the cost weighting on purpose: HBM sells at ~3x
    commodity and costs ~3x, but those two ratios are not identical and their difference
    is exactly HBM's margin advantage. Reusing one set of weights for both would force
    every product to earn the same margin by construction.
    """
    out: dict[Quarter, float] = {}
    for q, br in bridge.items():
        r, m = reported.get(q), mu.get(q)
        if r is None or m is None:
            continue
        price_eq_produced = cost_mod.commodity_equivalent_bits(a, m, q)
        # Scale the price-equivalent bits by the shipped/produced ratio: we know the mix
        # of what was made, and assume what shipped carried the same mix.
        price_eq_shipped = price_eq_produced * (br.shipped_bits / br.produced_bits)
        if price_eq_shipped > 0:
            out[q] = normalise_flow(r.revenue, r.fiscal.days) / price_eq_shipped
    return out


def _guided_quarter(a: Assumptions, pin_end: Quarter) -> Quarter | None:
    """The one guided quarter, or None. guidance_end must be pin_end + 1 or earlier."""
    guidance_end = Quarter.parse(str(a.value("guidance.guidance_end")))
    if guidance_end <= pin_end:
        return None
    if guidance_end != pin_end + 1:
        raise ValueError(
            f"guidance.guidance_end {guidance_end} must be asp.pin_end + 1 ({pin_end + 1}): "
            f"the model carries one guided quarter, and a stale guide past a reported quarter "
            f"would override an actual"
        )
    return guidance_end


def _guided_revenue(a: Assumptions, scenario: str) -> float:
    targets = a.value("guidance.revenue_usd_bn")
    return float(targets.get(scenario, targets["central"])) * BN


def _guided_asp_per_bit(
    a: Assumptions,
    scenario: str,
    mu: dict[Quarter, micron_mod.MicronBits],
    pin_end: Quarter,
) -> dict[Quarter, float]:
    """Commodity ASP for the guided quarter, SOLVED from the revenue guide.

    ASP is whatever makes bits x price reproduce the guide, so revenue is hit exactly
    rather than approached. Shipments == production here, as in every projected quarter.
    """
    g = _guided_quarter(a, pin_end)
    if g is None or g not in mu:
        return {}
    price_eq = cost_mod.commodity_equivalent_bits(a, mu[g], g)
    return {g: _guided_revenue(a, scenario) / price_eq} if price_eq > 0 else {}


def _guided_cost_per_bit(
    a: Assumptions,
    scenario: str,
    mu: dict[Quarter, micron_mod.MicronBits],
    pin_end: Quarter,
) -> dict[Quarter, float]:
    """Commodity cash cost per bit for the guided quarter, backed out of the GAAP margin.

        COGS      = revenue_guide x (1 - gross_margin_guide)
        cash COGS = COGS - D&A                      (the P&L adds D&A back as a line)
        cost/bit  = cash COGS / cost-weighted bits

    The P&L then rebuilds COGS from exactly these pieces, so the guided quarter lands on
    the guided margin by construction -- and the cost curve compounds forward from a cost
    Micron effectively published, rather than from FQ4'26's derived cost, which carries
    a 98-day quarter and incentive comp absorbed into inventory.
    """
    g = _guided_quarter(a, pin_end)
    if g is None or g not in mu:
        return {}
    cogs = _guided_revenue(a, scenario) * (1.0 - a.scalar("guidance.gross_margin"))
    dna = interpolate_annual(a.series("opex.dna_usd_bn_per_quarter"), g) * BN
    cost_eq = cost_mod.commodity_equivalent_cost_bits(a, mu[g], g)
    return {g: (cogs - dna) / cost_eq} if cost_eq > 0 else {}


def _actual_row(r: ReportedQuarter, mu: micron_mod.MicronBits, br, asp_pb, cost_pb, t) -> Row:
    """A reported quarter. Every financial line is Micron's own number, untouched."""
    return Row(
        quarter=r.calendar,
        fiscal=r.fiscal,
        is_actual=True,
        revenue=r.revenue,
        cogs=r.cogs,
        gross_profit=r.gross_profit,
        rnd=r.rnd,
        sga=r.sga,
        ebit=r.ebit,
        tax=r.tax,
        net_income=r.net_income,
        diluted_shares=r.diluted_shares,
        eps=r.eps,
        dna=r.dna,
        capex=r.capex,
        ocf=r.ocf,
        fcf=r.fcf,
        buyback=r.buyback,
        dividend=r.dividend,
        shipped_bits=br.shipped_bits if br else 0.0,
        produced_bits=br.produced_bits if br else 0.0,
        dram_bits=mu.dram_bits,
        hbm_bits=mu.dram_hbm_bits,
        nand_bits=mu.nand_bits,
        commodity_asp_per_gb=asp_pb * units.GIGA * units.BITS_PER_BYTE if asp_pb else 0.0,
        cash_cost_per_gb=cost_pb * units.GIGA * units.BITS_PER_BYTE if cost_pb else 0.0,
        markup=(asp_pb / cost_pb) if (asp_pb and cost_pb) else 0.0,
        tightness=t,
        tightness_ma4=t,
    )


def run(a: Assumptions, scenario: str = "central") -> Run:
    base = upstream.load_baseline(a, scenario)
    mu = {m.quarter: m for m in micron_mod.series(a, base)}
    sigs = {s.quarter: s for s in tight_mod.series(a, base)}

    from model import edgar

    reported_list = edgar.load()
    reported = {r.calendar: r for r in reported_list}
    bridge = {b.quarter: b for b in cost_mod.bridge(a, reported_list, mu)}

    pin_end = Quarter.parse(str(a.value("asp.pin_end")))
    guided_q = _guided_quarter(a, pin_end)

    # Cash cost per bit: derived from the filings through the pin, backed out of the
    # margin guide for the guided quarter, then the learning curve from the last of those.
    costs: dict[Quarter, float] = {
        q: bridge[q].cash_cost_per_bit  # EXCLUDES D&A; the P&L adds it back
        for q in sorted(sigs) if q <= pin_end and q in bridge
    }
    costs.update(_guided_cost_per_bit(a, scenario, mu, pin_end))
    anchor_q = max(costs)
    for q in sorted(sigs):
        if q > anchor_q:
            costs[q] = cost_mod.modelled_commodity_cost_per_bit(a, q, anchor_q, costs[anchor_q])

    pinned = _pinned_asp_per_bit(a, reported, bridge, mu)
    guided = _guided_asp_per_bit(a, scenario, mu, pin_end)
    market = None
    if str(a.value("asp.price_source")) == "market":
        market = {q: m.price_usd_per_gb for q, m in upstream.load_market(a, scenario).items()}
    asps = {
        x.quarter: x
        for x in asp_mod.series(a, [sigs[q] for q in sorted(sigs)], costs, pinned, guided, market)
    }
    capex_guide = {
        Quarter.parse(str(k)): float(v)
        for k, v in a.value("guidance.capex_net_usd_bn_by_quarter").items()
    }

    rows: list[Row] = []
    prev_shares: float | None = None
    prev_fcf = 0.0

    for q in sorted(sigs):
        if q not in asps:
            continue
        m, s = mu[q], sigs[q]

        if q <= pin_end and q in reported:
            r = _actual_row(reported[q], m, bridge.get(q), pinned.get(q), costs.get(q), s.tightness)
            rows.append(r)
            prev_shares = r.diluted_shares
            prev_fcf = r.fcf
            continue

        if q <= pin_end:
            continue  # before Micron's reported window

        # ---- projected ----------------------------------------------------
        ap = asps[q]
        cost_pb = costs[q]
        hbm_mult = interpolate_annual(a.series("cost.hbm_cost_multiple"), q)
        nand_cost_ratio = interpolate_annual(a.series("cost.nand_cost_ratio"), q)

        # Shipments = production. The inventory wedge is a transient: you cannot drain a
        # warehouse forever, and by 2026Q1 Micron's was already empty (days-of-inventory
        # flat ~122 since). Assuming otherwise would be assuming free bits in perpetuity.
        # _guided_asp_per_bit relies on this identity too -- keep them consistent.
        ship_scale = 1.0
        comm_bits = m.dram_commodity_bits * ship_scale
        hbm_bits = m.dram_hbm_bits * ship_scale
        nand_bits = m.nand_bits * ship_scale

        to_gb = lambda b: b / (units.GIGA * units.BITS_PER_BYTE)  # noqa: E731
        dram_rev = to_gb(comm_bits) * ap.commodity_per_gb
        hbm_rev = to_gb(hbm_bits) * ap.hbm_per_gb
        nand_rev = to_gb(nand_bits) * ap.nand_per_gb
        revenue = dram_rev + hbm_rev + nand_rev

        cash_cogs = (
            to_gb(comm_bits) * cost_pb * units.GIGA * units.BITS_PER_BYTE
            + to_gb(hbm_bits) * cost_pb * hbm_mult * units.GIGA * units.BITS_PER_BYTE
            + to_gb(nand_bits) * cost_pb * nand_cost_ratio * units.GIGA * units.BITS_PER_BYTE
        )
        dna = interpolate_annual(a.series("opex.dna_usd_bn_per_quarter"), q) * BN
        cogs = cash_cogs + dna
        gross = revenue - cogs

        rnd = interpolate_annual(a.series("opex.rnd_usd_bn_per_quarter"), q) * BN
        sga = interpolate_annual(a.series("opex.sga_usd_bn_per_quarter"), q) * BN
        if q == guided_q:
            # The GAAP opex guide, split in the series' own R&D : SG&A ratio.
            scale = a.scalar("guidance.opex_usd_bn") * BN / (rnd + sga)
            rnd, sga = rnd * scale, sga * scale
        ebit = gross - rnd - sga
        other = interpolate_annual(a.series("opex.other_income_usd_bn_per_quarter"), q) * BN
        pretax = ebit + other

        # No tax benefit on losses. Micron carried valuation allowances through FY23
        # rather than booking the full shield; modelling a benefit would make the trough
        # look ~15% less bad than it was.
        rate = interpolate_annual(a.series("opex.tax_rate"), q)
        if q == guided_q:
            rate = a.scalar("guidance.tax_rate")
        tax = pretax * rate if pretax > 0 else 0.0
        net = pretax - tax

        if q in capex_guide:
            # Micron's FY27 plan is NET of government incentives; the model's capex line
            # is GROSS (EDGAR), so the expected incentives are added back.
            incent = interpolate_annual(a.series("capital.capex_incentives_usd_bn_per_quarter"), q)
            capex = (capex_guide[q] + incent) * BN
        else:
            capex = revenue * interpolate_annual(a.series("opex.capex_intensity"), q)
        ocf = net + dna
        fcf = ocf - capex

        div = interpolate_annual(a.series("capital.dividend_usd_bn_per_quarter"), q) * BN
        bb_share = interpolate_annual(a.series("capital.buyback_share_of_fcf"), q)
        buyback = max(0.0, (fcf - div) * bb_share)

        # Share count. The weakest line in the model: retiring shares needs a price,
        # which needs a valuation, which is out of scope. A through-cycle P/E on trailing
        # EPS stands in -- crude, mildly circular, and flagged speculative in capital.yaml.
        shares = prev_shares or 1_145e6
        dilution = interpolate_annual(a.series("capital.dilution_shares_m_per_quarter"), q) * 1e6
        pe = a.scalar("capital.implied_pe_for_buybacks")
        implied_price = max(1.0, (net * 4 / shares) * pe)
        retired = buyback / implied_price if implied_price > 0 else 0.0
        shares = shares + dilution - retired

        rows.append(
            Row(
                quarter=q,
                fiscal=None,
                is_actual=False,
                revenue=revenue,
                dram_revenue=dram_rev,
                hbm_revenue=hbm_rev,
                nand_revenue=nand_rev,
                cogs=cogs,
                gross_profit=gross,
                rnd=rnd,
                sga=sga,
                ebit=ebit,
                other_income=other,
                tax=tax,
                net_income=net,
                diluted_shares=shares,
                eps=net / shares if shares else 0.0,
                dna=dna,
                capex=capex,
                ocf=ocf,
                fcf=fcf,
                buyback=buyback,
                dividend=div,
                shipped_bits=comm_bits + hbm_bits,
                produced_bits=m.dram_bits,
                dram_bits=m.dram_bits,
                hbm_bits=m.dram_hbm_bits,
                nand_bits=m.nand_bits,
                commodity_asp_per_gb=ap.commodity_per_gb,
                hbm_asp_per_gb=ap.hbm_per_gb,
                cash_cost_per_gb=cost_pb * units.GIGA * units.BITS_PER_BYTE,
                markup=ap.markup_over_cash_cost,
                tightness=ap.tightness,
                tightness_ma4=ap.tightness_ma4,
                extrapolating=ap.extrapolating,
                is_guided=ap.is_guided,
                fitted_asp_per_gb=ap.fitted_commodity_per_gb,
                is_floored=ap.is_floored,
            )
        )
        prev_shares = shares
        prev_fcf = fcf

    return Run(scenario=scenario, rows=rows, baseline=base)
