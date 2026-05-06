"""Multi-worker throughput demo (Step 5).

Sends a fixed batch of high-signal events (each runs the full supervisor,
so worker time is the bottleneck) and times how long until every job
reaches status=completed. Run it with different worker counts to see the
near-linear speedup.

Usage:
    make scale N=1
    make demo-scale       # baseline
    make scale N=4
    make demo-scale       # ~4x faster

Why high-signal: tiered cheap-store events finish in milliseconds and
wouldn't show worker bottleneck. Purchases/searches each go through
privacy → analyzer → Bedrock embed × M → vector upserts, which is what
real load looks like.

Why 4 customers: dodges the per-customer rate limit (default 100/min)
and exercises fairness — each worker can pick up any customer's job.
"""

import json
import os
import time
import urllib.error
import urllib.request
import uuid

BASE_URL = os.getenv("HYPERPERSONA_BASE_URL", "http://server:8000")
API_KEY = os.getenv("API_KEY", "test-key")

CUSTOMERS = [f"demo_scale_{i}" for i in range(4)]
EVENTS_PER_CUSTOMER = 10           # 4 × 10 = 40 events total
TIMEOUT_S = 120                    # plenty for 1 worker; way more than enough for many


def _api(method: str, path: str, body: dict | None = None) -> tuple[int, dict | None]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, method=method, data=data)
    req.add_header("X-API-Key", API_KEY)
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = resp.read().decode() or "null"
            return resp.status, json.loads(text)
    except urllib.error.HTTPError as e:
        text = e.read().decode() or "null"
        try:
            return e.code, json.loads(text)
        except json.JSONDecodeError:
            return e.code, {"raw": text}


def _section(title: str) -> None:
    print()
    print("=" * 64)
    print(title)
    print("=" * 64)


def main() -> None:
    # Cleanup leftover state
    for cid in CUSTOMERS:
        _api("DELETE", f"/customer/{cid}")

    _section("0. SETUP — consent for 4 customers")
    for cid in CUSTOMERS:
        _api("POST", "/consent", {
            "customer_id": cid,
            "scopes": ["personalization", "analytics"],
        })
    print(f"created consent for {len(CUSTOMERS)} customers")

    # Build the batch: 40 high-signal events (10 per customer)
    event_types = ["search", "add_to_cart", "purchase", "return"]
    batch_events = []
    for cid in CUSTOMERS:
        for i in range(EVENTS_PER_CUSTOMER):
            batch_events.append({
                "customer_id": cid,
                "client_event_id": str(uuid.uuid4()),
                "event_type": event_types[i % len(event_types)],
                "payload": {"i": i, "test": "scale"},
            })
    total = len(batch_events)

    _section(f"1. BURST {total} HIGH-SIGNAL EVENTS")
    s, b = _api("POST", "/events/batch", {"events": batch_events})
    print(f"POST /events/batch ({total}) → {s}  accepted={b.get('accepted')}")
    job_ids = [
        r["job_id"] for r in (b.get("results") or [])
        if r.get("status") == "queued"
    ]
    if not job_ids:
        print("no jobs queued — abort")
        return

    _section("2. POLL UNTIL ALL JOBS COMPLETE")
    t0 = time.time()
    completed: set[str] = set()
    failed: set[str] = set()
    last_progress = -1

    while time.time() - t0 < TIMEOUT_S:
        for jid in job_ids:
            if jid in completed or jid in failed:
                continue
            s, b = _api("GET", f"/jobs/{jid}")
            if s == 200 and b:
                if b.get("status") == "completed":
                    completed.add(jid)
                elif b.get("status") == "failed":
                    failed.add(jid)

        progress = len(completed) + len(failed)
        if progress != last_progress:
            elapsed = time.time() - t0
            print(f"  t={elapsed:5.1f}s  completed={len(completed):3d}/{total}  "
                  f"failed={len(failed)}  in_flight={total - progress}")
            last_progress = progress

        if progress >= total:
            break

        time.sleep(1)

    duration = time.time() - t0

    _section("3. RESULT")
    print(f"total events     : {total}")
    print(f"completed        : {len(completed)}")
    print(f"failed           : {len(failed)}")
    print(f"wall-clock time  : {duration:.1f}s")
    if duration > 0 and len(completed) > 0:
        throughput = len(completed) / duration
        print(f"throughput       : {throughput:.2f} events/sec")

    _section("4. CLEANUP")
    for cid in CUSTOMERS:
        _api("DELETE", f"/customer/{cid}")
    print(f"deleted {len(CUSTOMERS)} customers")

    print()
    print("Tip: run this with different worker counts to see the speedup:")
    print("  make scale N=1 && make demo-scale")
    print("  make scale N=4 && make demo-scale")
    print("  make scale N=8 && make demo-scale")


if __name__ == "__main__":
    main()
