"""Bulk-insert seed reviews and recompute per-product aggregates.

Reads server/src/data/reviews.seed.json and writes each review through
DynamoClient.put_review. After the bulk insert, recomputes `rating` +
`reviewCount` for every touched product (write-through to both Dynamo
and — at server next-restart — the catalog snapshot).

Idempotent: re-running overwrites existing review rows by their stable
`id` and recomputes aggregates from the current row set.

Runs in the server container.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, "/app")

from shared.dynamo import DynamoClient  # noqa: E402
from shared.logging_config import configure_json_logging  # noqa: E402

configure_json_logging()
log = logging.getLogger("seed_reviews")

SEED_FILE = Path(os.getenv("SEED_DATA_DIR", "/app/src/data")) / "reviews.seed.json"


def main() -> None:
    dynamo = DynamoClient(
        endpoint=os.getenv("DYNAMODB_ENDPOINT", "http://localhost:8001"),
        region=os.getenv("AWS_REGION", "us-east-1"),
    )

    with SEED_FILE.open() as f:
        bundle: dict[str, list[dict]] = json.load(f)

    total_reviews = 0
    for slug, reviews in bundle.items():
        for review in reviews:
            dynamo.put_review(slug, review)
            total_reviews += 1

        # Recompute aggregates from current Dynamo state for this product.
        rows = dynamo.list_reviews_for_product(slug)
        ratings = [float(r["rating"]) for r in rows if "rating" in r]
        if ratings:
            avg = round(sum(ratings) / len(ratings), 2)
            count = len(ratings)
            dynamo.update_product_review_aggregates(slug, avg, count)
            log.info("aggregates updated: slug=%s rating=%s reviewCount=%d", slug, avg, count)

    log.info("seeded %d reviews across %d products", total_reviews, len(bundle))


if __name__ == "__main__":
    main()
