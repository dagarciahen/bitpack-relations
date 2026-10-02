"""Bit packing of variable width fields into a byte buffer.

Every field occupies a whole number of bits. Fields are packed one
after another; when a field does not fit in the bits left inside
the current byte it moves to the top of the next byte. The result
is a memory map that the field equipment can read directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator, List, Sequence


class BitPackError(ValueError):
    """Raised when a field cannot be placed in the buffer."""


@dataclass(frozen=True)
class BitPackConfig:
    """Layout rules for the buffer."""

    index_start: int = 1
    index_step: int = 1
    byte_start: int = 2
    bits_per_byte: int = 8
    byte_limit: int = 1024
    fill_order: str = "msb_first"
    rollover: str = "keep"

    def __post_init__(self) -> None:
        if self.bits_per_byte < 1:
            raise BitPackError("bits_per_byte must be positive")
        if self.byte_start < 0:
            raise BitPackError("byte_start cannot be negative")
        if self.byte_limit < self.byte_start:
            raise BitPackError("byte_limit must be >= byte_start")
        if self.fill_order not in ("msb_first", "lsb_first"):
            raise BitPackError(
                f"unknown fill_order: {self.fill_order!r}"
            )
        if self.rollover not in ("keep", "restart", "reject"):
            raise BitPackError(
                f"unknown rollover policy: {self.rollover!r}"
            )

    @classmethod
    def from_dict(cls, data: dict) -> "BitPackConfig":
        """Build a config from the ``bitpacking`` schema section."""
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass(frozen=True)
class Placement:
    """Where a single field ended up in the buffer."""

    index: int
    byte: int
    bit: int
    width: int

    def mask(self, bits_per_byte: int = 8) -> str:
        """Render the byte as text, MSB on the left.

        Occupied bits are shown as ``X`` and free bits as ``-``.
        """
        occupied = range(self.bit, self.bit + self.width)
        cells = [
            "X" if i in occupied else "-"
            for i in range(bits_per_byte)
        ]
        return "".join(reversed(cells)) if bits_per_byte else ""


def pack(
    widths: Iterable[int],
    config: BitPackConfig | None = None,
) -> List[Placement]:
    """Place every field and return one placement per field.

    ``widths`` are the field sizes in bits, in the order the fields
    must be written to the buffer.
    """
    cfg = config or BitPackConfig()
    span = cfg.bits_per_byte

    index = cfg.index_start
    byte = cfg.byte_start
    free = span
    cursor = span
    placements: List[Placement] = []

    for width in widths:
        if width < 0:
            raise BitPackError(f"negative width: {width}")
        if width > span:
            raise BitPackError(
                f"width {width} exceeds bits_per_byte {span}"
            )

        if width <= free:
            cursor -= width
            free = cursor
        else:
            cursor = span - width
            byte += 1
            free = cursor

        if byte > cfg.byte_limit:
            index, byte, free, cursor = _rollover(
                cfg, index, span
            )

        placements.append(
            Placement(index=index, byte=byte, bit=cursor, width=width)
        )

    return placements


def _rollover(
    cfg: BitPackConfig,
    index: int,
    span: int,
) -> tuple[int, int, int, int]:
    """Apply the configured policy once the limit is crossed."""
    if cfg.rollover == "reject":
        raise BitPackError(
            f"layout crosses byte_limit {cfg.byte_limit}"
        )

    next_index = index + cfg.index_step

    if cfg.rollover == "restart":
        return next_index, cfg.byte_start, span, span

    return next_index, cfg.byte_limit, span, span


def iter_rows(
    widths: Sequence[int],
    config: BitPackConfig | None = None,
) -> Iterator[tuple[int, int, int, int]]:
    """Yield ``(index, byte, bit, width)`` tuples for each field."""
    for item in pack(widths, config):
        yield item.index, item.byte, item.bit, item.width


def render(widths: Iterable[int], config: BitPackConfig | None = None) -> str:
    """Draw the buffer layout, useful for docs and tests."""
    cfg = config or BitPackConfig()
    lines = []
    for item in pack(widths, cfg):
        lines.append(
            f"byte {item.byte:<5} bit {item.bit} "
            f"len {item.width:<2} {item.mask(cfg.bits_per_byte)}"
        )
    return "\n".join(lines)
