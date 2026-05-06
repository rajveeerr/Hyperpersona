"""Trace lookup.

Reads SQLite trace files written by workers. Each worker owns its own
file (agent_traces_{hostname}.db) — the server globs them all and merges
the rows for a given job_id.
"""

from fastapi import APIRouter, HTTPException

from shared.trace_reader import read_traces, trace_files_present

from ..config import settings


router = APIRouter()


@router.get("/traces/{job_id}")
def get_traces(job_id: str) -> list:
    if not trace_files_present(settings.traces_db_dir):
        raise HTTPException(
            status_code=503,
            detail=f"no trace files in {settings.traces_db_dir}",
        )

    rows = read_traces(settings.traces_db_dir, job_id)
    if not rows:
        raise HTTPException(status_code=404, detail="no trace rows for job")
    return rows
