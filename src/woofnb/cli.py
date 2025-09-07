from __future__ import annotations

import argparse
import sys
import shutil
from pathlib import Path

from .lint import lint_notebook
from .parse import parse_file
from .plan import topo_order
from .fmt import format_text
from .runner import run_file
from .jupyter import export_file_to_ipynb, import_ipynb_file


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


def _cmd_run(
    path: Path, *, cells: list[str] | None = None, include_deps: bool = True
) -> int:
    return run_file(str(path), mode="all", cells=cells, include_deps=include_deps)


def _cmd_test(path: Path) -> int:
    return run_file(str(path), mode="tests")


def _cmd_clean(path: Path | None, clean_all: bool) -> int:
    if clean_all:
        base = Path.cwd()
        # Remove sidecars
        count = 0
        for p in base.rglob("*.woofnb.out"):
            try:
                p.unlink()
                count += 1
            except Exception:
                pass
        # Remove caches
        for d in base.rglob(".woof-cache"):
            if d.is_dir():
                try:
                    shutil.rmtree(d)
                except Exception:
                    pass
        print(f"Cleaned {count} sidecars and .woof-cache directories under {base}")
        return 0
    if path is None:
        print("clean: please provide a file or use --all")
        return 2
    sidecar = path.with_suffix(path.suffix + ".out")
    if sidecar.exists():
        try:
            sidecar.unlink()
        except Exception:
            pass
    cache_dir = path.parent / ".woof-cache" / path.stem
    if cache_dir.exists():
        try:
            shutil.rmtree(cache_dir)
        except Exception:
            pass
    print(f"Cleaned sidecar and cache for {path}")
    return 0


def _not_implemented(name: str) -> int:
    print(f"Subcommand '{name}' not yet implemented (Phase 2+)")
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="woof", description="WOOF Notebook CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_fmt = sub.add_parser("fmt", help="Format a .woofnb file (header + cells)")
    p_fmt.add_argument("file")

    p_lint = sub.add_parser("lint", help="Lint a .woofnb file")
    p_lint.add_argument("file")

    p_graph = sub.add_parser("graph", help="Print topological order of cells")
    p_graph.add_argument("file")

    p_run = sub.add_parser("run", help="Execute notebook")
    p_run.add_argument("file")
    p_run.add_argument(
        "--cell",
        dest="cells",
        action="append",
        help="Cell id to run (may be repeated)",
    )
    p_run.add_argument(
        "--no-deps",
        dest="no_deps",
        action="store_true",
        help="Run only the selected cell(s) without dependencies",
    )

    p_test = sub.add_parser("test", help="Run test cells and deps only")
    p_test.add_argument("file")

    p_clean = sub.add_parser("clean", help="Remove sidecars and caches")
    p_clean.add_argument("file", nargs="?", help="Specific .woofnb file to clean")
    p_clean.add_argument(
        "--all", action="store_true", dest="all", help="Clean all under CWD"
    )

    p_export = sub.add_parser("export", help="Export .woofnb to .ipynb")
    p_export.add_argument("file", help="Input .woofnb file")
    p_export.add_argument("-o", "--output", help="Output .ipynb file (default: stdout)")

    p_import = sub.add_parser("import", help="Import .ipynb to .woofnb")
    p_import.add_argument("file", help="Input .ipynb file")
    p_import.add_argument(
        "-o", "--output", help="Output .woofnb file (default: stdout)"
    )

    args = parser.parse_args(argv)
    cmd = args.cmd
    path = (
        Path(getattr(args, "file", "."))
        if hasattr(args, "file") and getattr(args, "file")
        else None
    )

    if cmd == "fmt":
        return _cmd_fmt(path)
    if cmd == "lint":
        return _cmd_lint(path)
    if cmd == "graph":
        return _cmd_graph(path)
    if cmd == "run":
        return _cmd_run(
            path,
            cells=getattr(args, "cells", None),
            include_deps=not getattr(args, "no_deps", False),
        )
    if cmd == "test":
        return _cmd_test(path)
    if cmd == "clean":
        return _cmd_clean(path, getattr(args, "all", False))
    if cmd == "export":
        export_file_to_ipynb(str(path), getattr(args, "output", None))
        return 0
    if cmd == "import":
        import_ipynb_file(str(path), getattr(args, "output", None))
        return 0

    return _not_implemented(cmd)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
