from __future__ import annotations

import builtins
import hashlib
import io
import json
import os
import signal
import socket
import subprocess
import sys
import traceback
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

from ruamel.yaml import YAML

from .model import Notebook
from .parse import parse_file
from .plan import topo_order
from . import __version__ as WOOF_VERSION


@dataclass
class RunResult:
    failed_cells: List[str]
    total_cells: int
    mode: str  # "all" | "tests"
    sidecar_path: Path


# ---------- Header and policy helpers ----------


def _yaml_header_map(nb: Notebook) -> dict:
    try:
        yaml = YAML(typ="safe")
        # header_text includes the magic on line 1; skip it if present
        lines = nb.header_text.splitlines()
        start = 1 if lines and lines[0].strip().startswith("%WOOFNB") else 0
        data = yaml.load("\n".join(lines[start:]))
        return data or {}
    except Exception:
        return {}


def _io_policy(header_map: dict) -> dict:
    pol = header_map.get("io_policy", {}) or {}
    return {
        "allow_files": bool(pol.get("allow_files", False)),
        "allow_network": bool(pol.get("allow_network", False)),
        "allow_shell": bool(pol.get("allow_shell", False)),
    }


@contextmanager
def _enforce_policy(files_allowed: bool, net_allowed: bool):
    # Patch builtins.open and socket.socket if not allowed
    orig_open = builtins.open
    orig_socket = socket.socket

    def _deny_open(*a, **kw):  # noqa: ANN001, ANN002
        raise PermissionError("File I/O not allowed by policy")

    class _DenySocket(socket.socket):  # type: ignore[misc]
        def __init__(self, *args, **kwargs):  # noqa: ANN001, ANN002
            raise PermissionError("Network not allowed by policy")

    try:
        if not files_allowed:
            builtins.open = _deny_open  # type: ignore[assignment]
        if not net_allowed:
            socket.socket = _DenySocket  # type: ignore[assignment]
        yield
    finally:
        builtins.open = orig_open  # type: ignore[assignment]
        socket.socket = orig_socket  # type: ignore[assignment]


# ---------- Caching helpers ----------


def _deps_map(nb: Notebook) -> Dict[str, List[str]]:
    return {
        c.id: [
            d.strip() for d in c.header_tokens.get("deps", "").split(",") if d.strip()
        ]
        for c in nb.cells
    }


def _transitive_ids(root: str, deps_map: Dict[str, List[str]]) -> List[str]:
    seen: Set[str] = set()
    stack = [root]
    order: List[str] = []
    while stack:
        v = stack.pop()
        if v in seen:
            continue
        seen.add(v)
        order.append(v)
        for d in deps_map.get(v, []):
            stack.append(d)
    return order


def _cache_enabled(header_map: dict) -> bool:
    exec_map = header_map.get("execution", {}) or {}
    cache = exec_map.get("cache", "")
    return bool(cache) and str(cache) in {"1", "true", "yes", "content-hash"}


def _cache_dir(nb: Notebook) -> Path:
    base = Path(nb.path or "notebook.woofnb").resolve()
    return base.parent / ".woof-cache" / base.stem


def _cache_cell_path(nb: Notebook, cell_id: str) -> Path:
    return _cache_dir(nb) / f"{cell_id}.json"


def _compute_cache_key(
    cell_body: str, transitive: Dict[str, str], env: object, params: object
) -> str:
    payload = {
        "body": cell_body,
        "deps": transitive,
        "env": env,
        "params": params,
        "runner": WOOF_VERSION,
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _try_cache_read(nb: Notebook, cell_id: str, key: str) -> Optional[List[dict]]:
    p = _cache_cell_path(nb, cell_id)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("key") == key:
            return data.get("outputs") or []
    except Exception:
        return None
    return None


def _cache_write(nb: Notebook, cell_id: str, key: str, outputs: List[dict]) -> None:
    p = _cache_cell_path(nb, cell_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {"key": key, "outputs": outputs}
    p.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )


def _compute_execution_set(
    nb: Notebook,
    mode: str,
    selected_ids: Optional[Set[str]] = None,
    include_deps: bool = True,
) -> List[str]:
    ids = [c.id for c in nb.cells]
    order = _execution_order(nb)

    # If specific cells requested, compute closure optionally including deps
    if selected_ids:
        selected_ids = {i for i in selected_ids if i in ids}
        if not selected_ids:
            return []
        if include_deps:
            deps_map = _deps_map(nb)
            needed: Set[str] = set()
            for sid in selected_ids:
                for tid in _transitive_ids(sid, deps_map):
                    needed.add(tid)
        else:
            needed = set(selected_ids)
        return [cid for cid in order if cid in needed]

    if mode == "all":
        return ids

    # tests mode: include test cells and their deps
    test_ids: Set[str] = {c.id for c in nb.cells if c.type == "test"}
    deps_map = _deps_map(nb)

    # closure of deps for each test cell
    needed: Set[str] = set()
    stack: List[str] = []
    for t in test_ids:
        stack.append(t)
        while stack:
            v = stack.pop()
            if v in needed:
                continue
            needed.add(v)
            for d in deps_map.get(v, []):
                stack.append(d)
    # Return in topo/file order filtered to needed
    return [cid for cid in order if cid in needed]


def _execution_order(nb: Notebook) -> List[str]:
    # execution.order default linear
    header = nb.header_text
    order_mode = "linear"
    # best-effort parse of header execution.order without YAML lib
    if "execution:" in header and "order:" in header:
        try:
            yaml = YAML(typ="safe")
            data = yaml.load("\n".join(nb.header_text.splitlines()[1:]))
            if isinstance(data, dict):
                order_mode = data.get("execution", {}).get("order", "linear")
        except Exception:
            pass
    if order_mode == "graph":
        return topo_order(nb)
    return [c.id for c in nb.cells]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_sidecar(sidecar: Path, record: dict) -> None:
    with sidecar.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _parse_data_cell(body: str):
    # Try JSON first; then YAML
    try:
        return json.loads(body)
    except Exception:
        pass
    try:
        yaml = YAML(typ="safe")
        return yaml.load(body)
    except Exception:
        return body  # fallback raw


def _is_true(val: Optional[str]) -> bool:
    return (val or "").lower() in {"1", "true", "yes"}


def _parse_timeout(c) -> Optional[int]:
    t = c.header_tokens.get("timeout", "").strip()
    if not t:
        return None
    try:
        return int(t)
    except Exception:
        return None


def _cell_attempt_exec(code: str, g: Dict[str, object], timeout: Optional[int]) -> dict:
    # Execute code in shared globals with optional timeout (POSIX only)
    timed_out = False

    def _handle_alarm(signum, frame):  # noqa: ARG001
        nonlocal timed_out
        timed_out = True
        raise TimeoutError("Cell execution timed out")

    have_signal = hasattr(signal, "signal") and hasattr(signal, "SIGALRM")
    old_handler = None
    if timeout and have_signal and os.name == "posix":
        old_handler = signal.signal(signal.SIGALRM, _handle_alarm)
        signal.alarm(timeout)

    out_buf, err_buf = io.StringIO(), io.StringIO()
    records: List[dict] = []
    try:
        with redirect_stdout(out_buf), redirect_stderr(err_buf):
            exec(compile(code, "<cell>", "exec"), g, g)  # noqa: S102
    except Exception as e:  # noqa: BLE001
        tb = traceback.format_exc()
        records.append(
            {
                "output_type": "error",
                "ename": e.__class__.__name__,
                "evalue": str(e),
                "traceback": tb.splitlines(),
            }
        )
    finally:
        if timeout and have_signal and os.name == "posix":
            signal.alarm(0)
            if old_handler is not None:
                signal.signal(signal.SIGALRM, old_handler)
    stdout_text = out_buf.getvalue()
    stderr_text = err_buf.getvalue()
    if stdout_text:
        records.insert(
            0, {"output_type": "stream", "name": "stdout", "text": stdout_text}
        )
    if stderr_text:
        records.append({"output_type": "stream", "name": "stderr", "text": stderr_text})
    return {"outputs": records}


def _cell_attempt_subprocess(code: str, timeout: Optional[int]) -> dict:
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout if timeout else None,
            check=False,
        )
        outputs: List[dict] = []
        if proc.stdout:
            outputs.append(
                {"output_type": "stream", "name": "stdout", "text": proc.stdout}
            )
        if proc.stderr:
            outputs.append(
                {"output_type": "stream", "name": "stderr", "text": proc.stderr}
            )
        if proc.returncode != 0:
            outputs.append(
                {
                    "output_type": "error",
                    "ename": "SubprocessError",
                    "evalue": f"returncode={proc.returncode}",
                    "traceback": [],
                }
            )
        return {"outputs": outputs}
    except subprocess.TimeoutExpired:
        return {
            "outputs": [
                {
                    "output_type": "error",
                    "ename": "TimeoutExpired",
                    "evalue": "",
                    "traceback": [],
                }
            ]
        }


def run_notebook(
    nb: Notebook,
    *,
    mode: str = "all",
    sidecar_path: Optional[Path] = None,
    selected_ids: Optional[Set[str]] = None,
    include_deps: bool = True,
) -> RunResult:
    # Determine sidecar path
    if sidecar_path is None:
        base = Path(nb.path or "notebook.woofnb")
        sidecar_path = base.with_suffix(base.suffix + ".out")
    # Reset sidecar
    sidecar_path.write_text("", encoding="utf-8")

    failed: List[str] = []

    # Execution order
    order = _compute_execution_set(
        nb, mode, selected_ids=selected_ids, include_deps=include_deps
    )

    # Globals, header & policy, caching
    g: Dict[str, object] = {"__name__": "__main__"}
    woof_symbols: Dict[str, object] = {}
    g["woof"] = woof_symbols

    header_map = _yaml_header_map(nb)
    pol = _io_policy(header_map)
    cache_enabled = _cache_enabled(header_map)
    deps_map = _deps_map(nb)
    body_map: Dict[str, str] = {c.id: c.body for c in nb.cells}

    for c in nb.cells:
        if c.id not in order:
            continue
        if _is_true(c.header_tokens.get("disabled")):
            continue
        if c.type in {"md", "raw", "viz"}:  # skipped by default
            continue

        timestamp = _now_iso()

        # Caching key (includes transitive deps, env, params)
        trans_ids = _transitive_ids(c.id, deps_map)
        trans_bodies = {i: body_map.get(i, "") for i in trans_ids if i != c.id}
        env_map = header_map.get("env")
        params_map = header_map.get("parameters")
        cache_key = _compute_cache_key(c.body, trans_bodies, env_map, params_map)

        if cache_enabled:
            cached_outputs = _try_cache_read(nb, c.id, cache_key)
            if cached_outputs is not None:
                _append_sidecar(
                    sidecar_path,
                    {
                        "cell": c.id,
                        "timestamp": timestamp,
                        "outputs": cached_outputs,
                        "cached": True,
                    },
                )
                continue

        outputs: List[dict] = []

        # data cells inject value
        if c.type == "data":
            val = _parse_data_cell(c.body)
            woof_symbols[c.id] = val
            if c.id.isidentifier():
                g[c.id] = val
            outputs.append({"output_type": "execute_result", "repr": repr(val)})
            _append_sidecar(
                sidecar_path,
                {"cell": c.id, "timestamp": timestamp, "outputs": outputs},
            )
            if cache_enabled:
                _cache_write(nb, c.id, cache_key, outputs)
            continue

        # Execution params
        timeout = _parse_timeout(c)
        try:
            retries = int(c.header_tokens.get("retries", "0"))
        except Exception:
            retries = 0

        sidefx = (c.header_tokens.get("sidefx", "") or "").strip()
        isolated = sidefx == "isolated"

        # Enforce shell policy for bash
        if c.type == "bash":
            if not (pol["allow_shell"] and (sidefx == "shell" or c.type == "bash")):
                outputs = [
                    {
                        "output_type": "error",
                        "ename": "PolicyError",
                        "evalue": "Shell not allowed",
                        "traceback": [],
                    }
                ]
                _append_sidecar(
                    sidecar_path,
                    {"cell": c.id, "timestamp": timestamp, "outputs": outputs},
                )
                failed.append(c.id)
                continue

        attempts = 0
        last: dict | None = None
        while attempts <= retries:
            attempts += 1
            if isolated or c.type == "bash":
                # Subprocess execution (bash always here)
                result = _cell_attempt_subprocess(c.body, timeout)
            else:
                wants_fs = sidefx in {"fs", "shell"}
                wants_net = sidefx in {"net", "shell"}
                files_allowed = pol["allow_files"] and wants_fs
                net_allowed = pol["allow_network"] and wants_net
                with _enforce_policy(files_allowed, net_allowed):
                    result = _cell_attempt_exec(c.body, g, timeout)
            last = result
            if not any(
                o.get("output_type") == "error" for o in result.get("outputs", [])
            ):
                break

        if last is None:
            last = {"outputs": []}

        _append_sidecar(
            sidecar_path,
            {"cell": c.id, "timestamp": timestamp, "outputs": last["outputs"]},
        )
        if cache_enabled:
            _cache_write(nb, c.id, cache_key, last["outputs"])
        if any(o.get("output_type") == "error" for o in last["outputs"]):
            failed.append(c.id)

    actual_mode = "cells" if selected_ids else mode
    return RunResult(
        failed_cells=failed,
        total_cells=len(order),
        mode=actual_mode,
        sidecar_path=sidecar_path,
    )


def run_file(
    path: str,
    *,
    mode: str = "all",
    sidecar_path: Optional[str] = None,
    cells: Optional[List[str]] = None,
    include_deps: bool = True,
) -> int:
    nb = parse_file(path)
    selected_ids = set(cells) if cells else None
    res = run_notebook(
        nb,
        mode=mode,
        sidecar_path=Path(sidecar_path) if sidecar_path else None,
        selected_ids=selected_ids,
        include_deps=include_deps,
    )
    return 1 if res.failed_cells else 0
