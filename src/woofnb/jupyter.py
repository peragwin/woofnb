from __future__ import annotations

import json
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple

from ruamel.yaml import YAML
import nbformat

from .model import Cell, Notebook


def _parse_header_yaml(header_text: str) -> Dict:
    """Best-effort parse of YAML header (lines after the magic).

    Returns a plain dict, or {} if parsing fails.
    """
    try:
        lines = header_text.splitlines()
        # Drop the first line which contains the magic
        yaml_text = "\n".join(lines[1:])
        yaml = YAML(typ="safe")
        data = yaml.load(yaml_text)
        return data or {}
    except Exception:
        return {}


def _header_language(header_text: str) -> str:
    data = _parse_header_yaml(header_text)
    lang = "python"
    if isinstance(data, dict):
        lang = data.get("language") or lang
    return str(lang)


def _header_name(header_text: str) -> Optional[str]:
    data = _parse_header_yaml(header_text)
    if isinstance(data, dict):
        name = data.get("name")
        if isinstance(name, str) and name.strip():
            return name
    return None


def _cell_tags_from_tokens(tokens: OrderedDict[str, str]) -> List[str]:
    raw = tokens.get("tags") or ""
    if not raw:
        return []
    parts = [t.strip() for t in raw.split(",")]
    return [p for p in parts if p]


def woof_to_ipynb_dict(nb: Notebook) -> Dict:
    """Convert a WOOF Notebook to a minimal Jupyter nbformat v4 dict.

    - Only code cells are emitted as "code"; others become "raw" or "markdown".
    - Tags from the 'tags' header token are mapped to Jupyter cell.metadata.tags.
    - IDs are preserved if present; also stored in cell.metadata["woofnb"]["id"].
    """
    language = _header_language(nb.header_text)
    name = _header_name(nb.header_text)

    def _cell_to_nb(c: Cell) -> Dict:
        j_meta: Dict = {"woofnb": {"id": c.id, "type": c.type}}
        tags = _cell_tags_from_tokens(c.header_tokens)
        if tags:
            j_meta["tags"] = tags
        # Choose Jupyter cell type
        if c.type in {"md", "markdown"}:
            return {
                "cell_type": "markdown",
                "id": c.id,
                "source": (
                    c.body
                    if c.body.endswith("\n")
                    else (c.body + "\n" if c.body else "")
                ),
                "metadata": j_meta,
            }
        elif c.type == "code":
            return {
                "cell_type": "code",
                "id": c.id,
                "source": (
                    c.body
                    if c.body.endswith("\n")
                    else (c.body + "\n" if c.body else "")
                ),
                "outputs": [],
                "execution_count": None,
                "metadata": j_meta,
            }
        else:
            # Unknown/woof-specific types mapped to raw to preserve content safely
            j_meta["woofnb"]["mapped_from_type"] = c.type
            return {
                "cell_type": "raw",
                "id": c.id,
                "source": (
                    c.body
                    if c.body.endswith("\n")
                    else (c.body + "\n" if c.body else "")
                ),
                "metadata": j_meta,
            }

    nb_dict = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "name": language,
                "display_name": name or language,
                "language": language,
            },
            "language_info": {"name": language},
            "woofnb": {"magic_version": nb.magic_version},
        },
        "cells": [_cell_to_nb(c) for c in nb.cells],
    }
    return nb_dict


def ipynb_dict_to_woof(d: Dict, *, path: Optional[str] = None) -> Notebook:
    """Convert a Jupyter nbformat v4 dict to a WOOF Notebook.

    - Jupyter 'markdown' -> WOOF 'md'
    - Jupyter 'code' -> WOOF 'code'
    - Jupyter 'raw' -> WOOF 'raw'
    - Unknown types treated as 'raw'
    - IDs preserved if present; otherwise generated as <type><index> in file order
    - Tags in cell.metadata.tags mapped to header token 'tags' as comma-separated
    """
    meta = d.get("metadata", {}) if isinstance(d, dict) else {}
    ks = meta.get("kernelspec", {}) if isinstance(meta, dict) else {}
    language = ks.get("language") or ks.get("name") or "python"
    name = meta.get("woofnb", {}).get("name") or ks.get("display_name")

    header_lines: List[str] = ["%WOOFNB 1.0"]
    if name:
        header_lines.append(f"name: {name}")
    if language:
        header_lines.append(f"language: {language}")
    header_text = "\n".join(header_lines) + "\n"

    # Counters for ids
    counters: Dict[str, int] = {"code": 0, "md": 0, "raw": 0}

    def _gen_id(t: str) -> str:
        counters[t] = counters.get(t, 0) + 1
        return f"{t}{counters[t]}"

    cells_in: List[Dict] = d.get("cells", []) if isinstance(d, dict) else []
    cells: List[Cell] = []

    for jc in cells_in:
        if not isinstance(jc, dict):
            continue
        jtype = str(jc.get("cell_type") or "raw")
        if jtype == "markdown":
            ctype = "md"
        elif jtype == "code":
            ctype = "code"
        else:
            ctype = "raw"
        src = jc.get("source", "")
        if isinstance(src, list):
            body = "".join(src)
        else:
            body = str(src)
        body = body.rstrip("\n")
        jmeta = jc.get("metadata", {})
        if isinstance(jmeta, dict):
            woof_meta = jmeta.get("woofnb", {})
        else:
            woof_meta = {}
        # Preserve ID from Jupyter cell or woofnb metadata; otherwise generate
        cid = (
            jc.get("id")
            or (woof_meta.get("id") if isinstance(woof_meta, dict) else None)
            or _gen_id(ctype)
        )
        # If original woof type stored in metadata, prefer it (restores mapped types)
        if isinstance(woof_meta, dict):
            orig_type = woof_meta.get("type") or woof_meta.get("mapped_from_type")
            if isinstance(orig_type, str) and orig_type.strip():
                ctype = orig_type
        # tokens: id, type, tags if present
        tokens: "OrderedDict[str, str]" = OrderedDict()
        tokens["id"] = str(cid)
        tokens["type"] = ctype
        tags: List[str] = []
        if isinstance(jmeta, dict):
            t = jmeta.get("tags")
            if isinstance(t, list):
                tags = [str(x) for x in t if str(x).strip()]
        if tags:
            tokens["tags"] = ",".join(tags)
        cells.append(Cell(id=str(cid), type=ctype, body=body, header_tokens=tokens))

    return Notebook(
        header_text=header_text, cells=cells, magic_version="WOOFNB 1.0", path=path
    )


def export_ipynb_text(nb: Notebook) -> str:
    d = woof_to_ipynb_dict(nb)
    nbnode = nbformat.from_dict(d)
    s = nbformat.writes(nbnode, version=4)
    if not s.endswith("\n"):
        s += "\n"
    return s


def import_ipynb_text(text: str, *, path: Optional[str] = None) -> Notebook:
    nbnode = nbformat.reads(text, as_version=4)
    return ipynb_dict_to_woof(nbnode, path=path)


def export_file_to_ipynb(in_path: str, out_path: Optional[str] = None) -> None:
    from .parse import parse_file

    nb = parse_file(in_path)
    text = export_ipynb_text(nb)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        # stdout
        print(text, end="")


def import_ipynb_file(in_path: str, out_path: Optional[str] = None) -> None:
    with open(in_path, "r", encoding="utf-8") as f:
        text = f.read()
    nb = import_ipynb_text(text, path=in_path)
    from .serialize import serialize

    out_text = serialize(nb)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(out_text)
    else:
        print(out_text, end="")
