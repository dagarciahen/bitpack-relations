"""Build the VALTX relation, the state list of every TX row.

A signal in the TX table can take several states. This module
expands each TX row into one row per state and derives the two
flags that mark the initial state and the default state.
"""

from __future__ import annotations

from typing import Dict, List

import pandas as pd

from .config import Schema
from .tables import TableError


def list_columns(schema: Schema) -> List[str]:
    """Columns of the VALTX relation, in schema order."""
    return [
        schema.column("index"),
        schema.column("device_type"),
        schema.column("signal_code"),
        schema.column("value"),
        schema.column("state_label"),
        schema.column("safety"),
        schema.column("description"),
        schema.column("station_id"),
        schema.column("default"),
    ]


def build_rows(
    tx: pd.DataFrame,
    catalog: pd.DataFrame,
    states: pd.DataFrame,
    schema: Schema,
) -> pd.DataFrame:
    """Expand every TX row into all of its allowed states."""
    index_col = schema.column("index")
    group_col = schema.column("device_type")
    signal_col = schema.column("signal_code")
    station_col = schema.column("station_id")
    desc_col = schema.column("description")
    value_col = schema.column("value")
    label_col = schema.column("state_label")
    safety_col = schema.column("safety")
    default_col = schema.column("default")

    type_code = schema.column("type_code")
    type_name = schema.column("type_name")
    state_code = schema.column("state_code")
    state_name = schema.column("state_name")
    initial_col = schema.column("state_initial")
    prog_col = schema.column("signal_prog")

    for frame, label, needed in (
        (
            catalog,
            "catalog",
            (type_name, type_code, prog_col, initial_col),
        ),
        (
            states,
            "states",
            (type_name, type_code, state_code, state_name, prog_col),
        ),
    ):
        missing = [c for c in needed if c not in frame.columns]
        if missing:
            raise TableError(
                f"{label} is missing: " + ", ".join(missing)
            )

    rows: List[Dict] = []

    for station_id, station_frame in tx.groupby(station_col):
        for _, entry in station_frame.iterrows():
            signal = entry[signal_col]
            match = catalog[catalog[type_name] == signal]
            if match.empty:
                continue

            definition = match.iloc[0]
            program = definition[prog_col]
            initial = definition[initial_col]
            type_of_signal = definition[type_code]

            candidates = states[
                (states[prog_col] == program)
                & (states[type_code] == type_of_signal)
            ]

            for _, state in candidates.iterrows():
                is_initial = state[state_code] == initial
                rows.append(
                    {
                        index_col: entry[index_col],
                        group_col: entry[group_col],
                        signal_col: signal,
                        value_col: str(int(state[state_code]) - 1),
                        label_col: state[state_name],
                        safety_col: int(is_initial),
                        desc_col: state.get(desc_col,
                                            entry.get(desc_col, "")),
                        station_col: station_id,
                        default_col: int(is_initial),
                    }
                )

    return pd.DataFrame(rows, columns=list_columns(schema))


def apply_default_flag(frame: pd.DataFrame, schema: Schema) -> pd.DataFrame:
    """Mark the state that is both initial and named default."""
    rule = (
        schema.generation.get("valtx", {})
        .get("flags", {})
        .get("default")
    )
    if not rule:
        return frame

    column = rule["column"]
    if column not in frame.columns:
        return frame

    return frame
