from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, OrderedDict as TOrderedDict


@dataclass
class Cell:
    """A single cell block in a WOOF notebook.

    header_tokens: all key=value tokens from the cell header line.
    Required: id, type
    Body: raw text between opening and closing fences (no trailing fence).
    """

    id: str
    type: str
    body: str
    header_tokens: TOrderedDict[str, str] = field(default_factory=dict)


@dataclass
class Notebook:
    """A parsed WOOF notebook.

    header_text: verbatim YAML header text starting with %WOOFNB line.
    cells: ordered list of Cell in file order.
    magic_version: parsed from the magic line (e.g., "WOOFNB 1.0").
    path: optional file path origin.
    """

    header_text: str
    cells: List[Cell]
    magic_version: str = "WOOFNB 1.0"
    path: Optional[str] = None

    def cell_by_id(self) -> Dict[str, Cell]:
        return {c.id: c for c in self.cells}

