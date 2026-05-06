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


def _opensearch_slugs(vectors) -> set[str]:
    """Return every doc id (which is the slug) currently in product-catalog."""
    client = getattr(vectors, "client", None)
    if client is None:
        log.warning("vector store has no underlying client; cannot enumerate orphans")
        return set()
    slugs: set[str] = set()
    # Scroll through all docs, source=False so we don't pay for vectors.
    body = {"query": {"match_all": {}}, "_source": False}
    resp = client.search(index=COLLECTION_PRODUCTS, body=body, size=1000, scroll="1m")
    while True:
        hits = resp["hits"]["hits"]
        if not hits:
            break
        for hit in hits:
            slugs.add(hit["_id"])
        scroll_id = resp.get("_scroll_id")
        if not scroll_id:
            break
        resp = client.scroll(scroll_id=scroll_id, scroll="1m")
        if not resp["hits"]["hits"]:
            break
    return slugs


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
        mode=os.getenv("BEDROCK_MODE", "mock"),
        region=os.getenv("BEDROCK_REGION", "us-east-1"),
        text_model=os.getenv("BEDROCK_TEXT_MODEL", "amazon.titan-embed-text-v2:0"),
        embed_model=os.getenv("BEDROCK_EMBED_MODEL", "amazon.titan-embed-text-v2:0"),
    )
    vectors = make_vector_store(
        mode=os.getenv("VECTOR_MODE", "opensearch"),
        host=os.getenv("OPENSEARCH_HOST", "opensearch"),
        port=int(os.getenv("OPENSEARCH_PORT", "9200")),
    )
    snapshot = CatalogSnapshot(dynamo)
    writer = CatalogWriter(dynamo=dynamo, bedrock=bedrock, vectors=vectors, snapshot=snapshot)

    dynamo_products = [Product.model_validate(_strip_dynamo_keys(row)) for row in dynamo.scan_products()]
    dynamo_slugs = {p.slug for p in dynamo_products}
    opensearch_slugs = _opensearch_slugs(vectors)

    missing_in_vectors = dynamo_slugs - opensearch_slugs
    orphan_vectors = opensearch_slugs - dynamo_slugs

    log.info(
        "reconcile summary: dynamo=%d opensearch=%d missing_vectors=%d orphans=%d",
        len(dynamo_slugs), len(opensearch_slugs), len(missing_in_vectors), len(orphan_vectors),
    )

    # Re-upsert anything missing or potentially-stale. Re-embedding the
    # whole set is cheap with the mock client and idempotent with real
    # Titan. We do all dynamo products to also catch metadata drift
    # (price changed in Dynamo but vector metadata is stale).
    for product in dynamo_products:
        try:
            writer.upsert_product(product)
        except Exception:
            log.exception("re-upsert failed for slug=%s", product.slug)

    if orphan_vectors:
        if args.delete_orphans:
            client = getattr(vectors, "client", None)
            if client is None:
                log.warning("vector store has no client; cannot delete orphans")
            else:
                for slug in orphan_vectors:
                    client.delete(index=COLLECTION_PRODUCTS, id=slug, ignore=[404])
                    log.info("deleted orphan vector slug=%s", slug)
        else:
            log.warning(
                "%d orphan vectors detected (in OpenSearch but not Dynamo): %s — pass --delete-orphans to remove",
                len(orphan_vectors), sorted(orphan_vectors),
            )

    log.info("reconcile done")


if __name__ == "__main__":
    main()
