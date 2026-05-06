"""Trace lookup.

Reads SQLite trace files written by workers. Each worker owns its own
file (agent_traces_{hostname}.db) — the server globs them all and merges
the rows for a given job_id.

When TRACE_SYNC_MODE=s3 and the local glob comes back empty (e.g. after
worker restart, or in AgentCore microVM mode where the worker filesystem
is ephemeral), the route falls back to S3: it downloads any object whose
key contains job_{job_id} into a tempdir, then re-reads with the same
trace_reader.
"""

import logging
import tempfile

from fastapi import APIRouter, HTTPException

from shared.s3_sync import S3TraceSync
from shared.trace_reader import read_traces, trace_files_present

from ..config import settings


log = logging.getLogger(__name__)
router = APIRouter()


# Build the S3 fallback client lazily — only the first request that
# actually needs it pays the cost. Cached so we don't re-create per call.
_s3_sync: S3TraceSync | None = None


def _get_s3_sync() -> S3TraceSync | None:
    global _s3_sync
    if settings.trace_sync_mode != "s3" or not settings.s3_traces_bucket:
        return None
    if _s3_sync is None:
        _s3_sync = S3TraceSync(
            bucket=settings.s3_traces_bucket,
            region=settings.aws_region,
        )
    return _s3_sync


@router.get("/traces/{job_id}")
def get_traces(job_id: str) -> list:
    rows = []
    if trace_files_present(settings.traces_db_dir):
        rows = read_traces(settings.traces_db_dir, job_id)

    if not rows:
        # Fall back to S3 if configured.
        s3 = _get_s3_sync()
        if s3 is not None:
            with tempfile.TemporaryDirectory(prefix="traces-s3-") as tmp:
                downloaded = s3.fetch_for_job(job_id, tmp)
                if downloaded:
                    rows = read_traces(tmp, job_id)
                    log.info("traces: served %d row(s) for job=%s from S3 fallback",
                             len(rows), job_id)

    if not rows:
        if not trace_files_present(settings.traces_db_dir) and _get_s3_sync() is None:
            raise HTTPException(
                status_code=503,
                detail=f"no trace files in {settings.traces_db_dir}",
            )
        raise HTTPException(status_code=404, detail="no trace rows for job")
    return rows
