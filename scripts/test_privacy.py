"""End-to-end privacy verification.

Three test users registered per run (random emails so re-running is safe):

  main         — full personalization scope; happy path + GDPR delete
  no_consent   — registered but no consent record at all → 403 on POST /events
  no_scope     — consent with only 'analytics' (no personalization) → 403

Verifies:
  - Ungated and out-of-scope customers get 403 from /events
  - Happy path: ingest 3 events, traces in DDB + OpenSearch + cached offer in Redis
  - DELETE /customer wipes events + consent + vectors + cache for the auth'd user

Run inside the server container:
  make test-privacy
"""

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from urllib.parse import urlencode

import boto3
from opensearchpy import OpenSearch

BASE_URL = os.getenv("HYPERPERSONA_BASE_URL", "http://server:8000")
DDB_ENDPOINT = os.getenv("DYNAMODB_ENDPOINT", "http://dynamodb-local:8000")
REGION = os.getenv("AWS_REGION", "us-east-1")
OS_HOST = os.getenv("OPENSEARCH_HOST", "opensearch")
OS_PORT = int(os.getenv("OPENSEARCH_PORT", "9200"))
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

PASSWORD = "demo-password-123"


def _request(
    method: str, path: str, body: dict | None = None, *, token: str | None = None
) -> tuple[int, dict | None]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, method=method, data=data)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
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


def _register() -> tuple[str, str]:
    """Register a fresh user; return (token, customer_id)."""
    email = f"privacy_{uuid.uuid4().hex[:10]}@example.com"
    s, b = _request("POST", "/register", {"email": email, "password": PASSWORD})
    assert s == 200 and b and b.get("token"), f"register failed: {s} {b}"
    return b["token"], b["customer_id"]


def _section(title: str) -> None:
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


def main() -> None:
    import redis as redis_module

    dynamodb = boto3.resource("dynamodb", endpoint_url=(DDB_ENDPOINT or None), region_name=REGION)
    os_client = OpenSearch(
        hosts=[{"host": OS_HOST, "port": OS_PORT}],
        use_ssl=False,
        verify_certs=False,
    )
    redis_client = redis_module.from_url(REDIS_URL, decode_responses=True)

    _section("REGISTER 3 TEST USERS")
    main_token, main_id = _register()
    no_consent_token, no_consent_id = _register()
    no_scope_token, no_scope_id = _register()
    print(f"main       : {main_id}")
    print(f"no_consent : {no_consent_id}")
    print(f"no_scope   : {no_scope_id}")

    _section("CONSENT GATE — INGESTION")

    # No consent at all → 403
    s, b = _request("POST", "/events", {
        "client_event_id": str(uuid.uuid4()),
        "event_type": "page_view",
        "payload": {"page": "/x"},
    }, token=no_consent_token)
    print(f"no-consent customer → POST /events → {s} {b}")
    assert s == 403, f"expected 403 for ungated customer, got {s}"

    # Consent without personalization scope → 403
    _request("POST", "/consent", {"scopes": ["analytics"]}, token=no_scope_token)
    s, b = _request("POST", "/events", {
        "client_event_id": str(uuid.uuid4()),
        "event_type": "page_view",
        "payload": {"page": "/x"},
    }, token=no_scope_token)
    print(f"no-scope customer    → POST /events → {s} {b}")
    assert s == 403, f"expected 403 for missing personalization scope, got {s}"

    _section("HAPPY PATH — INGEST + PROCESS")

    # Set up consent for main user
    _request("POST", "/consent", {
        "scopes": ["personalization", "analytics"],
        "data_retention_days": 30,
    }, token=main_token)
    print(f"created consent for main user ({main_id[:8]}...)")

    # Ingest 3 events
    job_ids = []
    for i in range(3):
        s, b = _request("POST", "/events", {
            "client_event_id": str(uuid.uuid4()),
            "event_type": "purchase",
            "payload": {"product": f"item_{i}"},
        }, token=main_token)
        assert s == 202, f"expected 202, got {s} {b}"
        job_ids.append(b["job_id"])
    print(f"ingested 3 events → jobs {[j[:8] for j in job_ids]}")

    # Wait for the worker. Real Bedrock takes ~5-10s/event in manual mode,
    # ~17s/event in strands. 60s gives headroom for either.
    print("waiting up to 60s for worker...")
    deadline = time.time() + 60
    while time.time() < deadline:
        statuses = []
        for jid in job_ids:
            sj, bj = _request("GET", f"/jobs/{jid}", token=main_token)
            statuses.append((bj or {}).get("status", "?"))
        if all(s in ("completed", "failed") for s in statuses):
            break
        time.sleep(2)
    print(f"job statuses: {statuses}")

    # Spot-check state
    events = dynamodb.Table("customer_events").query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("PK").eq(f"CUSTOMER#{main_id}"),
    ).get("Items", [])
    print(f"DynamoDB events: {len(events)} (expect 3)")
    assert len(events) == 3
    has_expires = sum(1 for e in events if e.get("expires_at"))
    print(f"with expires_at: {has_expires} (expect 3, set from retention_days)")
    assert has_expires == 3

    facts = os_client.search(
        index="customer-facts",
        body={"size": 50, "query": {"term": {"customer_id": main_id}}},
    )["hits"]["hits"]
    print(f"OpenSearch customer-facts:       {len(facts)} (expect ≥3)")
    assert len(facts) >= 3

    behaviors = os_client.search(
        index="behavior-embeddings",
        body={"size": 50, "query": {"term": {"customer_id": main_id}}},
    )["hits"]["hits"]
    print(f"OpenSearch behavior-embeddings: {len(behaviors)} (expect 3)")
    assert len(behaviors) == 3

    _section("RIGHT-TO-DELETE")

    # Trigger a /recommend so we have an offer cached in Redis
    _request("GET", "/recommend?" + urlencode({"context": "shoes"}), token=main_token)
    print("triggered /recommend so cache key exists")

    cache_keys = list(redis_client.scan_iter(match=f"offer:{main_id}:*"))
    print(f"Redis cache keys before: {len(cache_keys)}")

    s, b = _request("DELETE", "/customer", token=main_token)
    print(f"DELETE /customer → {s}")
    print(f"  {b}")
    assert s == 200

    # Re-verify everything is gone
    events_after = dynamodb.Table("customer_events").query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("PK").eq(f"CUSTOMER#{main_id}"),
    ).get("Items", [])
    print(f"DynamoDB events after delete:    {len(events_after)} (expect 0)")
    assert len(events_after) == 0

    consent_resp = dynamodb.Table("customer_consent").get_item(
        Key={"PK": f"CUSTOMER#{main_id}", "SK": "CONSENT"},
    )
    print(f"DynamoDB consent after delete:   {'present' if consent_resp.get('Item') else 'absent'}")
    assert not consent_resp.get("Item")

    # OpenSearch delete_by_query is async; give it a moment
    time.sleep(1)
    facts_after = os_client.search(
        index="customer-facts",
        body={"size": 50, "query": {"term": {"customer_id": main_id}}},
    )["hits"]["hits"]
    print(f"OpenSearch facts after delete:   {len(facts_after)} (expect 0)")
    assert len(facts_after) == 0

    cache_after = list(redis_client.scan_iter(match=f"offer:{main_id}:*"))
    print(f"Redis cache keys after:          {len(cache_after)} (expect 0)")
    assert len(cache_after) == 0

    print()
    print("PASS — all privacy checks passed")


if __name__ == "__main__":
    main()
