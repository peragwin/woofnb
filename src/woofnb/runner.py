from __future__ import annotations

import io
import json
import os
import signal
import subprocess
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

from ruamel.yaml import YAML

from .model import Notebook
from .parse import parse_file
from .plan import topo_order


@dataclass
class RunResult:
    failed_cells: List[str]
    total_cells: int
    mode: str  # "all" | "tests"
    sidecar_path: Path


def _compute_execution_set(nb: Notebook, mode: str) -> List[str]:
    ids = [c.id for c in nb.cells]
    if mode == "all":
        return ids
    # tests mode: include test cells and their deps
    test_ids: Set[str] = {c.id for c in nb.cells if c.type == "test"}
    deps_map = {
        c.id: [
            d.strip() for d in c.header_tokens.get("deps", "").split(",") if d.strip()
        ]
        for c in nb.cells
    }

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
    order = _execution_order(nb)
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
    nb: Notebook, *, mode: str = "all", sidecar_path: Optional[Path] = None
) -> RunResult:
    # Determine sidecar path
    if sidecar_path is None:
        base = Path(nb.path or "notebook.woofnb")
        sidecar_path = base.with_suffix(base.suffix + ".out")
    # Reset sidecar
    sidecar_path.write_text("", encoding="utf-8")

    failed: List[str] = []

    # Execution order
    order = _compute_execution_set(nb, mode)

    # Shared globals
    g: Dict[str, object] = {"__name__": "__main__"}
    woof_symbols: Dict[str, object] = {}
    g["woof"] = woof_symbols

    for c in nb.cells:
        if c.id not in order:
            continue
        if _is_true(c.header_tokens.get("disabled")):
            continue
        if c.type in {"md", "raw", "viz"}:  # skipped by default
            continue

        timestamp = _now_iso()
        outputs: List[dict] = []

        # data cells inject value
        if c.type == "data":
            val = _parse_data_cell(c.body)
            woof_symbols[c.id] = val
            if c.id.isidentifier():
                g[c.id] = val
            # log a display_data of the value repr
            outputs.append({"output_type": "execute_result", "repr": repr(val)})
            _append_sidecar(
                sidecar_path, {"cell": c.id, "timestamp": timestamp, "outputs": outputs}
            )
            continue

        # code/test/bash cells execute
        timeout = _parse_timeout(c)
        retries = 0
        try:
            retries = int(c.header_tokens.get("retries", "0"))
        except Exception:
            retries = 0

        isolated = c.header_tokens.get("sidefx", "") == "isolated"
        attempts = 0
        last: dict | None = None
        while attempts <= retries:
            attempts += 1
            if isolated or c.type == "bash":
                result = _cell_attempt_subprocess(
                    c.body if c.type != "bash" else c.body, timeout
                )
            else:
                result = _cell_attempt_exec(c.body, g, timeout)
            last = result
            # success if no error output_type present
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
        if any(o.get("output_type") == "error" for o in last["outputs"]):
            failed.append(c.id)

    return RunResult(
        failed_cells=failed,
        total_cells=len(order),
        mode=mode,
        sidecar_path=sidecar_path,
    )


def run_file(
    path: str, *, mode: str = "all", sidecar_path: Optional[str] = None
) -> int:
    nb = parse_file(path)
    res = run_notebook(
        nb, mode=mode, sidecar_path=Path(sidecar_path) if sidecar_path else None
    )
    return 1 if res.failed_cells else 0
