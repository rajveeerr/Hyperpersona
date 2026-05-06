"""Pretty-print agent trace rows for a job.

Usage: make show-trace JOB=<job_id>

Reads SQLite trace files written by workers. With multiple workers, each
writes its own file in TRACES_DB_DIR — this script reads across all of
them.
"""

import json
import os
import sys

from shared.trace_reader import read_traces


def main() -> None:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("usage: show_trace.py <job_id>")
        sys.exit(1)

    job_id = sys.argv[1].strip()
    db_dir = os.getenv("TRACES_DB_DIR", "/app/traces")
    rows = read_traces(db_dir, job_id)

    if not rows:
        print(f"no trace rows for job {job_id}")
        return

    print(f"job {job_id} — {len(rows)} step(s)")
    print()
    for row in rows:
        ts = row["timestamp"]
        agent = row["agent_name"]
        step = row["step"]
        dur = row["duration_ms"] or 0.0
        status = row["status"]
        print(f"  {ts}  {agent:11} {step:20} {dur:7.1f}ms  {status}")
        if row["input"]:
            print(f"      in:  {json.dumps(row['input'])[:140]}")
        if row["output"]:
            print(f"      out: {json.dumps(row['output'])[:200]}")


if __name__ == "__main__":
    main()
