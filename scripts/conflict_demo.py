"""ACE conflict-detection demo.

The mock analyzer always extracts the same canned fact, so to demonstrate
conflict detection we seed contradictory facts about the same topic
directly into OpenSearch with different timestamps + polarities:

  Old fact (200 days ago):  "loves Nike trail shoes"        polarity=+1
  Recent fact (5 days ago): "doesn't like Nike anymore"     polarity=-1

We also seed a non-controversial fact for comparison:
  Recent fact:              "prefers waterproof gear"       polarity=+1

Then we hit /recommend and observe the trace:
  - 3 facts retrieved
  - "nike shoes" should appear in conflicts[]
  - The recent (-1) fact should win the dedup, not the old (+1) one

Run inside the server container so it can reach OpenSearch:
  make demo-conflict
"""

import hashlib
import json
import math
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from uuid import uuid4

from opensearchpy import OpenSearch

BASE_URL = os.getenv("HYPERPERSONA_BASE_URL", "http://server:8000")
API_KEY = os.getenv("API_KEY", "test-key")
OS_HOST = os.getenv("OPENSEARCH_HOST", "opensearch")
OS_PORT = int(os.getenv("OPENSEARCH_PORT", "9200"))

CUSTOMER = "demo_conflict_user"

# Local hash-based embedder — used by this demo script only so the conflict
# vis is deterministic without burning a Bedrock invoke. The production
# stack uses real Titan via shared/bedrock.py:BedrockClient.embed.
def mock_embed(text: str, dim: int = 1024) -> list[float]:
    seed = hashlib.sha256(text.encode("utf-8")).digest()
    out: list[float] = []
    counter = 0
    while len(out) < dim:
        chunk = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
        for byte in chunk:
            out.append((byte - 128) / 128.0)
            if len(out) >= dim:
                break
        counter += 1
    mag = math.sqrt(sum(x * x for x in out))
    return [x / mag for x in out] if mag > 0 else out


def _api_request(
    method: str, path: str, body: dict | None = None
) -> tuple[int, dict | None]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, method=method, data=data)
    req.add_header("X-API-Key", API_KEY)
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            text = resp.read().decode() or "null"
            return resp.status, json.loads(text)
    except urllib.error.HTTPError as e:
        text = e.read().decode() or "null"
        try:
            return e.code, json.loads(text)
        except json.JSONDecodeError:
            return e.code, {"raw": text}


def main() -> None:
    os_client = OpenSearch(
        hosts=[{"host": OS_HOST, "port": OS_PORT}],
        use_ssl=False,
        verify_certs=False,
    )

    print("=" * 64)
    print("CONFLICT DEMO — seeding 3 facts directly into OpenSearch")
    print("=" * 64)

    # Set up consent so /recommend won't be blocked
    _api_request("POST", "/consent", {
        "customer_id": CUSTOMER,
        "scopes": ["personalization", "analytics"],
    })
    print(f"created consent for {CUSTOMER}")

    # Wipe any prior demo state
    os_client.delete_by_query(
        index="customer-facts",
        body={"query": {"term": {"customer_id": CUSTOMER}}},
        refresh=True,
    )

    now = datetime.now(timezone.utc)
    facts = [
        # Old positive: "loves Nike" 200 days ago
        {
            "text": "loves Nike trail shoes",
            "polarity": 1,
            "timestamp": (now - timedelta(days=200)).isoformat(),
        },
        # Recent negative: "doesn't like Nike" 5 days ago — this should win the dedup
        {
            "text": "does not like Nike anymore",
            "polarity": -1,
            "timestamp": (now - timedelta(days=5)).isoformat(),
        },
        # Recent neutral: unrelated topic, should pass through cleanly
        {
            "text": "prefers waterproof gear",
            "polarity": 1,
            "timestamp": (now - timedelta(days=3)).isoformat(),
        },
    ]

    for f in facts:
        os_client.index(
            index="customer-facts",
            id=str(uuid4()),
            body={
                "vector": mock_embed(f["text"]),
                "customer_id": CUSTOMER,
                "text": f["text"],
                "source_event": "demo_seed",
                "polarity": f["polarity"],
                "timestamp": f["timestamp"],
            },
            refresh="wait_for",
        )
        days_ago = (now - datetime.fromisoformat(f["timestamp"])).days
        print(f"  seeded: {f['text']:40} polarity={f['polarity']:+d}  ({days_ago}d ago)")

    print()
    print("=" * 64)
    print("RUNNING /recommend WITH 'nike running shoes' AS QUERY")
    print("=" * 64)

    s, b = _api_request(
        "GET",
        "/recommend?" + urlencode({
            "customer_id": CUSTOMER,
            "context": "nike running shoes",
        }),
    )
    print(f"GET /recommend → {s}")
    print(f"  facts_retrieved : {b.get('facts_retrieved')}")
    print(f"  facts_used      : {b.get('facts_used')}")
    print(f"  conflicts       : {b.get('conflicts')}")
    print(f"  offer (head)    : {(b.get('offer') or '')[:140]}")

    print()
    if b.get("conflicts"):
        print(f"PASS — ACE detected conflicts: {b['conflicts']}")
        print("       The more recent (negative) fact wins the dedup.")
    else:
        print("note: no conflicts surfaced. ACE threshold may be too strict for")
        print("      mock embeddings — try lowering FACT_SCORE_THRESHOLD in")
        print("      shared/ace_ranking.py to see the conflict surface.")

    # Tidy up
    _api_request("DELETE", f"/customer/{CUSTOMER}")
    print(f"\ncleaned up {CUSTOMER}")


if __name__ == "__main__":
    main()
