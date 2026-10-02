"""Load and validate the declarative schema.

The schema is the single place where table names, column names and
generation rules live. Nothing in the generation code hardcodes a
field name, so the same code can drive a different naming
convention by swapping the JSON file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .bitpack import BitPackConfig

REQUIRED_SECTIONS = (
    "columns",
    "bitpacking",
    "project",
    "tables",
    "generation",
    "outputs",
)

REQUIRED_COLUMNS = (
    "index",
    "offset_byte",
    "offset_bit",
    "width_bits",
    "station_id",
    "device_type",
    "device_code",
    "signal_code",
    "description",
    "type_code",
    "type_name",
    "state_code",
    "state_name",
    "state_initial",
    "value",
    "state_label",
)


class SchemaError(ValueError):
    """Raised when the schema is missing or inconsistent."""


class Schema:
    """Read only view over the schema document."""

    def __init__(self, document: Dict[str, Any], path: Path) -> None:
        self._doc = document
        self.path = path
        self.bitpack = BitPackConfig.from_dict(
            document.get("bitpacking", {})
        )

    @classmethod
    def load(cls, path: str | Path) -> "Schema":
        """Read a schema file from disk and validate it."""
        schema_path = Path(path).expanduser()
        if not schema_path.is_file():
            raise SchemaError(f"schema not found: {schema_path}")

        try:
            document = json.loads(
                schema_path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as exc:
            raise SchemaError(
                f"{schema_path} is not valid JSON: {exc}"
            ) from exc

        cls._validate(document)
        return cls(document, schema_path)

    @staticmethod
    def _validate(document: Dict[str, Any]) -> None:
        if not isinstance(document, dict):
            raise SchemaError("schema root must be an object")

        missing = [s for s in REQUIRED_SECTIONS if s not in document]
        if missing:
            raise SchemaError(
                "schema is missing section(s): " + ", ".join(missing)
            )

        columns = document["columns"]
        if not isinstance(columns, dict):
            raise SchemaError("'columns' must be an object")

        absent = [
            key
            for key in REQUIRED_COLUMNS
            if not columns.get(key)
        ]
        if absent:
            raise SchemaError(
                "column mapping is missing: " + ", ".join(absent)
            )

        tables = document["tables"]
        if not isinstance(tables, dict) or not tables:
            raise SchemaError("'tables' must not be empty")

        for name, spec in tables.items():
            if "path" not in spec:
                raise SchemaError(
                    f"table {name!r} has no 'path' entry"
                )
            if spec.get("format", "dbf") not in ("dbf", "csv"):
                raise SchemaError(
                    f"table {name!r} has an unsupported format"
                )

        outputs = document["outputs"]
        if "tables" not in outputs:
            raise SchemaError("'outputs.tables' is required")

        for key in ("tx", "valtx", "rx", "valrx"):
            if key not in outputs["tables"]:
                raise SchemaError(
                    f"'outputs.tables' is missing {key!r}"
                )


    def column(self, logical_name: str) -> str:
        """Physical column name for a logical role."""
        try:
            return self._doc["columns"][logical_name]
        except KeyError as exc:
            raise SchemaError(
                f"unknown logical column: {logical_name!r}"
            ) from exc

    def has_column(self, logical_name: str) -> bool:
        return logical_name in self._doc["columns"]


    @property
    def project(self) -> Dict[str, Any]:
        return self._doc["project"]

    @property
    def tables(self) -> Dict[str, Any]:
        return self._doc["tables"]

    @property
    def generation(self) -> Dict[str, Any]:
        return self._doc["generation"]

    @property
    def outputs(self) -> Dict[str, Any]:
        return self._doc["outputs"]

    def table_path(self, name: str, base: Path | None = None) -> Path:
        """Resolve a table path, relative to the schema file."""
        spec = self.tables.get(name)
        if spec is None:
            raise SchemaError(f"unknown table: {name!r}")

        raw = Path(spec["path"])
        if raw.is_absolute():
            return raw

        root = base or self.path.parent.parent
        return (root / raw).resolve()

    def output_path(self, table_key: str, suffix: str,
                    base: Path | None = None) -> Path:
        """Resolve an output file next to the output directory."""
        name = self.outputs["tables"][table_key]
        root = base or self.path.parent.parent
        folder = Path(self.outputs.get("directory", "out"))
        if not folder.is_absolute():
            folder = root / folder
        return folder / f"{name}.{suffix}"

    def group_order(self, kind: str) -> List[str]:
        """Configured ordering of device groups."""
        section = self.generation.get("tx", {})
        return list(section.get("group_order", []))

    def prompt_groups(self, kind: str = "tx") -> List[str]:
        """Groups whose index value the operator must type in."""
        section = self.generation.get(kind, {})
        return list(section.get("prompt_groups", []))
