"""Build the RX and VALRX relations, the reception side.

The reception side mirrors the transmission side: the same rows,
with the renames declared in the schema applied. A rename is a
plain pair of signal names, so the mapping stays visible in the
config file instead of being buried in the code.
"""

from __future__ import annotations

from typing import Any, Dict

import pandas as pd

from .config import Schema
from .tables import TableError


def rename_rules(schema: Schema) -> list:
    """Renames declared for the reception side."""
    section = schema.generation.get("rx", {})
    rules = section.get("renames", [])
    if not isinstance(rules, list):
        raise TableError("'generation.rx.renames' must be a list")
    return rules


def apply_renames(frame: pd.DataFrame, schema: Schema) -> pd.DataFrame:
    """Apply every rename of the schema to a copy of the frame."""
    signal_col = schema.column("signal_code")
    desc_col = schema.column("description")

    if signal_col not in frame.columns:
        raise TableError(
            f"{signal_col!r} missing, cannot build the RX side"
        )

    result = frame.copy()

    for rule in rename_rules(schema):
        source = rule.get("from")
        target = rule.get("to")
        if not source or not target:
            raise TableError(
                "each rename needs a 'from' and a 'to' value"
            )

        mask = result[signal_col] == source
        if not mask.any():
            continue

        result.loc[mask, signal_col] = target

        if rule.get("description") and desc_col in result.columns:
            result.loc[mask, desc_col] = rule["description"]

    return result


def describe(schema: Schema) -> Dict[str, Any]:
    """Summary of the applied renames, used by the report."""
    return {
        "renames": [
            {
                "from": rule.get("from"),
                "to": rule.get("to"),
                "applied": True,
            }
            for rule in rename_rules(schema)
        ]
    }
