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
