"""Run the whole generation from one schema and one project file."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List

import pandas as pd

from . import rx, tx, valtx
from .config import Schema
from .nsproject import ProjectLayout
from .tables import read_table, read_tables, write_table

PromptCallback = Callable[[str], int | None]


@dataclass
class Result:
    """What a pipeline run produced."""

    frames: Dict[str, pd.DataFrame] = field(default_factory=dict)
    files: Dict[str, Dict[str, Path]] = field(default_factory=dict)
    stations: int = 0
    rows: Dict[str, int] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"stations : {self.stations}",
            f"rows     : "
            + ", ".join(
                f"{k}={v}" for k, v in self.rows.items()
            ),
        ]
        for key, paths in self.files.items():
            for fmt, path in paths.items():
                lines.append(f"{key:<6} {fmt:<7} {path}")
        for message in self.warnings:
            lines.append(f"warning: {message}")
        return "\n".join(lines)


class Pipeline:
    """Drive the schema, the project file and the generators."""

    def __init__(self, schema: Schema,
                 prompt: PromptCallback | None = None) -> None:
        self.schema = schema
        self.prompt = prompt
        self.result = Result()

    def run(self, project_file: str | Path,
            start_index: int | None = None) -> Result:
        """Generate every relation table."""
        layout = ProjectLayout.discover(project_file, self.schema)
        self.result.stations = len(layout)

        shared = read_tables(self.schema.tables, self.schema_base)
        device_types = shared["device_types"]
        mapping = shared["mapping_template"]
        states = shared["signal_states"]

        start = (
            start_index
            if start_index is not None
            else self.schema.bitpack.index_start
        )

        tx_rows: List[dict] = []
        for station in layout:
            if not station.ready:
                self.result.warnings.append(
                    f"{station.name} skipped: no catalog or id"
                )
                continue

            catalog = read_table(
                station.catalog_path,
                fmt="dbf",
                encoding=self.schema.tables["signal_catalog"].get(
                    "encoding", "latin1"
                ),
            )
            tx_rows.extend(
                tx.build_rows(
                    catalog,
                    mapping,
                    device_types,
                    station.station_id or "",
                    self.schema,
                    start,
                )
            )

        frame = pd.DataFrame(tx_rows)
        if frame.empty:
            raise RuntimeError(
                "no TX rows were produced, check the input tables"
            )

        frame = tx.sort_rows(frame, self.schema)
        frame = tx.apply_prompts(
            frame, self.schema, self.prompt, start
        )
        frame, _ = tx.assign_bitpack(frame, self.schema, start)

        self._store("tx", frame)

        valtx_frame = valtx.build_rows(
            frame,
            shared["signal_catalog"],
            states,
            self.schema,
        )
        valtx_frame = valtx.apply_default_flag(
            valtx_frame, self.schema
        )
        self._store("valtx", valtx_frame)

        rx_frame = rx.apply_renames(frame, self.schema)
        self._store("rx", rx_frame)

        valrx_frame = rx.apply_renames(valtx_frame, self.schema)
        self._store("valrx", valrx_frame)

        self._write_all()
        return self.result

    @property
    def schema_base(self) -> Path:
        """Directory the schema paths are relative to."""
        return self.schema.path.parent.parent

    def _store(self, key: str, frame: pd.DataFrame) -> None:
        self.result.frames[key] = frame
        self.result.rows[key] = len(frame)

    def _write_all(self) -> None:
        outputs = self.schema.outputs
        directory = self.schema.path.parent.parent / outputs.get(
            "directory", "out"
        )

        for key, frame in self.result.frames.items():
            self.result.files[key] = write_table(
                frame,
                directory,
                outputs["tables"][key],
                formats=tuple(outputs.get("formats", ["csv"])),
                encoding=outputs.get("encoding", "latin1"),
                field_type=outputs.get("dbf_field_type", "C(64)"),
            )
