# WOOFNB 1.0 – Implementation Plan

This document records the phased plan to implement the WOOF Notebook toolchain.

## Goals

- Agent-first, plain-text format with deterministic execution
- Conformance Levels A → C for MVP, path to D
- CLI: `woof fmt | lint | graph | run | test | export | import`
- Jupyter interop via import/export
- Default-deny security posture

## Tech Stack (initial)

- Python 3.11+, stdlib only for Phases 0–1 (no external deps)
- CLI: argparse (switch to Typer later)
- YAML parsing deferred (header stored verbatim); future: PyYAML/ruamel
- Graph: custom topo sort (networkx optional later)
- Tests: to be added when package management is configured

## Repository Layout (initial)

- src/woofnb/
  - **init**.py
  - model.py
  - parse.py
  - serialize.py
  - lint.py
  - plan.py
  - cli.py
- examples/
  - minimal.woofnb
- docs/
  - implementation-plan.md (this file)

## Phases

### Phase 0 — Project scaffolding

- Create package structure and CLI stub
- Add example notebook and docs
- Acceptance: `python -c "import woofnb"` works when installed/packaged; for now, files exist

### Phase 1 — Core model + parser + serializer (Level A)

- Models for Header, Cell, Notebook
- Parser: split YAML header (verbatim) + fenced `cell` blocks
- Tokenizer for key=value with quoted values and escapes
- Serializer with stable token ordering; preserves header verbatim
- Linter (basic): magic/version, unique IDs, deps existence, simple cycle check
- CLI: `woof fmt`, `woof lint`, `woof graph` minimal
- Acceptance: Round-trip on examples; fmt is idempotent on cells; lints run

### Phase 2+ (outline)

- Formatter: canonical header ordering (requires YAML lib)
- Runner v1 (Python), sidecar outputs, timeouts/retries
- Caching by content hash
- Security policy enforcement (fs/net/shell)
- Jupyter import/export
- Test orchestration

## Open Questions

- Package manager preference (uv/poetry/pip)?
- Minimum Python version? (3.11+ assumed)
- Interop priority: export or import first?
- Polyglot support in MVP?

## Status Update (Phase 2 kickoff)

- Packaging: uv with .venv; CLI entrypoint installed as `woof`
- Dependencies: ruamel.yaml (runtime); pytest, ruff (dev)
- Formatter: YAML-aware header canonicalization implemented; idempotence tests passing
- Next: expand lint rules; consider Typer CLI ergonomics; prepare CI to run tests + ruff
