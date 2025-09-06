from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .lint import lint_notebook
from .parse import parse_file
from .plan import topo_order
from .fmt import format_text
from .runner import run_file


def _cmd_fmt(path: Path) -> int:
    original = path.read_text(encoding="utf-8")
    text = format_text(original)
    path.write_text(text, encoding="utf-8")
    print(f"Formatted: {path}")
    return 0


def _cmd_lint(path: Path) -> int:
    nb = parse_file(str(path))
    errors, warns = lint_notebook(nb)
    for w in warns:
        print(f"WARN: {w.message}")
    for e in errors:
        print(f"ERROR: {e.message}")
    if errors:
        return 1
    print("OK: no lint errors")
    return 0


def _cmd_graph(path: Path) -> int:
    nb = parse_file(str(path))
    order = topo_order(nb)
    for vid in order:
        print(vid)
    return 0


def _cmd_run(path: Path) -> int:
    return run_file(str(path), mode="all")


def _cmd_test(path: Path) -> int:
    return run_file(str(path), mode="tests")


def _not_implemented(name: str) -> int:
    print(f"Subcommand '{name}' not yet implemented (Phase 2+)")
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="woof", description="WOOF Notebook CLI (scaffold)"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_fmt = sub.add_parser("fmt", help="Format a .woofnb file (header + cells)")
    p_fmt.add_argument("file")

    p_lint = sub.add_parser("lint", help="Lint a .woofnb file")
    p_lint.add_argument("file")

    p_graph = sub.add_parser("graph", help="Print topological order of cells")
    p_graph.add_argument("file")

    p_run = sub.add_parser("run", help="Execute notebook")
    p_run.add_argument("file")

    p_test = sub.add_parser("test", help="Run test cells and deps only")
    p_test.add_argument("file")

    sub.add_parser("export", help="Export to ipynb (stub)")
    sub.add_parser("import", help="Import from ipynb (stub)")

    args = parser.parse_args(argv)
    cmd = args.cmd
    path = Path(getattr(args, "file", ".")) if hasattr(args, "file") else None

    if cmd == "fmt":
        return _cmd_fmt(path)
    if cmd == "lint":
        return _cmd_lint(path)
    if cmd == "graph":
        return _cmd_graph(path)
    if cmd == "run":
        return _cmd_run(path)
    if cmd == "test":
        return _cmd_test(path)

    return _not_implemented(cmd)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
