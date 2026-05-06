"""Read agent traces across all worker SQLite files.

Each worker writes to its own file (agent_traces_{hostname}.db) so multiple
workers don't fight over a single SQLite lock. Readers (the server's
/traces route, the show_trace script) glob all files in the trace dir and
merge results.

Why a shared module: both server and worker (via show_trace.py) need to
read traces. The writer (TraceLogger) lives in worker/ because only
workers write.
"""

import glob
import json
import logging
import os
import sqlite3

log = logging.getLogger(__name__)


_QUERY = (
    "SELECT id, job_id, agent_name, step, input, output, "
    "duration_ms, timestamp, status "
    "FROM traces WHERE job_id = ? ORDER BY id"
)


def _list_db_files(db_dir: str) -> list[str]:
    return sorted(glob.glob(os.path.join(db_dir, "agent_traces_*.db")))


def read_traces(db_dir: str, job_id: str) -> list[dict]:
    """Return all trace rows for job_id across every worker's SQLite file.

    Sorted by timestamp so output order is consistent even if multiple
    workers contributed rows. Files that fail to open (locked, corrupt) are
    skipped with a warning rather than failing the whole query.
    """
    files = _list_db_files(db_dir)
    rows: list[dict] = []
    for db_path in files:
        try:
            conn = sqlite3.connect(db_path)
            try:
                cur = conn.execute(_QUERY, (job_id,))
                for r in cur.fetchall():
                    rows.append({
                        "id": r[0],
                        "job_id": r[1],
                        "agent_name": r[2],
                        "step": r[3],
                        "input": json.loads(r[4]) if r[4] else None,
                        "output": json.loads(r[5]) if r[5] else None,
                        "duration_ms": r[6],
                        "timestamp": r[7],
                        "status": r[8],
                    })
            finally:
                conn.close()
        except sqlite3.Error as e:
            log.warning("trace file %s unreadable, skipping: %s", db_path, e)
    rows.sort(key=lambda row: row["timestamp"])
    return rows


def trace_files_present(db_dir: str) -> bool:
    """True if any worker has written a trace file. Used by the route to
    distinguish 'no traces yet' (503) from 'job not found' (404)."""
    return bool(_list_db_files(db_dir))
