"""End-to-end smoke for the supervisor.

Seeds consent, enqueues a process_event job, waits for completion, and
prints the trace. Works against whatever SUPERVISOR_MODE the worker is
running — same script for manual and strands.

Usage:
    docker compose exec worker python /app/scripts/test_supervisor.py
"""

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone

sys.path.insert(0, "/app")

from shared.dynamo import DynamoClient  # noqa: E402
from shared.queue import make_job_queue, make_redis  # noqa: E402
from shared.schemas import Job  # noqa: E402
from shared.trace_reader import read_traces  # noqa: E402


REGION = os.getenv("AWS_REGION", "us-east-1")
DDB_ENDPOINT = os.getenv("DYNAMODB_ENDPOINT", "http://dynamodb-local:8000")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
TRACES_DIR = os.getenv("TRACES_DB_DIR", "/app/traces")


def main() -> int:
    mode = os.getenv("SUPERVISOR_MODE", "manual")
    print(f"=== SUPERVISOR SMOKE (mode={mode}) ===\n")

    dynamo = DynamoClient(endpoint=DDB_ENDPOINT, region=REGION)
    redis_client = make_redis(REDIS_URL)
    queue = make_job_queue(
        mode=os.getenv("QUEUE_MODE", "redis"),
        redis_client=redis_client,
        sqs_queue_url=os.getenv("SQS_QUEUE_URL", ""),
        region=REGION,
    )

    cust = f"cust_sup_{uuid.uuid4().hex[:8]}"
    event_id = str(uuid.uuid4())

    # Seed consent
    dynamo.put_consent({
        "customer_id": cust,
        "scopes": ["personalization", "analytics"],
        "data_retention_days": 90,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    })

    # Write event + enqueue job
    now = datetime.now(timezone.utc).isoformat()
    event = {
        "customer_id": cust,
        "event_id": event_id,
        "event_type": "purchase",
        "payload": {"product": "Salomon X Ultra trail running shoes", "price": 159},
        "status": "pending",
        "consent_scope": ["personalization"],
        "created_at": now,
    }
    dynamo.put_event(event)

    job = Job(job_type="process_event", payload={"customer_id": cust, "event_id": event_id})
    dynamo.put_job(job.model_dump())
    queue.push_one(job.model_dump_json())
    job_id = job.job_id

    print(f"customer_id : {cust}")
    print(f"event_id    : {event_id}")
    print(f"job_id      : {job_id}")
    print()

    # Wait for completion
    print("waiting for worker...")
    final_status = None
    for _ in range(90):
        e = dynamo.get_event(cust, event_id)
        if e and e.get("status") in ("processed", "failed"):
            final_status = e.get("status")
            break
        time.sleep(1)

    if final_status is None:
        print("TIMEOUT — event still pending after 90s")
        return 1

    print(f"event status: {final_status}\n")

    # Show trace
    rows = read_traces(TRACES_DIR, job_id)
    print(f"--- TRACE ({len(rows)} rows) ---")
    for r in rows:
        agent = r["agent_name"]
        step = r["step"]
        dur = r.get("duration_ms") or 0.0
        status = r["status"]
        out = r.get("output") or {}
        # Brief output preview
        if isinstance(out, dict):
            preview_keys = ("allowed", "reason", "facts_extracted", "status", "error", "mode")
            preview = {k: out[k] for k in preview_keys if k in out}
        else:
            preview = str(out)[:80]
        print(f"  {agent:<12} {step:<22} {dur:>7.0f}ms {status:<5} {json.dumps(preview, default=str)[:120]}")

    if final_status != "processed":
        print(f"\nFAIL — expected processed, got {final_status}")
        return 1

    # Mode-specific trace assertions:
    #  - manual:    privacy + analyzer rows (steps run in-process)
    #  - strands:   check_privacy_tool + analyze_behavior_tool rows (Strands @tool names)
    #  - agentcore: agentcore invoke_agent_runtime row (steps run in the
    #               microVM and aren't visible in our local trace)
    if mode == "agentcore":
        has_invoke = any(
            r["agent_name"] == "agentcore" and r["step"] == "invoke_agent_runtime"
            for r in rows
        )
        if not has_invoke:
            print("\nFAIL — no agentcore invoke_agent_runtime row in trace")
            return 1
    else:
        has_privacy = any(r["agent_name"] in ("privacy", "check_privacy_tool") for r in rows)
        has_analyzer = any(r["agent_name"] in ("analyzer", "analyze_behavior_tool") for r in rows)
        if not has_privacy:
            print("\nFAIL — no privacy step in trace")
            return 1
        if not has_analyzer:
            print("\nFAIL — no analyzer step in trace")
            return 1

    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
