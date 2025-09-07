# WOOF Notebook (WOOFNB)

Workflow Oriented Open Format — a lightweight, agent-first, plain-text notebook format and toolkit.

- Spec: see `specification.md`
- CLI: `woof` (fmt | lint | graph | run | test | clean)
- Language: Python 3.11+
- Package/venv: uv

## Installation

Recommended (uv tool install)

- macOS/Linux:

```
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install --force --upgrade git+https://github.com/peragwin/woofnb.git
```

- From a local checkout:

```
uv tool install --force --upgrade .
```

- Windows (PowerShell):

```
powershell -ExecutionPolicy Bypass -Command "iwr https://astral.sh/uv/install.ps1 -UseBasicParsing | iex"
uv tool install --force --upgrade git+https://github.com/peragwin/woofnb.git
```

Alternative (pipx)

If you prefer pipx:

```
# Install pipx if needed: https://pypa.github.io/pipx/
pipx ensurepath
# From GitHub
pipx install git+https://github.com/peragwin/woofnb.git
# Or from a local checkout
pipx install .
```

Installer script (Unix/macOS)

```
./scripts/install_woof.sh                 # local checkout
./scripts/install_woof.sh --from-git https://github.com/peragwin/woofnb.git
```

Verify

```
woof --help
```

## Quick start

1. Install uv (if not installed):

```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Sync dependencies (default + dev):

```
uv sync --group dev
```

3. Try the CLI on the example:

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
## Execution, caching, and policy

- Execution order
  - Default: linear; set to graph with header:

```

%WOOFNB 1.0
execution:
order: graph

```

- Caching (content-hash)
  - Enable with:

```

%WOOFNB 1.0
execution:
order: linear
cache: content-hash

```

  - Cache key includes: cell body + transitive dep bodies + env + parameters + runner version
  - Cache is stored under `.woof-cache/<notebook-stem>/<cell-id>.json`

- Policy (default-deny)
  - Header controls allow-list:

```

%WOOFNB 1.0
io_policy:
allow_files: false
allow_network: false
allow_shell: false

```

  - Each cell must also declare intent via a `sidefx` token to enable capabilities per cell:
    - `sidefx=fs` for file access; `sidefx=net` for network; `sidefx=shell` for bash
  - Example cell fence:

```

```cell id=fetch type=code deps=prep sidefx=net timeout=10
print("net request here...")
```

```

## Cleaning sidecars and caches

- Clean for a specific notebook:

```

uv run woof clean examples/minimal.woofnb

```

- Clean all under the current directory (sidecars + .woof-cache trees):

```

uv run woof clean --all

```

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
