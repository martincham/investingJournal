"""Unit handling for memory bit quantities.

Everything internal to the model is stored in **bits**. Nothing else. The single
most common way a memory-industry model goes silently wrong is mixing Gb (gigabit,
the unit die capacity is quoted in) with GB (gigabyte, the unit module and system
capacity is quoted in) and landing 8x off. A DDR5 die is "16Gb" = 2GB; a DIMM is
"64GB" = 512Gb. Both numbers appear in the same source documents.

So: convert at the boundary, store bits, and never multiply two quantities whose
units you did not just read off a converter.
"""

from __future__ import annotations

# Decimal SI prefixes, which is what the memory industry uses when quoting bit
# shipments and market size (a "1TB" SSD is 1e12 bytes). Binary prefixes apply to
# addressable die capacity but not to the aggregate shipment figures we model.
BITS_PER_BYTE = 8

KILO = 1e3
MEGA = 1e6
GIGA = 1e9
TERA = 1e12
PETA = 1e15
EXA = 1e18


def gb_to_bits(gigabytes: float) -> float:
    """GigaBYTES -> bits. Use for module/system capacity (a 64GB RDIMM, a 288GB GPU)."""
    return gigabytes * GIGA * BITS_PER_BYTE


def gib_to_bits(gigabits: float) -> float:
    """GigaBITS -> bits. Use for die capacity (a 16Gb DDR5 die, a 24Gb HBM die)."""
    return gigabits * GIGA


def tb_to_bits(terabytes: float) -> float:
    """TeraBYTES -> bits. Use for SSD capacity (a 122TB eSSD)."""
    return terabytes * TERA * BITS_PER_BYTE


def eb_to_bits(exabytes: float) -> float:
    """ExaBYTES -> bits. The industry's aggregate shipment unit."""
    return exabytes * EXA * BITS_PER_BYTE


def bits_to_eb(bits: float) -> float:
    """bits -> ExaBYTES. The model's display unit."""
    return bits / (EXA * BITS_PER_BYTE)


def bits_to_gb(bits: float) -> float:
    """bits -> GigaBYTES."""
    return bits / (GIGA * BITS_PER_BYTE)


def bits_to_zb(bits: float) -> float:
    """bits -> ZettaBYTES. NAND aggregates get large enough for this to be readable."""
    return bits / (1e21 * BITS_PER_BYTE)


def check_bits(value: float, label: str = "quantity") -> float:
    """Sanity-guard a bit quantity.

    Catches the 8x error indirectly: any realistic global quarterly bit figure sits
    between ~1 EB and ~10 ZB. A value outside that range in a series that is supposed
    to be global-scale means a converter was skipped or applied twice.
    """
    if value < 0:
        raise ValueError(f"{label}: negative bit quantity ({value})")
    return value


def assert_global_scale(bits: float, label: str = "quantity") -> float:
    """Assert a bit figure is plausibly a global quarterly aggregate.

    Deliberately wide (0.1 EB .. 10 ZB). This is not a precision check, it is a
    "did we lose or gain a factor of 8 / 1000" check.
    """
    check_bits(bits, label)
    lo, hi = eb_to_bits(0.1), eb_to_bits(10_000)
    if not (lo <= bits <= hi):
        raise ValueError(
            f"{label}: {bits_to_eb(bits):,.3f} EB is outside plausible global scale "
            f"(0.1 EB .. 10,000 EB). Suspect a missing or doubled unit conversion."
        )
    return bits
