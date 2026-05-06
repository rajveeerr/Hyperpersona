"""Reconcile DynamoDB products against the OpenSearch product-catalog index.

For every product row in Dynamo:
  - If the matching OpenSearch document is missing OR its slug doesn't
    map back to a Dynamo row, re-embed and re-upsert via CatalogWriter.

Optional: --delete-orphans removes vectors that have no Dynamo row
(e.g. a product was deleted directly in Dynamo without going through
CatalogWriter).

Idempotent. Run after changing the embed text recipe in catalog_writer
or whenever you suspect drift between the two stores:

  make reconcile-products
  # or
  docker compose exec worker python /app/scripts/reconcile_products.py --delete-orphans
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from urllib.parse import unquote

sys.path.insert(0, "/app")

from shared.bedrock import make_bedrock_client  # noqa: E402
from shared.constants import COLLECTION_PRODUCTS  # noqa: E402
from shared.dynamo import DynamoClient  # noqa: E402
from shared.logging_config import configure_json_logging  # noqa: E402
from shared.vector_store import make_vector_store  # noqa: E402

from src.schemas.catalog import Product  # noqa: E402
from src.services.catalog_snapshot import CatalogSnapshot  # noqa: E402
from src.services.catalog_writer import CatalogWriter  # noqa: E402

configure_json_logging()
log = logging.getLogger("reconcile_products")


def _strip_dynamo_keys(item: dict) -> dict:
    out = dict(item)
    out.pop("PK", None)
    out.pop("SK", None)
    return out


def _enumerate_docs(vectors) -> dict[str, list[str]]:
    """Return slug -> [doc_id, ...] map for everything in product-catalog.

    On local OpenSearch, doc id IS the slug, so each list has one element.
    On AOSS, doc ids are auto-generated UUIDs (AOSS rejects custom ids), so
    a single slug may map to multiple ids if seed scripts were re-run —
    those duplicates show up as `len(ids) > 1` and the reconcile loop
    collapses them by deleting all and re-upserting once.
    """
    client = getattr(vectors, "client", None)
    if client is None:
        log.warning("vector store has no underlying client; cannot enumerate")
        return {}
    is_aoss = getattr(vectors, "is_aoss", False)
    out: dict[str, list[str]] = {}

    if is_aoss:
        # AOSS doesn't support scroll/PIT. Single bounded search instead —
        # the product-catalog index is small (10k cap is plenty).
        resp = client.search(
            index=COLLECTION_PRODUCTS,
            body={"query": {"match_all": {}}, "_source": ["slug"]},
            size=10000,
        )
        for hit in resp["hits"]["hits"]:
            slug = hit.get("_source", {}).get("slug")
            if slug:
                # AOSS returns _id URL-encoded in JSON responses (auto-ids
                # contain colons). opensearch-py URL-encodes path segments,
                # so passing the raw response value to client.delete double-
                # encodes and 404s. Decode once here.
                out.setdefault(slug, []).append(unquote(hit["_id"]))
        return out

    # Local OpenSearch path: scroll through, doc id == slug.
    body = {"query": {"match_all": {}}, "_source": False}
    resp = client.search(index=COLLECTION_PRODUCTS, body=body, size=1000, scroll="1m")
    while True:
        hits = resp["hits"]["hits"]
        if not hits:
            break
        for hit in hits:
            out.setdefault(hit["_id"], []).append(hit["_id"])
        scroll_id = resp.get("_scroll_id")
        if not scroll_id:
            break
        resp = client.scroll(scroll_id=scroll_id, scroll="1m")
        if not resp["hits"]["hits"]:
            break
    return out


def _delete_docs(client, doc_ids: list[str]) -> None:
    """Delete each doc by its OpenSearch _id.

    Works on both transports: local OpenSearch lets us delete custom slug-ids
    that we wrote, and AOSS allows DELETE /_doc/<id> when the id was one AOSS
    itself generated (which is what _enumerate_docs returns for AOSS).
    AOSS rejects _delete_by_query and rejects delete-by-custom-id, so this
    is the only path that works for both.
    """
    for doc_id in doc_ids:
        try:
            client.delete(index=COLLECTION_PRODUCTS, id=doc_id, ignore=[404])
        except Exception:
            log.exception("delete failed for doc_id=%s", doc_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile Dynamo products with OpenSearch product-catalog.")
    parser.add_argument(
        "--delete-orphans",
        action="store_true",
        help="Remove vectors that have no Dynamo row.",
    )
    args = parser.parse_args()

    dynamo = DynamoClient(
        endpoint=os.getenv("DYNAMODB_ENDPOINT", "http://localhost:8001"),
        region=os.getenv("AWS_REGION", "us-east-1"),
    )
    bedrock = make_bedrock_client(
        mode=os.getenv("BEDROCK_MODE", "real"),
        region=os.getenv("BEDROCK_REGION", "us-east-1"),
        text_model=os.getenv("BEDROCK_TEXT_MODEL", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"),
        embed_model=os.getenv("BEDROCK_EMBED_MODEL", "amazon.titan-embed-text-v2:0"),
    )
    vectors = make_vector_store(
        mode=os.getenv("VECTOR_MODE", "opensearch"),
        host=os.getenv("OPENSEARCH_HOST", "opensearch"),
        port=int(os.getenv("OPENSEARCH_PORT", "9200")),
        aoss_endpoint=os.getenv("AOSS_ENDPOINT", ""),
        region=os.getenv("AWS_REGION", "us-east-1"),
    )
    snapshot = CatalogSnapshot(dynamo)
    writer = CatalogWriter(dynamo=dynamo, bedrock=bedrock, vectors=vectors, snapshot=snapshot)

    is_aoss = getattr(vectors, "is_aoss", False)
    client = getattr(vectors, "client", None)

    dynamo_products = [Product.model_validate(_strip_dynamo_keys(row)) for row in dynamo.scan_products()]
    dynamo_slugs = {p.slug for p in dynamo_products}
    slug_to_docids = _enumerate_docs(vectors)
    opensearch_slugs = set(slug_to_docids.keys())

    missing_in_vectors = dynamo_slugs - opensearch_slugs
    orphan_vectors = opensearch_slugs - dynamo_slugs
    duplicates = {s: ids for s, ids in slug_to_docids.items() if len(ids) > 1 and s in dynamo_slugs}
    total_docs = sum(len(ids) for ids in slug_to_docids.values())

    log.info(
        "reconcile summary: dynamo=%d opensearch_slugs=%d opensearch_docs=%d missing=%d orphans=%d duplicate_slugs=%d",
        len(dynamo_slugs), len(opensearch_slugs), total_docs,
        len(missing_in_vectors), len(orphan_vectors), len(duplicates),
    )

    # Re-upsert every Dynamo product to catch metadata drift (price changed
    # in Dynamo but vector metadata is stale). On AOSS we delete-by-slug
    # first since auto-generated ids mean upsert-by-id isn't available, so
    # without the delete each re-run would accumulate duplicates.
    for product in dynamo_products:
        try:
            existing = slug_to_docids.get(product.slug, [])
            if is_aoss and existing and client is not None:
                # AOSS auto-generates ids on upsert, so re-runs would pile up
                # duplicates. Delete the prior copies first.
                _delete_docs(client, existing)
            writer.upsert_product(product)
        except Exception:
            log.exception("re-upsert failed for slug=%s", product.slug)

    if orphan_vectors:
        if args.delete_orphans:
            if client is None:
                log.warning("vector store has no client; cannot delete orphans")
            else:
                for slug in orphan_vectors:
                    _delete_docs(client, slug_to_docids.get(slug, []))
                    log.info("deleted orphan vector slug=%s", slug)
        else:
            log.warning(
                "%d orphan vectors detected (in OpenSearch but not Dynamo): %s — pass --delete-orphans to remove",
                len(orphan_vectors), sorted(orphan_vectors),
            )

    log.info("reconcile done")


if __name__ == "__main__":
    main()
