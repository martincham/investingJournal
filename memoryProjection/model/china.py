"""China as a captive region: selling west is reallocation, not new supply.

The premise: CXMT's (and YMTC's) output is fully booked domestically. Chinese memory
supply serves Chinese memory demand.

It is worth being precise about what does and does not follow from that, because it is
easy to overclaim and the tests in tests/test_china.py exist to stop exactly that.

WHAT IS TRUE -- the reallocation invariant:

    WHERE Chinese bits are sold cannot change the global balance.

    If CXMT exports a bit west, the Chinese buyer who lost it must import a bit from
    Samsung/SK/Micron to replace it. Supply and demand in the merchant pool both move
    by the same amount, and the world's total deficit is untouched. Formally, for
    captive fraction c:

        global deficit   = D - S                      (independent of c)
        merchant deficit = (D - c) - (S - c) = D - S  (identical, for every c)

    So the ABSOLUTE deficit is invariant. Only the RATIO (D-c)/(S-c) moves with c, and
    that movement is a bookkeeping artifact of changing the denominator -- not a
    physical effect. Read the deficit, not the ratio, when comparing scopes.

WHAT IS NOT TRUE -- and the model refuses to pretend otherwise:

    "A CXMT ramp cannot close the global gap."

    It can. More CXMT capacity means more bits physically exist, and the world is
    better off by exactly that many bits. What a CXMT ramp does NOT do is add bits to
    what NON-CHINESE producers ship: its relief to the merchant market comes entirely
    from China importing less, and is therefore bounded by Chinese domestic demand.
    Once China is self-sufficient, further CXMT output has to be exported to go
    anywhere at all.

The double-count this module prevents is counting CXMT wafers as merchant supply
relief while ALSO leaving Chinese demand in the merchant pool. That version of the
model shows a shortage ending that never ends.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import units
from .config import Assumptions
from .demand import DemandQuarter
from .supply import SupplyQuarter


@dataclass
class Balance:
    """Supply, demand and gap for one quarter, at both global and addressable scope."""

    quarter_label: str

    global_supply_bits: float
    global_demand_bits: float

    addressable_supply_bits: float
    addressable_demand_bits: float

    captive_bits: float

    @property
    def global_gap(self) -> float:
        """Demand / supply - 1. Unserved demand at constant 2025 prices."""
        if self.global_supply_bits <= 0:
            return 0.0
        return self.global_demand_bits / self.global_supply_bits - 1.0

    @property
    def addressable_gap(self) -> float:
        """The merchant market's gap -- the pool Samsung/SK/Micron actually sell into.

        NOTE the ratio (unlike the deficit) depends on the scope you measure it over,
        so it is only comparable across runs at a FIXED captive_share. Use
        `deficit_eb` when comparing scopes.
        """
        if self.addressable_supply_bits <= 0:
            return 0.0
        return self.addressable_demand_bits / self.addressable_supply_bits - 1.0

    @property
    def deficit_bits(self) -> float:
        """Unserved demand at constant 2025 prices, in bits.

        The physically meaningful number, and invariant to where the bits get sold:
        the merchant deficit and the global deficit are always identical, because
        moving a bit from the captive pool to the merchant pool moves supply AND
        demand by the same amount.
        """
        return self.global_demand_bits - self.global_supply_bits

    @property
    def deficit_eb(self) -> float:
        return units.bits_to_eb(self.deficit_bits)

    @property
    def merchant_deficit_bits(self) -> float:
        return self.addressable_demand_bits - self.addressable_supply_bits

    @property
    def global_supply_eb(self) -> float:
        return units.bits_to_eb(self.global_supply_bits)

    @property
    def global_demand_eb(self) -> float:
        return units.bits_to_eb(self.global_demand_bits)

    @property
    def addressable_supply_eb(self) -> float:
        return units.bits_to_eb(self.addressable_supply_bits)

    @property
    def addressable_demand_eb(self) -> float:
        return units.bits_to_eb(self.addressable_demand_bits)


def _balance(
    label: str,
    total_supply: float,
    total_demand: float,
    china_supply: float,
    china_demand: float,
    captive_share: float,
) -> Balance:
    # Bits produced in China AND absorbed in China. Cannot exceed either side.
    captive = min(china_supply * captive_share, china_demand)
    captive = max(0.0, captive)

    return Balance(
        quarter_label=label,
        global_supply_bits=total_supply,
        global_demand_bits=total_demand,
        # Both sides drop by the same absolute amount. That symmetry is the point:
        # it is what makes the global gap invariant to captive_share.
        addressable_supply_bits=max(total_supply - captive, 1e-9),
        addressable_demand_bits=max(total_demand - captive, 1e-9),
        captive_bits=captive,
    )


def balance_dram(a: Assumptions, s: SupplyQuarter, d: DemandQuarter) -> Balance:
    return _balance(
        s.quarter.label,
        s.dram_total_bits,
        d.dram_total_bits,
        s.dram_china_bits,
        d.dram_china_bits,
        a.scalar("china.captive_share"),
    )


def balance_nand(a: Assumptions, s: SupplyQuarter, d: DemandQuarter) -> Balance:
    return _balance(
        s.quarter.label,
        s.nand_total_bits,
        d.nand_total_bits,
        s.nand_china_bits,
        d.nand_china_bits,
        a.scalar("china.captive_share"),
    )
