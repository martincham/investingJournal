# Memory projection vintage 2026-11

| | |
|---|---|
| Source commit | `f73b926` |
| Observed data through | 2026Q3 |
| Generated (UTC) | 2026-11-07T19:23:14+00:00 |
| Scenarios | tight,central,loose |
| memory_model.sqlite sha256 | `7ca3ee8d39107e8ce8dea1b92800ded3c7769e3c4278de0d1b5ad03c8e756055` |

The November 2026 projection, including the industry DRAM price layer (table `market`). Observed data through 2026Q3 (Q3 derived from company reports, pending TrendForce in December). Adds demand at 2026Q3 prices alongside unrationed demand, the `ai_cpu_server` segment, and price, margin and revenue per quarter. Re-frozen on 2026-11-07 after the price layer was added; the first November freeze (7149d2a, never pushed) had no market table.

## Moving micronProjection from 2026-07 to this vintage

In `micronProjection/assumptions/upstream.yaml` and its tests:

1. `sqlite_path: ../memoryProjection/vintages/2026-11/memory_model.sqlite`, and `expected_sha256` from the table above.
2. `expected_actuals_end: 2026Q3`. This lines up with Micron FQ4'26, now in the EDGAR cache, so `asp.pin_end` moves with it.
3. Add `ai_cpu_server` to `inelastic_segments` (agentic-AI CPU servers). The loader raises on unknown segments by design.
4. `test_hbm_is_never_capped_upstream` will fail: `hbm_is_capped` is true in 2032Q2–Q4 of central (test ceiling C5). Relax it to "never capped before 2032" or drop it.
5. AI is now rationed in reality (HBM and LPDDR cuts per unit). The unrationed line still serves the inelastic core first, so the contested-pool tightness signal is unchanged in kind. See AGENTS.md, "But reality now rations AI too".
6. A choice for the price model: keep the fitted ASP response, or read industry price and margin from the `market` table (real 2025 $/GB; the speed is in `run_meta.market_kappa`).

Frozen output. Do not edit or re-run. `assumptions/` is a copy of the inputs
that produced it, so `diff -r vintages/<old>/assumptions vintages/<new>/assumptions`
shows what changed between projections.
