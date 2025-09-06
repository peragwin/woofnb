# WOOF Notebook (WOOFNB)

Workflow Oriented Open Format — a lightweight, agent-first, plain-text notebook format and toolkit.

- Spec: see `specification.md`
- CLI: `woof` (fmt | lint | graph | run | test)
- Language: Python 3.11+
- Package/venv: uv

## Quick start

1) Install uv (if not installed):

```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2) Sync dependencies (default + dev):

```
uv sync --group dev
```

3) Try the CLI on the example:

```
uv run woof graph examples/minimal.woofnb
uv run woof lint examples/minimal.woofnb
uv run woof fmt examples/minimal.woofnb
uv run woof run examples/minimal.woofnb
uv run woof test examples/minimal.woofnb
```

If you prefer to use the module without uv, you can add `src` to `PYTHONPATH` and invoke `python -m woofnb.cli`.

## What is WOOFNB?

A plain-text notebook format optimized for:
- Clean diffs and merges
- Deterministic execution (linear or DAG)
- Agent editability (simple grammar, explicit deps, per-cell controls)
- Security by default (deny fs/net/shell unless allowed)
- Interop (planned import/export to Jupyter)

See the spec in `specification.md` for the full details.

## Repository layout

- `src/woofnb/` — toolkit package
  - `model.py` — data structures
  - `parse.py` — parser for header + cell fences
  - `serialize.py` — serializer with canonical token ordering
  - `fmt.py` — YAML-aware header formatting
  - `lint.py` — validations (ids, deps, cycles, policy checks WIP)
  - `plan.py` — linear/graph planning (topo)
  - `runner.py` — Runner v1: execute code/data/test, sidecar outputs
  - `cli.py` — CLI entrypoint
- `examples/` — example notebooks (`.woofnb`)
- `docs/` — design/implementation notes
- `tests/` — unit tests (unittest)

## Development

- Lint:

```
uv run ruff check src tests
```

- Tests:

```
uv run python -m unittest discover -s tests -p 'test_*.py'
```

- Formatting (tool’s own fmt):

```
uv run woof fmt examples/minimal.woofnb
```

## Sidecar outputs and artifacts

- Sidecar outputs are written to `<notebook>.woofnb.out` as JSON Lines
- Artifacts (planned) will live under `./artifacts/<cell-id>/...`

## Status

- Phase 0–1: parser/serializer/lint/graph complete
- Phase 2: YAML-aware header formatting implemented
- Runner v1: implemented for Python; isolation and policy enforcement are minimal
- CI: GitHub Actions workflow added to run ruff + tests

## License

TBD.

