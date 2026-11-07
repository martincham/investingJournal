# Micron reported data

Last updated 2026-11-07. Latest reported quarter: **FY26Q4** (ended 2026-09-03, calendar 2026Q3, a 98-day quarter). Next report: FY27Q1, around mid-December 2026.

| File | What it holds | How it's made |
|---|---|---|
| `quarterly_gaap.csv` | GAAP P&L, cash flow, inventory and shares for every fiscal quarter EDGAR supports | `./.venv/bin/python data/export_reported.py`. It reads the cached `data/edgar/companyfacts.json` through `model.edgar.load`, so FQ4 is derived as FY minus 9M, the same way the model does it |
| `release_metrics.csv` | Figures XBRL doesn't carry: non-GAAP lines, DRAM/NAND revenue and bit/price changes, business-unit results, SCA/RPO, DIO | Entered by hand from the earnings releases and prepared remarks |
| `guidance.csv` | Company guidance with the actual result once reported, plus FY27 and industry bit-growth outlook | Entered by hand from the same documents |

The raw source documents live in `data/filings/<quarter>/` and are gitignored. Re-download them from EDGAR (8-K exhibit 99.1) or investors.micron.com.

Things to know:

- **Ranges.** Qualitative statements ("mid-20s percentage range") are stored as `value_low`/`value_high` or `low`/`mid`/`high`. Those numbers are my reading of the wording. The original text is kept in `as_stated`.
- **FCF definitions differ.** In `quarterly_gaap.csv`, FCF is OCF minus gross PP&E spending. Micron's "adjusted FCF" uses capex net of government incentives. For FY26Q4 that's $32,863M against $33,199M.
- **Diluted shares for Q4** are backed out of rounded means, so they can be off by about 1M from the filing (1,146M vs 1,147M in FY26Q4).
- **SCA customer deposits** sit in financing cash flow ($12.3B received in FY26Q4), not in OCF or FCF.
