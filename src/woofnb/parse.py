from __future__ import annotations

from collections import OrderedDict
from typing import Tuple

from .model import Cell, Notebook

MAGIC_PREFIX = "%WOOFNB "


def _parse_cell_header_tokens(s: str) -> OrderedDict[str, str]:
    """Parse space-separated key=value tokens with quoted values and escapes.

    Example: 'id=train type=code name="train model" deps=a,b timeout=30'
    Returns an OrderedDict preserving token order.
    """
    i = 0
    n = len(s)
    out: OrderedDict[str, str] = OrderedDict()

    def skip_ws(j: int) -> int:
        while j < n and s[j].isspace():
            j += 1
        return j

    while True:
        i = skip_ws(i)
        if i >= n:
            break
        # key
        k_start = i
        while i < n and s[i] not in "= \t\r\n":
            i += 1
        key = s[k_start:i]
        if i >= n or s[i] != "=":
            # Malformed; treat rest as value-less flag
            out[key] = ""
            break
        i += 1  # skip '='
        i = skip_ws(i)
        # value
        if i < n and s[i] == '"':
            i += 1
            buf = []
            while i < n:
                ch = s[i]
                if ch == '\\':
                    if i + 1 < n and s[i + 1] == '"':
                        buf.append('"')
                        i += 2
                        continue
                if ch == '"':
                    i += 1
                    break
                buf.append(ch)
                i += 1
            value = "".join(buf)
        else:
            v_start = i
            while i < n and not s[i].isspace():
                i += 1
            value = s[v_start:i]
        out[key] = value
    return out


def _expect_magic_and_header(text: str) -> Tuple[str, str, int]:
    """Return (magic_version, header_text, index_of_next_line)."""
    lines = text.splitlines()
    if not lines:
        raise ValueError("Empty file: missing magic header line")
    # Find first non-empty line for magic
    idx = 0
    while idx < len(lines) and lines[idx].strip() == "":
        idx += 1
    if idx >= len(lines) or not lines[idx].startswith(MAGIC_PREFIX):
        raise ValueError("Missing or invalid magic header line '%WOOFNB x.y'")
    magic_line = lines[idx].strip()
    magic_version = magic_line[len("%"):].strip()  # e.g., 'WOOFNB 1.0'
    # Header continues until first cell fence line starting with ```cell
    header_parts = [lines[idx]]
    idx += 1
    while idx < len(lines):
        if lines[idx].lstrip().startswith("```cell"):
            break
        header_parts.append(lines[idx])
        idx += 1
    header_text = "\n".join(header_parts).rstrip("\n") + "\n"
    # Return next line index to continue scanning cells
    return magic_version, header_text, idx


def parse_text(text: str, path: str | None = None) -> Notebook:
    magic_version, header_text, idx = _expect_magic_and_header(text)
    lines = text.splitlines()
    cells: list[Cell] = []

    while idx < len(lines):
        line = lines[idx]
        if not line.lstrip().startswith("```cell"):
            idx += 1
            continue
        # Extract token string after '```cell'
        after = line.lstrip()[len("```cell"):].strip()
        tokens = _parse_cell_header_tokens(after)
        cell_id = tokens.get("id") or ""
        cell_type = tokens.get("type") or "raw"
        # Collect body until closing fence line '```'
        idx += 1
        body_lines: list[str] = []
        while idx < len(lines) and lines[idx].strip() != "```":
            body_lines.append(lines[idx])
            idx += 1
        body = "\n".join(body_lines).rstrip("\n")
        # Skip closing fence if present
        if idx < len(lines) and lines[idx].strip() == "```":
            idx += 1
        cells.append(Cell(id=cell_id, type=cell_type, body=body, header_tokens=tokens))

    return Notebook(header_text=header_text, cells=cells, magic_version=magic_version, path=path)


def parse_file(path: str) -> Notebook:
    with open(path, "r", encoding="utf-8") as f:
        return parse_text(f.read(), path=path)

