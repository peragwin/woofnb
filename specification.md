# WOOF Notebook Specification (WOOFNB 1.0)

**Canonical name:** _WOOF Notebook_
**Acronym:** **WOOF** — _Workflow Oriented Open Format_
**Canonical file extension:** `.woofnb`
**Alias / shorthand extension:** `.wnb`
**MIME type:** `application/vnd.woof.notebook+text; version=1.0`
**Status:** Draft 1.0 (agent-first, human-readable)

---

## 1. Purpose & Design Goals

WOOF Notebook is a lightweight, plain-text, **agent-first** notebook format designed for clean diffs, deterministic execution, and seamless collaboration.

- **Diff/Merge Friendly:** Stable, minimal syntax; no noisy metadata; optional sidecars for heavy outputs.
- **Agent-Editable:** Simple grammar; explicit dependencies; per-cell capabilities and resource limits.
- **Deterministic Execution:** Linear or DAG (graph) order; cache keyed by content + deps + env.
- **Interoperable:** Round-trip converters to/from Jupyter `.ipynb`.
- **Secure by Default:** Deny file/network/shell access unless explicitly allowed.
- **Extensible:** Reserved keys, semantic versioning, optional sections.

---

## 2. File Structure

A WOOF Notebook source is a single **UTF-8** text file:

1. **Header:** A YAML document beginning with a magic/version line.
2. **Cells:** One or more fenced **cell blocks**, each with a single-line _cell header_ (key=value tokens) followed by the _cell body_.
3. **(Optional) Outputs Sidecar:** Stored separately to keep sources small and diffable.

````markdown
%WOOFNB 1.0
name: example
language: python

# ...more YAML header...

```cell id=prep type=code deps=
# code...
```

```cell id=report type=md
# markdown...
```
````

---

## 3. Header (YAML)

The header is a **single YAML document** that MUST start with the magic line:

```yaml
%WOOFNB 1.0
```

### 3.1 Required Keys

- `name` (string): Human-friendly name.
- `language` (enum/string): Primary language (e.g., `python`, `r`, `julia`, `bash`).

### 3.2 Recommended Keys

- `env` (map): Execution environment declaration.

  - Example:

    ```yaml
    env:
      python: "3.11"
      requirements: [numpy==2.0.1, matplotlib==3.9.0]
      # or containers:
      container:
        image: "ghcr.io/acme/woof-runner:py311"
    ```

- `parameters` (map): Freeform parameters used by cells.
- `defaults` (map): Default execution constraints.

  - `timeout_sec` (int)
  - `memory_mb` (int)

- `execution` (map):

  - `order` (`linear` | `graph`)
  - `cache` (`content-hash` | `none`)

- `io_policy` (map):

  - `allow_files` (bool) = false
  - `allow_network` (bool) = false
  - `allow_shell` (bool) = false

### 3.3 Optional Keys

- `provenance` (map): `{ created_by, created_at, agent, source_repo, commit }`
- `metadata` (map): Arbitrary, tool-specific metadata.
- `tags` (list of strings)
- `version` (string): User-managed project version (distinct from `%WOOFNB`).

> **Notes**
>
> - Tools MUST ignore unknown header keys (forward-compatibility).
> - Runners SHOULD validate known keys and warn on conflicts.

---

## 4. Cell Blocks

Cells are delimited by a fenced block that begins with a **cell header line**:

````text
```cell <key=value tokens>
<cell body...>
```
````

### 4.1 Cell Header Line

- A single line after the opening fence: ` ```cell ...`
- Contains **space-separated** `key=value` tokens.
- Values must NOT include spaces; if needed, quote with `"`; `\"` escapes quotes.

**Required keys**

- `id` (string, unique within file; `[A-Za-z0-9._-]+`)
- `type` (enum; see 4.2)

**Common keys**

- `name` (string; human label)
- `deps` (comma-separated list of cell `id`s; empty = no deps)
- `timeout` (int, seconds; overrides `defaults.timeout_sec`)
- `memory_mb` (int; overrides `defaults.memory_mb`)
- `sidefx` (capabilities intent: `none|fs|net|shell|isolated`)
- `tags` (comma-separated strings)
- `retries` (int >= 0)
- `priority` (int; for schedulers)
- `disabled` (bool: `true|false`)

**Example**

````text
```cell id=train type=code name=train_model deps=prep,features timeout=30 sidefx=none tags=ml,fast
# code...
```
````

### 4.2 Cell Types

- `code` — Executable code in the notebook’s `language`.
- `md` — Markdown; not executed.
- `data` — Inline small data (JSON or YAML; runner MUST pass as value).
- `test` — Assertions that validate one or more deps.
- `viz` — Declarative visualization spec (e.g., Vega-Lite JSON).
- `bash` — Shell script cell (runner MAY sandbox; requires `io_policy.allow_shell=true` or `sidefx=shell`).
- `raw` — Uninterpreted text blob; ignored by runner.

### 4.3 Cell Body

- Arbitrary UTF-8 text.
- For `data` cells, body SHOULD be valid JSON (preferred) or YAML.
- For `viz` cells, body SHOULD be a valid declarative spec.
- For `test` cells, body MUST be valid code in `language` or as declared by `lang`.

---

## 5. Execution Semantics

### 5.1 Order

- `linear`: Execute cells **in file order**, skipping non-executable types (`md`, `raw`, `viz` unless a runner executes viz).
- `graph`: Execute cells in **topological order** of the dependency graph defined by `deps`. Ties resolved by file order.

### 5.2 State Model

- Default: **single kernel** per `language` (shared memory/state).
- `sidefx=isolated`: Run the cell in a **fresh process/kernel** (no shared state).
- Runners MAY allow explicit kernel names (e.g., `kernel=py311`) for advanced use.

### 5.3 Capabilities & I/O

- Global defaults from `io_policy` in header.
- Per-cell `sidefx` can **declare** intent; the runner **enforces** policy:

  - `none` — No external effects expected.
  - `fs` — Requires filesystem I/O.
  - `net` — Requires network.
  - `shell` — Requires shell access (implies `fs` by convention).
  - `isolated` — Fresh process with no shared globals.

### 5.4 Resources

- `timeout` (sec) and `memory_mb` per cell override header defaults.
- Runners MUST enforce timeouts; memory enforcement is runner-dependent (SHOULD warn if unsupported).

### 5.5 Caching

- If `execution.cache=content-hash`, a cell MAY be skipped when the **cache key** matches:

  - Hash of cell body
  - Hash of transitive deps’ bodies
  - Env fingerprint (`env`)
  - `parameters` (whole map)
  - Runner version (optional)

- Runners MUST invalidate cache on any part change.

### 5.6 Retries

- If `retries` is set, runner MAY retry on **transient errors** (non-deterministic failure classes).
- Deterministic failures (e.g., syntax errors) SHOULD NOT be retried.

---

## 6. Data Exchange Between Cells

Runners SHOULD expose a **symbol table** or variable binding mechanism:

- For `data` cells:

  - JSON body is parsed; the value is bound under the cell `id` (e.g., `data = {{cfg}}`) **or** injected as a runtime object if the language supports it.

- For `code` cells:

  - Symbols defined at top-level become part of the shared state (unless `isolated`).

---

## 7. Outputs & Artifacts

### 7.1 Sidecar Outputs

To keep the source small and diffable, heavy outputs MUST NOT be embedded by default.

- **Sidecar filename:** `<notebook>.woofnb.out` (JSON Lines).
- Each line is a JSON object `{ "cell": "<id>", "timestamp": "...", "outputs": [...] }`.
- `outputs` SHOULD mirror a minimal subset of Jupyter’s output schema:

  - `stream` (name=`stdout|stderr`, text)
  - `display_data` (mime → data or file reference)
  - `execute_result` (repr)
  - `error` (ename, evalue, traceback)

### 7.2 Artifact Files

- Directory: `./artifacts/<cell-id>/...` (runner-managed).
- Markdown cells reference images via relative paths, e.g., `![chart](artifacts/chart1/bar.png)`.
- Runners MAY provide `embed=true` options to inline small images as data URIs (not recommended for large assets).

---

## 8. Interop with Jupyter

A reference converter MUST:

- Map WOOF cells to `ipynb` cells (`type → cell_type`).
- Preserve cell `id` and header tokens under `cell.metadata.woof.*`.
- Map sidecar outputs back into `ipynb` outputs if requested.
- When converting `ipynb → WOOF`, strip transient metadata and serialize outputs to the sidecar.

---

## 9. Minimal JSON Schema (Informative)

```json
{
  "file": "WOOFNB",
  "version": "1.0",
  "header": {
    "name": "string",
    "language": "string",
    "env": {
      "python": "string",
      "requirements": ["string"],
      "container": { "image": "string" }
    },
    "parameters": { "additionalProperties": true },
    "defaults": { "timeout_sec": "number", "memory_mb": "number" },
    "execution": { "order": "string", "cache": "string" },
    "io_policy": {
      "allow_files": "boolean",
      "allow_network": "boolean",
      "allow_shell": "boolean"
    },
    "provenance": {
      "created_by": "string",
      "created_at": "string",
      "agent": "string"
    },
    "metadata": { "additionalProperties": true },
    "tags": ["string"]
  },
  "cells": [
    {
      "id": "string",
      "type": "string",
      "name": "string",
      "deps": ["string"],
      "timeout": "number",
      "memory_mb": "number",
      "sidefx": "string",
      "tags": ["string"],
      "retries": "number",
      "priority": "number",
      "disabled": "boolean",
      "lang": "string",
      "body": "string"
    }
  ]
}
```

---

## 10. Canonical Formatting

A formatter (`woof fmt`) MUST enforce:

- Stable header order.
- Stable token order in cell headers.
- Whitespace normalization.
- Unique IDs.

---

## 11. Validation & Linting

A linter (`woof lint`) MUST check:

- Valid header and required keys.
- Unique IDs; no missing deps.
- Acyclic graph in `graph` mode.
- Policy compliance for sidefx.

---

## 12. Security Model

- **Default-deny**: All external capabilities disabled unless explicitly allowed.
- **Sandboxing**: Runners SHOULD sandbox per cell.
- **Network**: Only if both policy and sidefx allow.
- **Shell**: Only if both policy and sidefx allow.
- **File I/O**: If enabled, SHOULD restrict to working directory.

---

## 13. CLI Reference (Informative)

- `woof fmt <file.woofnb>`
- `woof lint <file.woofnb>`
- `woof graph <file.woofnb>`
- `woof run <file.woofnb>`
- `woof test <file.woofnb>`
- `woof export <file.woofnb> --ipynb out.ipynb`
- `woof import <file.ipynb> --woofnb out.woofnb`

---

## 14. Examples

### 14.1 Minimal

````yaml
%WOOFNB 1.0
name: hello-world
language: python
execution:
  order: graph
```

```cell id=data1 type=data
[1,2,3]
```

```cell id=mean type=code deps=data1
values = [1,2,3]
print(sum(values)/len(values))
```

```cell id=test1 type=test deps=mean
assert True
```
````

---

## 15. Versioning & Compatibility

- Magic line declares spec version.
- Minor versions backwards-compatible.
- Breaking changes reserved for major versions.

---

## 16. Conformance Levels

- **Level A:** Parse/Format.
- **Level B:** Execute basics.
- **Level C:** Graph, cache, viz, sidecar.
- **Level D:** Polyglot & strict security.

---

## 17. Reserved & Extensions

- Reserved cell keys: `schedule`, `kernel`, `checkpoint`, `mounts`.
- Reserved header namespaces: `x-*` and `metadata`.

---

## 18. ABNF (Informative)

````
CELL-LINE   = "```cell" 1*SP TOKEN *(1*SP TOKEN)
TOKEN       = KEY "=" VALUE
KEY         = 1*(ALPHA / DIGIT / "_" / "-" )
VALUE       = QUOTED / BARE
BARE        = 1*(ALPHA / DIGIT / "_" / "-" / "." / "," )
QUOTED      = DQUOTE *( QCHAR ) DQUOTE
QCHAR       = %x20-21 / %x23-5B / %x5D-7E / ESC
ESC         = "\\" DQUOTE
````

---

## 19. Reference Runner Behavior

- Parse → Plan → Enforce → Execute → Cache → Report.
- Exit non-zero if any cell fails (unless disabled).

---

## 20. Naming

- **Format name:** WOOF Notebook
- **Extensions:** `.woofnb` (canonical), `.wnb` (alias)
- **Acronym:** Workflow Oriented Open Format (Notebook)
