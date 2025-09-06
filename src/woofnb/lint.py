from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from .model import Notebook


@dataclass
class LintIssue:
    level: str  # "ERROR" | "WARN"
    message: str


def lint_notebook(nb: Notebook) -> Tuple[List[LintIssue], List[LintIssue]]:
    errors: List[LintIssue] = []
    warns: List[LintIssue] = []

    if not nb.magic_version.startswith("WOOFNB "):
        errors.append(LintIssue("ERROR", "Invalid magic header version"))

    # IDs unique
    seen = set()
    for c in nb.cells:
        if not c.id:
            errors.append(LintIssue("ERROR", "Cell missing id"))
        if c.id in seen:
            errors.append(LintIssue("ERROR", f"Duplicate cell id: {c.id}"))
        seen.add(c.id)

    # deps exist
    ids = {c.id for c in nb.cells}
    for c in nb.cells:
        deps_str = c.header_tokens.get("deps", "")
        if not deps_str:
            continue
        for d in deps_str.split(","):
            d = d.strip()
            if d and d not in ids:
                errors.append(LintIssue("ERROR", f"Cell {c.id} depends on missing id: {d}"))

    # simple cycle check (graph mode or general)
    graph = {c.id: [d.strip() for d in c.header_tokens.get("deps", "").split(",") if d.strip()] for c in nb.cells}
    temp = set()
    perm = set()

    def visit(v: str) -> bool:
        if v in perm:
            return True
        if v in temp:
            return False
        temp.add(v)
        for n in graph.get(v, []):
            if n not in graph:
                continue
            if not visit(n):
                return False
        temp.remove(v)
        perm.add(v)
        return True

    for node in graph.keys():
        if node not in perm:
            if not visit(node):
                errors.append(LintIssue("ERROR", "Cycle detected in dependencies"))
                break

    return errors, warns

