"""Global memory bit supply & demand model, 2026Q1-2032Q4.

Two lines, quarterly, for DRAM and NAND separately:
  supply  -- bits the industry can physically produce, through the tightest of six
             bottlenecks, with the binding one identified in every quarter
  demand  -- bits the world would consume at constant 2025 real prices

No price layer, no financials. See 00-plan.md.
"""

from . import calendar, china, config, demand, scenarios, supply, units  # noqa: F401

__all__ = ["calendar", "china", "config", "demand", "scenarios", "supply", "units"]
