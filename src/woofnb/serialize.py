from __future__ import annotations

from collections import OrderedDict
from typing import Iterable

from .model import Notebook

_CANON_KEY_ORDER = [
    "id",
    "type",
    "name",
    "deps",
    "timeout",
    "memory_mb",
    "sidefx",
    "tags",
    "retries",
    "priority",
    "disabled",
    "lang",
]


def _iter_tokens_canonical(tokens: OrderedDict[str, str]) -> Iterable[tuple[str, str]]:
    seen = set()
    for k in _CANON_KEY_ORDER:
        if k in tokens:
            yield k, tokens[k]
            seen.add(k)
    # any remaining keys in original order
    for k, v in tokens.items():
        if k not in seen:
            yield k, v


def serialize(nb: Notebook) -> str:
    parts: list[str] = []
    header = nb.header_text
    if not header.endswith("\n"):
        header += "\n"
    parts.append(header)
    for cell in nb.cells:
        tok_strs = []
        for k, v in _iter_tokens_canonical(cell.header_tokens):
            if any(ch.isspace() for ch in v) or '"' in v:
                vv = '"' + v.replace('"', '\\"') + '"'
            else:
                vv = v
            tok_strs.append(f"{k}={vv}")
        header_line = "```cell " + " ".join(tok_strs)
        parts.append(header_line)
        if cell.body:
            parts.append(cell.body)
        parts.append("```")
        # blank line between cells optional; skip to keep minimal
    return "\n".join(parts).rstrip("\n") + "\n"

