"""Table input and output driven by the schema.

Reading uses ``dbfread`` for DBF files and ``pandas`` for CSV, so
the same generator can run against either format. Writing produces
DBF, CSV and pickle side by side.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd


class TableError(RuntimeError):
    """Raised when a table cannot be read or written."""


def read_table(path: str | Path, fmt: str = "dbf",
               encoding: str = "latin1") -> pd.DataFrame:
    """Read one table into a DataFrame."""
    table_path = Path(path).expanduser()
    if not table_path.is_file():
        raise TableError(f"table not found: {table_path}")

    try:
        if fmt == "dbf":
            from dbfread import DBF

            return pd.DataFrame(
                iter(DBF(str(table_path), encoding=encoding))
            )
        if fmt == "csv":
            return pd.read_csv(table_path, encoding=encoding)
    except Exception as exc:  # noqa: BLE001
        raise TableError(
            f"cannot read {table_path} as {fmt}: {exc}"
        ) from exc

    raise TableError(f"unsupported format: {fmt!r}")


def read_tables(specs: Dict[str, Dict], base: Path) -> Dict[str, pd.DataFrame]:
    """Read every table declared in the schema."""
    frames: Dict[str, pd.DataFrame] = {}
    for name, spec in specs.items():
        raw = Path(spec["path"])
        path = raw if raw.is_absolute() else base / raw
        frames[name] = read_table(
            path,
            fmt=spec.get("format", "dbf"),
            encoding=spec.get("encoding", "latin1"),
        )
    return frames


def require_columns(frame: pd.DataFrame, columns, table_name: str) -> None:
    """Fail early with a readable message when a column is absent."""
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise TableError(
            f"table {table_name!r} is missing column(s): "
            + ", ".join(missing)
        )


def write_table(
    frame: pd.DataFrame,
    directory: Path,
    name: str,
    formats=("csv", "pickle", "dbf"),
    encoding: str = "latin1",
    field_type: str = "C(64)",
) -> Dict[str, Path]:
    """Write one relation table in every requested format."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written: Dict[str, Path] = {}

    if "csv" in formats:
        target = directory / f"{name}.csv"
        frame.to_csv(target, index=False, encoding=encoding)
        written["csv"] = target

    if "pickle" in formats:
        target = directory / f"{name}.pkl"
        frame.to_pickle(target)
        written["pickle"] = target

    if "dbf" in formats:
        target = directory / f"{name}.DBF"
        _write_dbf(frame, target, field_type)
        written["dbf"] = target

    return written


def _write_dbf(frame: pd.DataFrame, target: Path,
               field_type: str) -> None:
    """Write a DBF table, replacing any previous file."""
    try:
        import dbf
    except ImportError as exc:  # pragma: no cover
        raise TableError(
            "the 'dbf' package is required to write DBF tables"
        ) from exc

    if target.exists():
        target.unlink()

    definition = "; ".join(f"{col} {field_type}" for col in frame.columns)
    table = dbf.Table(str(target), definition)
    table.open(mode=dbf.READ_WRITE)
    try:
        for _, row in frame.iterrows():
            table.append(tuple("" if pd.isna(v) else str(v) for v in row))
    finally:
        table.close()
