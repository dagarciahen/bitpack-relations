"""Discovery of the target files from a plain text project file.

The project file is a small key/value text file. It lists how many
stations there are and where each station project lives. Every
station project in turn points at its own data catalog.

This module only knows about the *keys*, which come from the
schema, so a different project format needs no code change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from .config import Schema


class ProjectError(RuntimeError):
    """Raised when the project file cannot be understood."""


def _read_text(path: Path) -> str:
    """Read a legacy text file, trying the usual codepages."""
    for encoding in ("utf-8", "latin1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
        except OSError as exc:
            raise ProjectError(f"cannot read {path}: {exc}") from exc
    raise ProjectError(f"cannot decode {path}")


def _lookup(text: str, key: str) -> str | None:
    """Return the value of ``key = value`` or None."""
    match = re.search(
        rf"^\s*{re.escape(key)}\s*=\s*(.+?)\s*$", text, re.MULTILINE
    )
    return match.group(1) if match else None


@dataclass(frozen=True)
class Station:
    """One station of the project."""

    name: str
    project_path: Path
    station_id: str | None
    catalog_path: Path | None

    @property
    def ready(self) -> bool:
        return bool(self.station_id and self.catalog_path)


class ProjectLayout:
    """Stations and shared tables declared by the project file."""

    def __init__(self, stations: List[Station]) -> None:
        self.stations = stations

    @classmethod
    def discover(cls, project_file: str | Path,
                 schema: Schema) -> "ProjectLayout":
        """Read the project file and resolve every station."""
        path = Path(project_file).expanduser()
        if not path.is_file():
            raise ProjectError(f"project file not found: {path}")

        text = _read_text(path)
        spec = schema.project

        count_key = spec["station_count_key"]
        raw_count = _lookup(text, count_key)
        if raw_count is None:
            raise ProjectError(
                f"key {count_key!r} not found in {path}"
            )

        try:
            total = int(raw_count)
        except ValueError as exc:
            raise ProjectError(
                f"key {count_key!r} is not a number: {raw_count!r}"
            ) from exc

        template = spec["station_key_template"]
        stations: List[Station] = []

        for number in range(1, total + 1):
            key = template.format(n=number)
            raw_path = _lookup(text, key)
            if not raw_path:
                continue

            station_path = Path(raw_path)
            station_id, catalog = _describe_station(
                station_path, schema
            )
            stations.append(
                Station(
                    name=key,
                    project_path=station_path,
                    station_id=station_id,
                    catalog_path=catalog,
                )
            )

        if not stations:
            raise ProjectError(
                f"no station entries found in {path}"
            )

        return cls(stations)

    def __len__(self) -> int:
        return len(self.stations)

    def __iter__(self):
        return iter(self.stations)

    @property
    def ready(self) -> List[Station]:
        """Stations with both an id and a data catalog."""
        return [s for s in self.stations if s.ready]

    def as_dict(self) -> Dict[str, Dict[str, str]]:
        """Serialisable view, handy for debugging and tests."""
        return {
            station.name: {
                "PROJECT_PATH": str(station.project_path),
                "STATION_ID": station.station_id or "",
                "CATALOG_PATH": str(station.catalog_path or ""),
            }
            for station in self.stations
        }


def _describe_station(station_path: Path,
                      schema: Schema) -> tuple[str | None, Path | None]:
    """Extract the station id and locate its data catalog."""
    if not station_path.is_file():
        return None, None

    text = _read_text(station_path)
    spec = schema.project

    station_id = _lookup(text, spec["station_id_key"])

    catalog: Path | None = None
    raw_catalog = _lookup(text, spec.get("catalog_file_key", ""))
    if raw_catalog:
        candidate = Path(raw_catalog)
        if candidate.is_file():
            catalog = candidate
        elif candidate.is_dir():
            candidate = candidate / spec["catalog_file_name"]
            if candidate.is_file():
                catalog = candidate

    if catalog is None:
        candidate = (
            station_path.parent
            / spec.get("catalog_dir", "")
            / spec["catalog_file_name"]
        )
        if candidate.is_file():
            catalog = candidate

    return station_id, catalog
