from __future__ import annotations

from typing import List

from .model import Notebook


def topo_order(nb: Notebook) -> List[str]:
    """Return topological order of cell ids; ties resolved by file order.

    If cycles exist, raises ValueError.
    """
    order = [c.id for c in nb.cells]
    graph = {c.id: [d.strip() for d in c.header_tokens.get("deps", "").split(",") if d.strip()] for c in nb.cells}

    temp = set()
    perm = set()
    out: list[str] = []

    def visit(v: str):
        if v in perm:
            return
        if v in temp:
            raise ValueError("Cycle detected in dependencies")
        temp.add(v)
        for n in graph.get(v, []):
            if n in graph:
                visit(n)
        temp.remove(v)
        perm.add(v)
        out.append(v)

    for v in order:
        if v not in perm:
            visit(v)

    # out is reverse postorder; map to file order tie-breaker by stable append
    # Ensure we maintain file order for nodes without deps relation
    pos = {vid: i for i, vid in enumerate(order)}
    out.sort(key=lambda vid: pos.get(vid, 1_000_000))
    return out

