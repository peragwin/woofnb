"""WOOF Notebook (WOOFNB) reference toolkit – early scaffold.

Phases 0–1: models, parser, serializer, basic lint/graph, CLI stubs.
"""

__all__ = [
    "Notebook",
    "Cell",
    "parse_text",
    "parse_file",
    "serialize",
]

__version__ = "0.0.1-dev"

from .model import Notebook, Cell  # noqa: E402
from .parse import parse_text, parse_file  # noqa: E402
from .serialize import serialize  # noqa: E402

