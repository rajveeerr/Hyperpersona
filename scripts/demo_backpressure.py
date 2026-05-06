"""Backpressure + per-customer rate limit demo (Step 4).

Default config (see server/src/config.py):
  - max_events_per_customer_per_min = 100
  - max_queue_depth = 10000

Sequence:
  1. Show current /metrics/queue
  2. Send 100 events for customer A in one batch  → all 100 accepted
  3. Send 50 more events for customer A           → all rejected (cap hit)
  4. Send 10 events for customer B                → all accepted (separate bucket)
  5. Show /metrics/queue grew
  6. Cleanup

Usage: make demo-backpressure
"""

import json
import os
import urllib.error
import urllib.request
import uuid

BASE_URL = os.getenv("HYPERPERSONA_BASE_URL", "http://server:8000")
API_KEY = os.getenv("API_KEY", "test-key")

CUSTOMER_A = "demo_burst_a"
CUSTOMER_B = "demo_burst_b"


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


def _build_batch(customer_id: str, n: int, prefix: str) -> dict:
    return {
        "events": [
            {
                "customer_id": customer_id,
                "client_event_id": str(uuid.uuid4()),
                "event_type": "page_view",
                "payload": {"i": i, "prefix": prefix},
            }
            for i in range(n)
        ]
    }


def _count_by_status(results: list) -> dict:
    out: dict[str, int] = {}
    for r in results:
        st = r.get("status") + (
            f" ({r['reason']})" if r.get("reason") else ""
        )
        out[st] = out.get(st, 0) + 1
    return out


def main() -> None:
    # Self-clean any leftover state
    _api("DELETE", f"/customer/{CUSTOMER_A}")
    _api("DELETE", f"/customer/{CUSTOMER_B}")

    _section("0. CONSENT")
    for cid in (CUSTOMER_A, CUSTOMER_B):
        _api("POST", "/consent", {
            "customer_id": cid,
            "scopes": ["personalization", "analytics"],
        })
    print(f"created consent for {CUSTOMER_A} and {CUSTOMER_B}")

    _section("1. /metrics/queue (before)")
    s, b = _api("GET", "/metrics/queue")
    print(f"GET /metrics/queue → {s}  {b}")
    depth_before = b.get("queue_depth", 0)

    _section("2. BURST 100 EVENTS for customer A — all should be accepted")
    s, b = _api("POST", "/events/batch", _build_batch(CUSTOMER_A, 100, "first"))
    print(f"POST /events/batch (100) → {s}  accepted={b.get('accepted')}  rejected={b.get('rejected')}")
    print(f"   breakdown: {_count_by_status(b.get('results') or [])}")

    _section("3. BURST 50 MORE for customer A — should ALL be rate-limited")
    s, b = _api("POST", "/events/batch", _build_batch(CUSTOMER_A, 50, "second"))
    print(f"POST /events/batch (50)  → {s}  accepted={b.get('accepted')}  rejected={b.get('rejected')}")
    print(f"   breakdown: {_count_by_status(b.get('results') or [])}")
    a_second_accepted = b.get("accepted", 0)
    a_second_rejected = b.get("rejected", 0)

    _section("4. BURST 10 EVENTS for DIFFERENT customer B — should all pass")
    s, b = _api("POST", "/events/batch", _build_batch(CUSTOMER_B, 10, "b"))
    print(f"POST /events/batch (10)  → {s}  accepted={b.get('accepted')}  rejected={b.get('rejected')}")
    print(f"   breakdown: {_count_by_status(b.get('results') or [])}")
    b_accepted = b.get("accepted", 0)

    _section("5. /metrics/queue (after)")
    s, b = _api("GET", "/metrics/queue")
    print(f"GET /metrics/queue → {s}  {b}")
    depth_after = b.get("queue_depth", 0)

    _section("6. CLEANUP")
    for cid in (CUSTOMER_A, CUSTOMER_B):
        _api("DELETE", f"/customer/{cid}")
    print(f"deleted {CUSTOMER_A} and {CUSTOMER_B}")

    print()
    if a_second_accepted == 0 and a_second_rejected == 50 and b_accepted == 10:
        print("PASS — backpressure + per-customer rate limit verified")
        print(f"       customer A capped at 100/min; next 50 returned customer_rate_limit")
        print(f"       customer B unaffected (separate bucket): 10/10 accepted")
        print(f"       queue depth observed: {depth_before} → {depth_after}")
    else:
        print("note: counts didn't line up — see breakdown above")


if __name__ == "__main__":
    main()
