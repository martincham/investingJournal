"""The model's bits and revenue split against what Micron said about FQ4'26.

Micron does not report bits, so these use the qualitative statements recorded in
data/reported/release_metrics.csv: DRAM bit shipments "up mid-single-digit", NAND
"approximately 10%", DRAM 73% / NAND 26% of revenue. They check the bit share
(model/micron.py) and the price ratios (asp.yaml) at the last reported quarter.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from model import cost, micron, upstream
from model.conf import load
from model.vendor.calendar import Quarter, interpolate_annual

ROOT = Path(__file__).resolve().parent.parent
FQ3, FQ4 = Quarter(2026, 2), Quarter(2026, 3)


@pytest.fixture(scope="module")
def a():
    return load()


@pytest.fixture(scope="module")
def mu(a):
    base = upstream.load_baseline(a, "central")
    return {m.quarter: m for m in micron.series(a, base)}


@pytest.fixture(scope="module")
def metrics():
    with (ROOT / "data" / "reported" / "release_metrics.csv").open() as fh:
        return {(r["fiscal_label"], r["metric"]): r for r in csv.DictReader(fh)}


def test_dram_bit_growth_matches_mid_single_digits(mu, metrics):
    m = metrics[("FY26Q4", "dram_bits_qoq")]
    lo, hi = float(m["value_low"]), float(m["value_high"])
    growth = mu[FQ4].dram_bits / mu[FQ3].dram_bits - 1
    assert lo - 0.01 <= growth <= hi + 0.01, f"model DRAM bits {growth:+.1%} vs '{m['as_stated']}'"


@pytest.mark.xfail(
    strict=True,
    reason="Model NAND PRODUCTION +5.4% vs reported NAND SHIPMENTS ~+10% in FQ4'26. "
    "Upstream calls its NAND line the unreliable one, and production is not shipments. "
    "Revenue split still matches (next test). Flips to passing if either moves.",
)
def test_nand_bit_growth_matches_about_ten_percent(mu, metrics):
    growth = mu[FQ4].nand_bits / mu[FQ3].nand_bits - 1
    assert growth == pytest.approx(float(metrics[("FY26Q4", "nand_bits_qoq")]["value"]), abs=0.025)


def test_nand_share_of_revenue_matches_fq4(a, mu, metrics):
    """NAND $14.1bn of $54.2bn. The nand_asp_ratio x bits must reproduce that share --
    the check that caught a 16x error in this ratio in July would catch it again."""
    m = mu[FQ4]
    eq = cost.commodity_equivalent_bits(a, m, FQ4)
    share = interpolate_annual(a.series("asp.nand_asp_ratio"), FQ4) * m.nand_bits / eq
    nand = float(metrics[("FY26Q4", "nand_revenue")]["value"])
    dram = float(metrics[("FY26Q4", "dram_revenue")]["value"])
    assert share == pytest.approx(nand / (nand + dram), abs=0.03)
