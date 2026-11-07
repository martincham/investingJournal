"""Global memory bit supply & demand model, 2026Q1-2032Q4.

Two lines, quarterly, for DRAM and NAND separately:
  supply  -- bits the industry can physically produce, through the tightest of six
             bottlenecks, with the binding one identified in every quarter
  demand  -- bits the world would consume at constant 2025 real prices, and (Nov 2026)
             at 2026Q3 prices

Plus (Nov 2026) an industry DRAM price layer in market.py: price, margin and revenue
projected from the last observed quarter. It reads the physical lines and never feeds
back into them. No company financials. See 00-plan.md.
"""

from . import calendar, china, config, demand, scenarios, supply, units  # noqa: F401

__all__ = ["calendar", "china", "config", "demand", "scenarios", "supply", "units"]
