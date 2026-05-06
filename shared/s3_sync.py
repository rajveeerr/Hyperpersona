"""SQLite trace sync to S3 with two implementations behind a Protocol.

  - NoopTraceSync   does nothing. Default. Trace files stay local on the
                    shared docker volume.
  - S3TraceSync     after each job, snapshots the worker's SQLite file
                    and uploads it to s3://bucket/traces/YYYY/MM/DD/
                    job_{job_id}_{hostname}_{ts}.db. The fetch_for_job
                    method is what the server's /traces route calls when
                    the local glob comes back empty (e.g. after worker
                    restart, or in AgentCore microVM mode where the
                    filesystem is ephemeral).

Use make_trace_sync(mode, bucket, region) to build the right one.
"""

from __future__ import annotations

import logging
import os
import shutil
import socket
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Protocol

log = logging.getLogger(__name__)


class TraceSync(Protocol):
    def sync(self, db_path: str, job_id: str) -> str | None: ...
    def fetch_for_job(self, job_id: str, dest_dir: str) -> list[str]: ...


# --- Noop ---------------------------------------------------------------


class NoopTraceSync:
    """Default. Local SQLite is the only store; no upload, no fetch."""

    def sync(self, db_path: str, job_id: str) -> str | None:
        return None

    def fetch_for_job(self, job_id: str, dest_dir: str) -> list[str]:
        return []


# --- S3 -----------------------------------------------------------------


class S3TraceSync:
    """Snapshot + upload after each job; list + download on lookup miss.

    Lookups list the last 7 daily prefixes and pull any object whose key
    contains `job_{job_id}`. Hackathon-scale; for production, store the
    job_id → s3_key mapping in DynamoDB jobs table to avoid the LIST.
    """

    LOOKUP_DAYS = 7

    def __init__(self, bucket: str, region: str = "us-east-1", prefix: str = "traces/") -> None:
        import boto3
        self.s3 = boto3.client("s3", region_name=region)
        self.bucket = bucket
        self.prefix = prefix
        self.region = region

    def sync(self, db_path: str, job_id: str) -> str | None:
        if not os.path.exists(db_path):
            # Not a sync error — the trace file just doesn't exist yet.
            # Different from "AWS rejected my upload"; don't raise.
            log.info("trace_sync: db_path %s missing — nothing to upload", db_path)
            return None

        # Snapshot to a temp file so the upload sees a consistent file even
        # if another job lands and writes to the live SQLite during upload.
        # AWS errors propagate; the daemon-thread wrapper in job_handler
        # logs.exception so failure is visible without failing the job.
        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
                tmp_path = tmp.name
            shutil.copy2(db_path, tmp_path)

            now = datetime.now(timezone.utc)
            hostname = os.environ.get("HOSTNAME") or socket.gethostname() or "unknown"
            hostname_safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in hostname)
            key = (
                f"{self.prefix}{now.strftime('%Y/%m/%d')}/"
                f"job_{job_id}_{hostname_safe}_{int(now.timestamp())}.db"
            )
            self.s3.upload_file(tmp_path, self.bucket, key)
            log.info("trace_sync: uploaded %s → s3://%s/%s",
                     os.path.basename(db_path), self.bucket, key)
            return key
        finally:
            # Clean up temp file regardless of success/failure.
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def fetch_for_job(self, job_id: str, dest_dir: str) -> list[str]:
        os.makedirs(dest_dir, exist_ok=True)
        downloaded: list[str] = []
        marker = f"job_{job_id}_"
        now = datetime.now(timezone.utc)

        # AWS errors propagate. An empty prefix returns an empty Contents
        # list (no error), so any exception here is a real AWS failure
        # the caller needs to know about.
        for offset in range(self.LOOKUP_DAYS):
            day = now - timedelta(days=offset)
            day_prefix = f"{self.prefix}{day.strftime('%Y/%m/%d')}/"
            resp = self.s3.list_objects_v2(Bucket=self.bucket, Prefix=day_prefix)
            for obj in resp.get("Contents", []) or []:
                key = obj["Key"]
                if marker not in key:
                    continue
                # Rename to the agent_traces_ prefix so trace_reader's
                # glob ("agent_traces_*.db") picks it up. We strip the
                # ".db" then re-add to keep the suffix.
                base = os.path.basename(key)
                local_name = f"agent_traces_s3_{base.removesuffix('.db')}.db"
                local = os.path.join(dest_dir, local_name)
                self.s3.download_file(self.bucket, key, local)
                downloaded.append(local)
        if downloaded:
            log.info("trace_sync: fetched %d file(s) for job=%s", len(downloaded), job_id)
        return downloaded


# --- Factory ------------------------------------------------------------


def make_trace_sync(mode: str, bucket: str = "", region: str = "us-east-1") -> TraceSync:
    if mode == "local":
        log.info("TraceSync: local (noop)")
        return NoopTraceSync()
    if mode == "s3":
        if not bucket:
            raise ValueError("TRACE_SYNC_MODE=s3 requires S3_TRACES_BUCKET to be set")
        log.info("TraceSync: s3 (bucket=%s region=%s)", bucket, region)
        return S3TraceSync(bucket=bucket, region=region)
    raise ValueError(f"Unknown TRACE_SYNC_MODE: {mode!r} (expected 'local' or 's3')")
