"""Build the TX relation, the transmission side of the exchange.

Each row pairs a device of a station with a signal declared in the
mapping template. After the rows are built they are sorted by
station and device group, then the bit packer assigns every row its
byte and bit address.
"""

from __future__ import annotations

from typing import Callable, Iterable, List

import pandas as pd

from .bitpack import BitPackConfig, pack
from .config import Schema
from .tables import TableError

PromptCallback = Callable[[str], int | None]


def type_lookup(device_types: pd.DataFrame,
                schema: Schema) -> dict:
    """Map the numeric type code to its group name."""
    code = schema.column("type_code")
    name = schema.column("type_name")

    if code not in device_types.columns:
        raise TableError(f"{code!r} missing from the device types")
    if name not in device_types.columns:
        raise TableError(f"{name!r} missing from the device types")

    return dict(zip(device_types[code], device_types[name]))


def build_rows(
    catalog: pd.DataFrame,
    mapping: pd.DataFrame,
    device_types: pd.DataFrame,
    station_id: str,
    schema: Schema,
    start_index: int,
) -> List[dict]:
    """Cross a station catalog with the mapping template."""
    groups = type_lookup(device_types, schema)

    type_code = schema.column("type_code")
    group_col = schema.column("device_type")
    device_col = schema.column("device_code")
    signal_col = schema.column("signal_code")
    desc_col = schema.column("description")
    index_col = schema.column("index")

    for frame, label, column in (
        (catalog, "catalog", type_code),
        (mapping, "mapping", type_code),
        (catalog, "catalog", device_col),
        (mapping, "mapping", signal_col),
    ):
        if column not in frame.columns:
            raise TableError(f"{column!r} missing from {label}")

    rows: List[dict] = []

    for code, group_name in groups.items():
        devices = catalog[catalog[type_code] == code]
        signals = mapping[mapping[type_code] == code]

        for _, device in devices.iterrows():
            for _, signal in signals.iterrows():
                rows.append(
                    {
                        index_col: start_index,
                        schema.column("offset_byte"): 0,
                        schema.column("offset_bit"): 0,
                        schema.column("width_bits"): 0,
                        schema.column("station_id"): station_id,
                        group_col: group_name,
                        device_col: device[device_col],
                        signal_col: signal[signal_col],
                        desc_col: signal.get(desc_col, ""),
                    }
                )

    return rows


def order_key(schema: Schema, groups: Iterable[str]) -> list:
    """Build the categorical order for the device group column."""
    order = list(schema.group_order("tx"))
    extra = [g for g in groups if g not in order]
    return order + sorted(set(extra))


def sort_rows(frame: pd.DataFrame, schema: Schema) -> pd.DataFrame:
    """Sort by station, then by the configured group order."""
    group_col = schema.column("device_type")
    station_col = schema.column("station_id")

    ordered = pd.Categorical(
        frame[group_col],
        categories=order_key(schema, frame[group_col].unique()),
        ordered=True,
    )

    result = frame.assign(**{group_col: ordered})
    result = result.sort_values(by=[station_col, group_col])
    return result.reset_index(drop=True)


def assign_bitpack(
    frame: pd.DataFrame,
    schema: Schema,
    start_index: int,
    config: BitPackConfig | None = None,
) -> tuple[pd.DataFrame, int]:
    """Write the byte, bit and width of every row."""
    cfg = config or schema.bitpack
    index_col = schema.column("index")
    byte_col = schema.column("offset_byte")
    bit_col = schema.column("offset_bit")
    width_col = schema.column("width_bits")

    widths = [
        0 if pd.isna(w) else int(w)
        for w in frame.get(width_col, pd.Series(dtype=int))
    ]

    placements = pack(widths, cfg)

    result = frame.copy()
    result[byte_col] = [p.byte for p in placements]
    result[bit_col] = [p.bit for p in placements]
    result[width_col] = [p.width for p in placements]
    result[index_col] = [p.index for p in placements]

    return result, start_index


def apply_prompts(
    frame: pd.DataFrame,
    schema: Schema,
    prompt: PromptCallback | None,
    start_index: int,
) -> pd.DataFrame:
    """Ask the operator for the index of the configured groups."""
    if prompt is None:
        return frame

    index_col = schema.column("index")
    group_col = schema.column("device_type")
    result = frame.copy()

    for group in schema.prompt_groups("tx"):
        if group not in set(result[group_col]):
            continue
        value = prompt(group)
        if value is None:
            continue
        result.loc[result[group_col] == group, index_col] = value

    return result
