"""Draw the packing layout, useful while tuning a schema.

Run it with a handful of field widths to see where each field lands:

    python -m bitpack_relations.diagram 3 3 4 2 8
"""

from __future__ import annotations

import sys

from .bitpack import BitPackConfig, render


def main(argv: list[str] | None = None) -> int:
    values = argv if argv is not None else sys.argv[1:]
    try:
        widths = [int(v) for v in values]
    except ValueError:
        print("usage: diagram <width> [<width> ...]", file=sys.stderr)
        return 2

    if not widths:
        widths = [3, 3, 4, 2, 8]

    print(f"fields with width {widths}")
    print(render(widths, BitPackConfig()))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
