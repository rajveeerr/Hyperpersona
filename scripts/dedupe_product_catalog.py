"""De-duplicate the AOSS `product-catalog` index by slug.

Why this script exists:
  AOSS VECTORSEARCH collections reject client-supplied document IDs, so
  every call to `client.index()` creates a NEW doc with an auto-generated
  `_id` — even when the metadata.slug is identical to an existing one.
  Re-running `make seed-products` therefore doubles (or triples) the
  index size every time. Recommend / KNN dedup downstream by slug, so
  user-facing behaviour is unaffected, but the index is wasteful and
  the duplicates inflate every search response.

Strategy (safe, lossless):
  1. Page through every doc keeping only `_id` + `_source.slug` +
     a creation-order proxy (`_id` lexicographic order — AOSS ids are
     time-encoded so later ids sort higher).
  2. Group by slug. For each group with >1 doc, KEEP the doc with the
     highest `_id` (i.e. the most recently written) and add the rest
     to a delete list.
  3. Bulk-delete the duplicates in chunks via the OpenSearch bulk API.
  4. Verify total count == unique slug count.

Idempotent: a second run is a no-op (no duplicates left to remove).

Run via:  .venv/bin/python scripts/dedupe_product_catalog.py
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from opensearchpy.helpers import bulk
from opensearchpy.helpers.signer import RequestsAWSV4SignerAuth


COLLECTION = "product-catalog"
ENDPOINT = os.environ.get("AOSS_ENDPOINT", "https://eja7umnxrfag2z06acbd.us-east-1.aoss.amazonaws.com").replace("https://", "")
REGION = os.environ.get("AWS_REGION", "us-east-1")


def _client() -> OpenSearch:
    creds = boto3.Session().get_credentials()
    if creds is None:
        sys.exit("error: no AWS credentials in env (source /tmp/aws_session.sh)")
    return OpenSearch(
        hosts=[{"host": ENDPOINT, "port": 443}],
        http_auth=RequestsAWSV4SignerAuth(creds, REGION, "aoss"),
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=60,
    )


def _scan_all(client: OpenSearch) -> list[tuple[str, str]]:
    """Yield (id, slug) for every doc in the collection. AOSS doesn't
    support the `_scroll` API, so we page with `search_after` over `_id`."""
    out: list[tuple[str, str]] = []
    search_after: list | None = None
    while True:
        body: dict = {
            "size": 1000,
            "sort": [{"_id": "asc"}],
            "_source": ["slug"],
        }
        if search_after:
            body["search_after"] = search_after
        resp = client.search(index=COLLECTION, body=body)
        hits = resp["hits"]["hits"]
        if not hits:
            break
        for h in hits:
            slug = (h.get("_source") or {}).get("slug")
            if slug:
                out.append((h["_id"], slug))
        search_after = hits[-1]["sort"]
        if len(hits) < 1000:
            break
    return out


def main() -> None:
    client = _client()
    print(f"reading {COLLECTION!r} via {ENDPOINT!r}...")
    pairs = _scan_all(client)
    print(f"  scanned {len(pairs)} docs")

    by_slug: dict[str, list[str]] = defaultdict(list)
    for doc_id, slug in pairs:
        by_slug[slug].append(doc_id)

    print(f"  unique slugs: {len(by_slug)}")
    extras = sum(len(ids) - 1 for ids in by_slug.values() if len(ids) > 1)
    print(f"  duplicate docs to remove: {extras}")

    if extras == 0:
        print("nothing to dedupe — index is already clean.")
        return

    # For each slug, keep the doc with the lexicographically largest _id
    # (auto-ids on AOSS encode insertion time, so this is the freshest).
    delete_ids: list[str] = []
    for slug, ids in by_slug.items():
        if len(ids) <= 1:
            continue
        ids_sorted = sorted(ids)  # ascending → last is freshest
        keep = ids_sorted[-1]
        delete_ids.extend(ids_sorted[:-1])

    print(f"  deleting {len(delete_ids)} duplicate docs in bulk...")
    actions = (
        {"_op_type": "delete", "_index": COLLECTION, "_id": did}
        for did in delete_ids
    )
    success, errors = bulk(client, actions, raise_on_error=False, raise_on_exception=False)
    print(f"  bulk delete: {success} succeeded, {len(errors) if errors else 0} errored")
    if errors:
        for err in (errors if isinstance(errors, list) else [errors])[:5]:
            print(f"    sample err: {err}")

    # Verify
    resp = client.search(
        index=COLLECTION,
        body={"query": {"match_all": {}}, "size": 0, "track_total_hits": True},
    )
    final_total = resp["hits"]["total"]["value"]
    print(f"  final docs: {final_total}  (expected ≈ {len(by_slug)})")
    if final_total > len(by_slug) + 5:
        print("  WARNING: more docs than unique slugs — re-run dedupe.")


if __name__ == "__main__":
    main()
