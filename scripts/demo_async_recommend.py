"""Async /recommend demo (Step 6).

Fires N concurrent GET /recommend requests for distinct customers and
times each one + the wall-clock total. With the new async handler, all
N should run in parallel on the server's event loop — total ≈ slowest
individual request, not N × individual.

Old sync handler: each call pinned a uvicorn thread for up to 30s on
BRPOP. With FastAPI's default thread pool of ~40, ~40 concurrent
/recommend calls would starve every other endpoint.

Why distinct customers + unique contexts: bypasses the offer cache so
every request really hits the worker pipeline.

Usage: make demo-async-recommend
       (recommended: run with N=4 workers via `make scale N=4` first)
"""

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode

BASE_URL = os.getenv("HYPERPERSONA_BASE_URL", "http://server:8000")
API_KEY = os.getenv("API_KEY", "test-key")

CONCURRENCY = 10
CUSTOMERS = [f"demo_async_{i}" for i in range(CONCURRENCY)]


def _api(method: str, path: str, body: dict | None = None) -> tuple[int, dict | None, float]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, method=method, data=data)
    req.add_header("X-API-Key", API_KEY)
    if body:
        req.add_header("Content-Type", "application/json")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            text = resp.read().decode() or "null"
            return resp.status, json.loads(text), time.time() - t0
    except urllib.error.HTTPError as e:
        text = e.read().decode() or "null"
        try:
            return e.code, json.loads(text), time.time() - t0
        except json.JSONDecodeError:
            return e.code, {"raw": text}, time.time() - t0


def _section(title: str) -> None:
    print()
    print("=" * 64)
    print(title)
    print("=" * 64)


def _setup_customer(cid: str) -> str:
    """Consent + ingest 2 high-signal events. Returns the unique context."""
    _api("DELETE", f"/customer/{cid}")
    _api("POST", "/consent", {
        "customer_id": cid,
        "scopes": ["personalization", "analytics"],
    })
    batch = {"events": [
        {
            "customer_id": cid,
            "client_event_id": str(uuid.uuid4()),
            "event_type": "purchase",
            "payload": {"product": f"item_{cid}"},
        },
        {
            "customer_id": cid,
            "client_event_id": str(uuid.uuid4()),
            "event_type": "search",
            "payload": {"query": f"query_{cid}"},
        },
    ]}
    _api("POST", "/events/batch", batch)
    # Unique context per customer to dodge the offer cache
    return f"demo context for {cid} {uuid.uuid4()}"


def _do_recommend(customer_id: str, context: str) -> dict:
    qs = urlencode({"customer_id": customer_id, "context": context})
    s, b, dur = _api("GET", f"/recommend?{qs}")
    return {"customer_id": customer_id, "status": s, "duration": dur}


def main() -> None:
    _section("0. SETUP — consent + 2 events for each of 10 customers")
    contexts: dict[str, str] = {}
    for cid in CUSTOMERS:
        contexts[cid] = _setup_customer(cid)
    print(f"set up {len(CUSTOMERS)} customers")

    print()
    print("waiting 8s for worker(s) to process the 20 ingestion jobs...")
    time.sleep(8)

    _section(f"1. FIRE {CONCURRENCY} CONCURRENT /recommend REQUESTS")
    print("(distinct customers, unique contexts → no cache hits)")
    print()

    wall_t0 = time.time()
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = [
            pool.submit(_do_recommend, cid, contexts[cid])
            for cid in CUSTOMERS
        ]
        results = [f.result() for f in as_completed(futures)]
    wall_total = time.time() - wall_t0

    durations = sorted([r["duration"] for r in results])
    success = sum(1 for r in results if r["status"] == 200)

    print(f"  wall-clock total       : {wall_total:.2f}s")
    print(f"  successful responses   : {success}/{CONCURRENCY}")
    print(f"  per-request min        : {durations[0]:.2f}s")
    print(f"  per-request median     : {durations[len(durations)//2]:.2f}s")
    print(f"  per-request max        : {durations[-1]:.2f}s")
    sum_individual = sum(durations)
    print(f"  sum of individual times: {sum_individual:.2f}s")
    speedup = sum_individual / wall_total if wall_total > 0 else 0
    print(f"  effective parallelism  : {speedup:.1f}x  (1.0 = serial)")

    _section("2. CLEANUP")
    for cid in CUSTOMERS:
        _api("DELETE", f"/customer/{cid}")
    print(f"deleted {len(CUSTOMERS)} customers")

    print()
    if success == CONCURRENCY and speedup > 2.0:
        print("PASS — async /recommend stays parallel under concurrent load")
        print(f"       {CONCURRENCY} requests, {wall_total:.1f}s wall, "
              f"{sum_individual:.1f}s sum → {speedup:.1f}x parallelism")
        print("       (sync handler would have serialized to ~sum of individual)")
    else:
        print("note: counts/parallelism didn't line up — see numbers above")
        print("      (workers may be busy or queue may be backlogged)")


if __name__ == "__main__":
    main()
