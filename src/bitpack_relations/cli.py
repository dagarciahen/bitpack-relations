"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import Schema, SchemaError
from .nsproject import ProjectError, ProjectLayout


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bitpack-relations",
        description=(
            "Generate the relation tables from a declarative schema."
        ),
    )
    parser.add_argument(
        "--schema",
        default="config/schema.json",
        help="path to the schema file (default: %(default)s)",
    )
    parser.add_argument(
        "--project",
        help="path to the project file listing the stations",
    )
    parser.add_argument(
        "--index",
        type=int,
        help="value of the first exchange index",
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="only list the discovered stations and exit",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        schema = Schema.load(args.schema)
    except SchemaError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.inspect:
        return _inspect(schema, args.project)

    if not args.project:
        print(
            "error: --project is required to generate tables",
            file=sys.stderr,
        )
        return 2

    from .pipeline import Pipeline

    try:
        result = Pipeline(schema).run(args.project, args.index)
    except (ProjectError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(result.summary())
    return 0


def _inspect(schema: Schema, project: str | None) -> int:
    if not project:
        print(
            "error: --inspect needs --project as well",
            file=sys.stderr,
        )
        return 2

    try:
        layout = ProjectLayout.discover(project, schema)
    except ProjectError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"{len(layout)} station(s) found in {project}")
    for station in layout:
        state = "ok" if station.ready else "incomplete"
        print(f"  {station.name:<8} {state:<10} {station.station_id}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
