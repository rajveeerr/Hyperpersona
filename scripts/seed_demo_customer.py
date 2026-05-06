"""Seed the demo customer: customer_auth row, profile (+ addresses), orders.

Creates `demo-customer-1` with credentials the frontend can use to log in
via POST /login:

  email    = demo@hyperpersona.test
  password = demo-password-123

After this script runs, the frontend can call /login and use the
returned JWT on every other endpoint.

Idempotent: skips the auth insert if the email is already registered;
overwrites the profile row; re-inserts the demo orders.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from botocore.exceptions import ClientError

sys.path.insert(0, "/app")

from shared.dynamo import DynamoClient  # noqa: E402
from shared.logging_config import configure_json_logging  # noqa: E402
from shared.schemas import utc_now_iso  # noqa: E402

# Re-use the server's bcrypt password hashing.
from src.auth import hash_password  # noqa: E402

configure_json_logging()
log = logging.getLogger("seed_demo_customer")

DEMO_CUSTOMER_ID = "demo-customer-1"
DEMO_EMAIL = "demo@hyperpersona.dev"
DEMO_PASSWORD = "demo-password-123"

SEED_DIR = Path(os.getenv("SEED_DATA_DIR", "/app/src/data"))


def _resolve_placed_at(offset_days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=offset_days)).isoformat()


def main() -> None:
    dynamo = DynamoClient(
        endpoint=os.getenv("DYNAMODB_ENDPOINT", "http://localhost:8001"),
        region=os.getenv("AWS_REGION", "us-east-1"),
    )

    # 1. customer_auth row (skip if already there — idempotent without
    # rotating the bcrypt salt on every run).
    try:
        dynamo.put_auth({
            "email": DEMO_EMAIL,
            "customer_id": DEMO_CUSTOMER_ID,
            "password_hash": hash_password(DEMO_PASSWORD),
            "created_at": utc_now_iso(),
        })
        log.info("created auth row for %s", DEMO_EMAIL)
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            log.info("auth row already exists for %s — skipping", DEMO_EMAIL)
        else:
            raise

    # 2. profile (+ addresses) — overwrite every run.
    with (SEED_DIR / "demo_profile.seed.json").open() as f:
        profile = json.load(f)
    profile["lastUpdated"] = utc_now_iso()
    dynamo.profile_put(DEMO_CUSTOMER_ID, profile)
    log.info("profile written for %s with %d addresses", DEMO_CUSTOMER_ID, len(profile.get("addresses", [])))

    # 3. demo orders — placedAt computed from a relative offset, then
    # written under a stable SK (ORDER#{id}). Wipe existing demo orders
    # first so re-running is idempotent (no duplicate rows from prior
    # SK schemes).
    deleted = dynamo.orders_delete_all_for_customer(DEMO_CUSTOMER_ID)
    if deleted:
        log.info("cleared %d existing order rows before reseed", deleted)

    with (SEED_DIR / "demo_orders.seed.json").open() as f:
        orders = json.load(f)
    for order in orders:
        offset = order.pop("placedAtOffsetDays", 0)
        order["placedAt"] = _resolve_placed_at(offset)
        dynamo.orders_put(DEMO_CUSTOMER_ID, order)
    log.info("seeded %d demo orders for %s", len(orders), DEMO_CUSTOMER_ID)


if __name__ == "__main__":
    main()
