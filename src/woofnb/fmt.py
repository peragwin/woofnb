from __future__ import annotations

from io import StringIO
from typing import Iterable

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from .parse import parse_text
from .serialize import serialize

_HEADER_KEY_ORDER: list[str] = [
    "name",
    "language",
    "env",
    "parameters",
    "defaults",
    "execution",
    "io_policy",
    "provenance",
    "metadata",
    "tags",
    "version",
]


def _reorder_mapping(m: CommentedMap, order: Iterable[str]) -> CommentedMap:
    # Keep existing items, move known keys first in the given order, then others in original order
    known = [k for k in order if k in m]
    others = [k for k in m.keys() if k not in known]
    new = CommentedMap()
    for k in known + others:
        new[k] = m[k]
        # move associated comments
        if m.ca.items and k in m.ca.items:
            new.ca.items[k] = m.ca.items[k]
    # Preserve end-of-map comments
    new.ca.comment = m.ca.comment
    return new


def format_header_text(header_text: str) -> str:
    lines = header_text.splitlines()
    # Keep all leading blank lines before magic, but typical files start with magic on first line
    idx = 0
    while idx < len(lines) and lines[idx].strip() == "":
        idx += 1
    if idx >= len(lines) or not lines[idx].startswith("%WOOFNB "):
        return header_text  # unchanged if not valid
    magic = lines[idx].strip()
    yaml_lines = lines[idx + 1 :]
    yaml_str = "\n".join(yaml_lines).rstrip("\n") + ("\n" if yaml_lines else "")

    if not yaml_str.strip():
        # No YAML body; just return magic
        return magic + "\n"

    yaml = YAML()
    yaml.preserve_quotes = True
    data = yaml.load(StringIO(yaml_str))
    if not isinstance(data, CommentedMap):
        # Non-mapping header; emit as-is
        return magic + "\n" + yaml_str

    data = _reorder_mapping(data, _HEADER_KEY_ORDER)

    out = StringIO()
    yaml.dump(data, out)
    rendered = out.getvalue()
    if not rendered.endswith("\n"):
        rendered += "\n"
    return magic + "\n" + rendered


def format_text(text: str) -> str:
    nb = parse_text(text)
    nb.header_text = format_header_text(nb.header_text)
    return serialize(nb)

