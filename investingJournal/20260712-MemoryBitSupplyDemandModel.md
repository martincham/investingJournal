July 12th, 2026

Results note for the model in `memoryProjection/`. A record of what the model says, not
an argument. Related: [[20260608-MicronMU2026Thesis]]

## What it is

Two lines, quarterly, DRAM and NAND separately.

- **Supply** — bits producible, through the tightest of six candidate bottlenecks
- **Demand** — bits the world would consume **at constant 2025 real prices**

**Everything through 2026Q2 is observed data**, not model output. After that, P10–P90
bands from a 400-draw correlated Monte Carlo.

Open `memoryProjection/report/memory_model.html`.

## The asymmetry that governs how to read the chart

Supply can be pinned to reality. **Demand can never be**, and its band never collapses —
not even over history.

"Bits the world would consume at 2025 prices" is a *counterfactual*. What was observed in
2026 is what actually cleared, at 2026's prices, after phone makers cut memory content and
PC OEMs killed low-end SKUs. IDC attributes the 1Q26 smartphone decline (-2.9% YoY,
293.8M units) explicitly to memory constraints. That rationed outcome is not demand — it
is demand after the shortage got done with it.

So: the supply line has no error bar before 2026Q2. The demand line has one everywhere.

## Central case — DRAM (EB/yr)

| Year | Supply | Demand | Gap | Gap P10–P90 | Accelerators |
|---|---|---|---|---|---|
| 2025 | 39.0 | 43.6 | +11.7% | *observed supply* | 14.0M |
| 2026 | 43.6 | 52.7 | +20.9% | +16% … +30% | 18.0M |
| 2027 | 48.7 | 61.7 | +26.5% | +17% … +46% | 21.1M |
| 2028 | 53.5 | 71.6 | +33.8% | +19% … +58% | 25.4M |
| 2029 | 58.4 | 82.0 | +40.4% | +21% … +69% | 28.4M |
| 2030 | 64.5 | 92.6 | +43.6% | +27% … +74% | 29.9M |
| 2032 | 83.0 | 115.6 | +39.3% | +17% … +65% | 32.2M |

**P(gap closes) is ~0% in every projected year**, even at P10. Read that with the caveat
below, not as a probability statement about the world.

## Observed anchors the model is pinned to

| | |
|---|---|
| DRAM industry revenue 4Q25 | $53.58bn (+29.4% QoQ) |
| DRAM industry revenue 1Q26 | ~$97bn (+81% QoQ) |
| DRAM contract prices 1Q26 | up to +98% QoQ; Q2 guided +58–63% |
| Micron DRAM bits, 9M FY26 | +~30% YoY, on ASP +~140% |
| NVIDIA DC compute revenue | $60.4bn in the Apr-2026 quarter (+18% QoQ) |
| PC units 1Q26 | 65.6M (+3% YoY) — IDC calls it *pull-forward* ahead of price rises |
| Smartphone units 1Q26 | 293.8M (-2.9% YoY) — IDC blames memory constraints |

**The single most informative data point:** in 1Q26, DRAM revenue rose 81% while **bits
fell**. Suppliers' inventories were depleted and they could no longer ship more than they
made. That is what a supply wall looks like in the data.

## Findings

**1. EUV is not the bottleneck — cleanroom is, until ~2030.**
Most DRAM wafers never touch an EUV scanner: DRAM only began using EUV around 2020, and
legacy nodes, DDR4, niche DRAM and every CXMT wafer are pure DUV multipatterning. One
NXE:3600D delivers ~104,000 wafer-layers/month, so at 1–2 EUV layers a single scanner
supports 50–100 kWSPM. The EUV ceiling sits ~22% *above* installed capacity through 2029.
What binds is **cleanroom and installed wafer capacity** — concrete, not ASML.
Lithography takes over around 2030Q3, once EUV layers per wafer climb toward 5–6.

**2. A GPU stops being worth its watt about four years before it stops paying its power bill.**

| Vintage | TFLOP/W | HBM | Power-evicted | Cash-unviable | Life lost |
|---|---|---|---|---|---|
| 2020 (A100-class) | 0.8 | 32GB | **2026Q1** | 2030Q3 | 4.5 yr |
| 2021 | 1.1 | 40GB | 2026Q1 | 2031Q4 | 5.8 yr |
| 2022 | 1.6 | 64GB | 2028Q1 | never | 4+ yr |
| 2023 (H100-class) | 3.0 | 80GB | 2030Q1 | never | 4+ yr |

When power is the binding constraint, the real cost of an old GPU is not its electricity
bill — it is the output foregone by not putting a frontier chip in that same watt. A chip
doing 6% of the frontier's work per watt gets thrown out long before it is cash-unviable.
It is simultaneously **profitable to run and not worth keeping**.

**3. Replacement demand is real but smaller than expected: 3–6% of shipments, not 20%+.**
Retiring an A100 (80GB, 0.4kW) and refilling its watt with a Rubin Ultra (~1TB) is a large
HBM purchase for zero net power growth. But in the central case the datacentre buildout is
still growing fast enough that *new* power dominates — replacement only becomes the main
story if the buildout stalls. Worth watching: in a world where AI datacentre growth stops,
memory demand does **not** go to zero, it goes to the replacement stream.

**4. The answer rests on DRAM bits-per-wafer more than on anything AI-related.**
Sensitivity of the 2029 gap, ±25%: DRAM density **78 pts**, HBM wafer share 27, CXMT 15,
HBM trade-ratio 12, HBM GB/accelerator 8. The most important number is not an AI number —
it is whether DRAM density scaling is really as dead as assumed.

**5. The HBM trade-ratio (2.85x) is derived, not guessed.** HBM takes ~22% of DRAM *wafers*
in 2026 but yields only ~9% of DRAM *bits*. Solving gives k = 2.85, independently matching
a separate source's "one HBM wafer displaces three DRAM wafers."

**6. Announced ≠ built.** The datacentre pipeline model delivers ~62% of announced capacity
in 2026 falling to ~42% by 2032. Most of the shortfall is *slip* (arrives late) rather than
*cancellation* (never arrives) — which matters, because slipped capacity comes back and
cancelled capacity does not.

## The caveat that matters most

**P(gap closes) ≈ 0% is not a claim about the world.** It is a claim about the model's
inputs. The demand line is *unrationed by construction* — it never self-corrects, because
there is no price layer. In reality the gap closes partly by demand destruction (which is
already happening: phone makers are cutting memory content right now). The gap measures
**pressure**, not physical shortfall.

The Monte Carlo band is also narrower than true uncertainty: the sigmas are judgements,
not fitted from data, and structural surprises (3D DRAM landing early, a genuine AI capex
pause, a CXMT breakthrough) are not in the distribution at all.

## Credibility gate

The backcast reproduces **8 of 9 known cycle phases** 2018–2026, including the 2019 and
2023 gluts and the 2021 chip crisis. 53 tests. Bugs caught by tests rather than by
inspection: a power ceiling binding in 2026; an accelerator build 85% larger than the
capex could fund; annual anchors read as 1-Jan values (halving the inventory swings that
drive the cycle); HBM wafer share applied to a pool including CXMT (which makes no HBM); a
Monte Carlo that generated negative gigawatts; and HBM demand below HBM supply during a
period when HBM was sold out.
