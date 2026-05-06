"""Tiered processing demo (Step 2 of the scaling plan).

Sends 7 events for one customer:
  - 4 high-signal: search, add_to_cart, purchase, return
  - 3 low-signal:  page_view × 3 (would be 50+ in real traffic)
  Threshold = 3 → the 3rd page_view auto-fires summarize_session,
  which rolls all three cheap events into one OpenSearch summary doc.

Verifies after processing:
  - High-signal events have status "processed" (full supervisor ran)
  - Low-signal events have status "processed_cheap" or "aggregated"
  - At least one summary doc lives in OpenSearch session-summaries

That's the cost lever made visible: the full Bedrock pipeline only fires
on high-value events; everything else gets rolled up cheap.

REQUIRES the worker to run with EVENT_PROCESSING_MODE=tiered. Default
mode is "full" (every event runs the supervisor — max accuracy). To
flip on tiered for the demo:

    EVENT_PROCESSING_MODE=tiered docker compose up -d --force-recreate worker
    make demo-tiered

This script auto-detects the mode after sending events and prints a
friendly message if tiered is OFF, instead of failing.

Usage: make demo-tiered
"""

import json
import os
import time
import urllib.error
import urllib.request
import uuid

import boto3
from boto3.dynamodb.conditions import Key
from opensearchpy import OpenSearch

BASE_URL = os.getenv("HYPERPERSONA_BASE_URL", "http://server:8000")
API_KEY = os.getenv("API_KEY", "test-key")
DDB_ENDPOINT = os.getenv("DYNAMODB_ENDPOINT", "http://dynamodb-local:8000")
REGION = os.getenv("AWS_REGION", "us-east-1")
OS_HOST = os.getenv("OPENSEARCH_HOST", "opensearch")
OS_PORT = int(os.getenv("OPENSEARCH_PORT", "9200"))

CUSTOMER = "demo_tiered_user"


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
    dynamodb = boto3.resource("dynamodb", endpoint_url=DDB_ENDPOINT, region_name=REGION)
    os_client = OpenSearch(
        hosts=[{"host": OS_HOST, "port": OS_PORT}],
        use_ssl=False,
        verify_certs=False,
    )

    # Self-clean leftover state
    _api("DELETE", f"/customer/{CUSTOMER}")

    _section("1. CONSENT")
    s, b = _api("POST", "/consent", {
        "customer_id": CUSTOMER,
        "scopes": ["personalization", "analytics"],
    })
    print(f"POST /consent → {s}")

    _section("2. INGEST 7 MIXED EVENTS (4 high-signal, 3 low-signal)")
    events = [
        ("search",      {"query": "trail running shoes"}),    # high
        ("page_view",   {"page": "/shoes/listing"}),           # low
        ("page_view",   {"page": "/shoes/salomon-x-ultra"}),   # low
        ("page_view",   {"page": "/shoes/merrell-moab"}),      # low — trips threshold
        ("add_to_cart", {"product": "Salomon X Ultra"}),       # high
        ("purchase",    {"product": "Salomon X Ultra"}),       # high
        ("return",      {"product": "Wrong Size"}),            # high
    ]
    batch = {
        "events": [
            {
                "customer_id": CUSTOMER,
                "client_event_id": str(uuid.uuid4()),
                "event_type": evt_type,
                "payload": payload,
            }
            for evt_type, payload in events
        ]
    }
    s, b = _api("POST", "/events/batch", batch)
    print(f"POST /events/batch ({len(events)}) → {s}  accepted={b.get('accepted')}")

    print()
    print("waiting 14s for worker to process all events + run summarize_session...")
    time.sleep(14)

    _section("3. EVENT STATUS BREAKDOWN")
    items = dynamodb.Table("customer_events").query(
        KeyConditionExpression=Key("PK").eq(f"CUSTOMER#{CUSTOMER}"),
    ).get("Items", [])

    by_status: dict[str, list[str]] = {}
    for item in items:
        st = item.get("status", "?")
        by_status.setdefault(st, []).append(item.get("event_type", "?"))

    print(f"total events in DDB: {len(items)} (expect 7)")
    for st, evt_types in sorted(by_status.items()):
        print(f"  {st:18}: {len(evt_types)}  {evt_types}")

    processed = len(by_status.get("processed", []))
    cheap_or_agg = (
        len(by_status.get("processed_cheap", []))
        + len(by_status.get("aggregated", []))
    )

    print()
    print(f"  high-signal → supervisor ran: {processed} (expect 4)")
    print(f"  low-signal  → cheap path:     {cheap_or_agg} (expect 3)")

    # Auto-detect mode: if all 7 events ran supervisor, tiered is OFF.
    if processed == 7 and cheap_or_agg == 0:
        print()
        print("=" * 64)
        print("TIERED MODE IS OFF — demo cannot demonstrate the cheap path.")
        print("=" * 64)
        print("All 7 events ran the full supervisor. To enable tiered mode:")
        print("  EVENT_PROCESSING_MODE=tiered docker compose up -d --force-recreate worker")
        print("  make demo-tiered")
        _api("DELETE", f"/customer/{CUSTOMER}")
        print(f"\ncleaned up {CUSTOMER}")
        return

    _section("4. OPENSEARCH session-summaries")
    summaries = os_client.search(
        index="session-summaries",
        body={"size": 50, "query": {"term": {"customer_id": CUSTOMER}}},
    )["hits"]["hits"]
    print(f"summary docs for {CUSTOMER}: {len(summaries)}")
    for hit in summaries:
        src = hit["_source"]
        print(f"  id={hit['_id']}  events={src.get('event_count')}")
        print(f"  text: {src.get('text', '')[:120]}")

    _section("5. RECOMMEND — verify summaries are read at recommend time")
    from urllib.parse import urlencode
    s, b = _api(
        "GET",
        "/recommend?" + urlencode({
            "customer_id": CUSTOMER,
            "context": "looking for hiking gear",
        }),
    )
    print(f"GET /recommend → {s}")
    print(f"  facts_used      : {b.get('facts_used')}")
    print(f"  behaviors_used  : {b.get('behaviors_used')}")
    print(f"  summaries_used  : {b.get('summaries_used')}  ← Step 2.5 plug")
    print(f"  offer (head)    : {(b.get('offer') or '')[:120]}")
    summaries_used = b.get("summaries_used") or 0

    _section("6. CLEANUP")
    s, b = _api("DELETE", f"/customer/{CUSTOMER}")
    print(f"DELETE /customer/{CUSTOMER} → {s}  {b}")

    print()
    if processed == 4 and cheap_or_agg == 3 and len(summaries) >= 1 and summaries_used >= 1:
        print("PASS — tiered processing + summary retrieval verified")
        print("       4 high-signal events ran the supervisor (Bedrock-heavy)")
        print(f"       3 low-signal events were cheap-stored and rolled up")
        print(f"       into {len(summaries)} session summary (1 Bedrock embed total)")
        print(f"       Recommender pulled in {summaries_used} summary at recommend time")
    else:
        print("note: counts didn't line up — see breakdown above")


if __name__ == "__main__":
    main()
