"""Generate relation tables from a declarative schema."""

from .config import Schema, SchemaError
from .bitpack import BitPackConfig, BitPackError, Placement, pack

__version__ = "0.1.0"

__all__ = [
    "Schema",
    "SchemaError",
    "BitPackConfig",
    "BitPackError",
    "Placement",
    "pack",
    "__version__",
]
