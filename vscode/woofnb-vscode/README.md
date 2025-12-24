# WOOF Notebook VS Code Extension (MVP)

This extension adds basic support for WOOFNB notebooks (`.woofnb`, `.wnb`) to VS Code.

Features:
- Open/edit `.woofnb` files as notebooks (cells parsed from fenced ```cell blocks)
- Run: All, Tests, Single cell (with or without dependencies)
- Display outputs per cell (from sidecar `<file>.woofnb.out`)
- Lint/Format/Clean via the `woof` CLI

Requirements:
- `woof` must be on PATH (configurable)

Settings:
- `woofnb.runnerCommand`: default `woof` (e.g., set to `uv run woof`)
- `woofnb.runnerArgs`: extra args before subcommands
- `woofnb.runCellIncludesDeps`: default true

Commands:
- `WOOF: Run All` (`woofnb.runAll`)
- `WOOF: Run Tests` (`woofnb.runTests`)
- `WOOF: Run Cell (no deps)` (`woofnb.runCellOnly`)
- `WOOF: Lint Notebook` (`woofnb.lint`)
- `WOOF: Format Notebook` (`woofnb.format`)
- `WOOF: Clean Sidecar & Cache` (`woofnb.clean`)

Notes:
- Per-cell execution uses `woof run <file> --cell <id>` (repeated) and `--no-deps` when requested.
- Outputs are read from the sidecar after the run finishes (streaming is planned).
- All cells are treated as code for now and use the `python` language mode.
