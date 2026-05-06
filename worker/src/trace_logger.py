"""Per-worker SQLite trace writer.

Each worker container writes to its own file: agent_traces_{hostname}.db.
That lets us run multiple workers concurrently without all of them
fighting over a single SQLite write lock.

Reads are handled by shared.trace_reader.read_traces, which globs every
worker's file in the trace dir and merges results.
"""

import json
import logging
import os
import socket
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)


class _StrandsTraceHook:
    """Bridges Strands lifecycle events into TraceLogger rows.

    Registered against the Agent via `hooks=[tracer.make_strands_hook(job_id)]`.
    One instance per agent invocation so the job_id stays scoped.

    We emit one row per tool call (with elapsed time and ok/error status)
    and one row per model call. Schema matches ManualSupervisor's _step
    output so `make show-trace` is mode-agnostic.
    """

    def __init__(self, tracer: "TraceLogger", job_id: str) -> None:
        self.tracer = tracer
        self.job_id = job_id
        self._tool_starts: dict[str, float] = {}
        self._model_start: float | None = None

    def register_hooks(self, registry, **_kwargs) -> None:
        # Imported lazily — only StrandsSupervisor needs strands installed.
        import time as _t  # noqa: F401  (used by inner closures)
        from strands.hooks.events import (
            AfterModelCallEvent,
            AfterToolCallEvent,
            BeforeModelCallEvent,
            BeforeToolCallEvent,
        )
        registry.add_callback(BeforeToolCallEvent, self._on_before_tool)
        registry.add_callback(AfterToolCallEvent, self._on_after_tool)
        registry.add_callback(BeforeModelCallEvent, self._on_before_model)
        registry.add_callback(AfterModelCallEvent, self._on_after_model)

    def _on_before_tool(self, event) -> None:
        import time
        tu = event.tool_use
        self._tool_starts[tu.get("toolUseId", "")] = time.time()

    def _on_after_tool(self, event) -> None:
        import time
        tu = event.tool_use
        tool_use_id = tu.get("toolUseId", "")
        start = self._tool_starts.pop(tool_use_id, time.time())
        duration_ms = (time.time() - start) * 1000

        if event.exception is not None:
            status = "error"
            output = {"error": f"{type(event.exception).__name__}: {event.exception}"}
        else:
            status = "ok"
            # ToolResult is a dict with status + content blocks; serialize defensively.
            output = event.result if isinstance(event.result, dict) else {"result": str(event.result)}

        self.tracer.log(
            self.job_id,
            tu.get("name", "tool"),
            "tool_call",
            tu.get("input", {}),
            output,
            duration_ms,
            status,
        )

    def _on_before_model(self, _event) -> None:
        import time
        self._model_start = time.time()

    def _on_after_model(self, _event) -> None:
        import time
        if self._model_start is None:
            return
        duration_ms = (time.time() - self._model_start) * 1000
        self._model_start = None
        self.tracer.log(
            self.job_id,
            "model",
            "model_call",
            {},
            {},
            duration_ms,
            "ok",
        )


_SCHEMA = """
CREATE TABLE IF NOT EXISTS traces (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id       TEXT NOT NULL,
    agent_name   TEXT NOT NULL,
    step         TEXT NOT NULL,
    input        TEXT,
    output       TEXT,
    duration_ms  REAL,
    timestamp    TEXT NOT NULL,
    status       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_traces_job ON traces(job_id);
"""


def _hostname_safe() -> str:
    """Hostname that's safe to embed in a filename. Docker compose container
    names are already filesystem-safe (e.g. hyperpersona-worker-1)."""
    raw = os.environ.get("HOSTNAME") or socket.gethostname() or "unknown"
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in raw)


class TraceLogger:
    def __init__(self, db_dir: str = "/app/traces") -> None:
        os.makedirs(db_dir, exist_ok=True)
        self.db_dir = db_dir
        self.db_path = os.path.join(db_dir, f"agent_traces_{_hostname_safe()}.db")
        self._lock = threading.Lock()
        self._init_db()
        log.info("TraceLogger writing to %s", self.db_path)

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def log(
        self,
        job_id: str,
        agent_name: str,
        step: str,
        input_data: Any,
        output_data: Any,
        duration_ms: float,
        status: str = "ok",
    ) -> None:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                # Self-heal: schema CREATE is IF NOT EXISTS, so this is a
                # no-op when the file is intact and re-creates the table
                # if the file got wiped (e.g. AgentCore microVM cycle, or
                # a manual rm). Cheap (microseconds), bulletproof.
                conn.executescript(_SCHEMA)
                conn.execute(
                    "INSERT INTO traces "
                    "(job_id, agent_name, step, input, output, duration_ms, timestamp, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        job_id,
                        agent_name,
                        step,
                        json.dumps(input_data, default=str),
                        json.dumps(output_data, default=str),
                        duration_ms,
                        datetime.now(timezone.utc).isoformat(),
                        status,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    def make_strands_hook(self, job_id: str):
        """Return a Strands HookProvider that logs tool + model calls to this
        TraceLogger under the given job_id, matching the row shape that
        ManualSupervisor writes via _step().
        """
        return _StrandsTraceHook(self, job_id)

    def get_traces(self, job_id: str) -> list[dict]:
        """Read traces from this worker's file only. For cross-worker reads
        use shared.trace_reader.read_traces."""
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                "SELECT id, job_id, agent_name, step, input, output, "
                "duration_ms, timestamp, status "
                "FROM traces WHERE job_id = ? ORDER BY id",
                (job_id,),
            )
            rows = cur.fetchall()
        finally:
            conn.close()

        return [
            {
                "id": r[0],
                "job_id": r[1],
                "agent_name": r[2],
                "step": r[3],
                "input": json.loads(r[4]) if r[4] else None,
                "output": json.loads(r[5]) if r[5] else None,
                "duration_ms": r[6],
                "timestamp": r[7],
                "status": r[8],
            }
            for r in rows
        ]
