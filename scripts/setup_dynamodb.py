"""Create DynamoDB tables.

Idempotent — safe to re-run. Reads DYNAMODB_ENDPOINT from env:
  - empty / unset → real AWS DynamoDB (in AWS_REGION)
  - http://...    → DynamoDB Local at that URL

Run inside the server container so it sees the same env vars as the server:

  make setup-db
  # or
  docker compose exec server python /app/scripts/setup_dynamodb.py
"""

import os

import boto3
from botocore.exceptions import ClientError

ENDPOINT = os.getenv("DYNAMODB_ENDPOINT", "").strip() or None  # empty => real AWS
REGION = os.getenv("AWS_REGION", "us-east-1")

dynamodb = boto3.client("dynamodb", endpoint_url=ENDPOINT, region_name=REGION)

PK_SK = [
    {"AttributeName": "PK", "KeyType": "HASH"},
    {"AttributeName": "SK", "KeyType": "RANGE"},
]
PK_SK_ATTRS = [
    {"AttributeName": "PK", "AttributeType": "S"},
    {"AttributeName": "SK", "AttributeType": "S"},
]
STATUS_INDEX_KEYS = [
    {"AttributeName": "status", "KeyType": "HASH"},
    {"AttributeName": "created_at", "KeyType": "RANGE"},
]
STATUS_INDEX_ATTRS = [
    {"AttributeName": "status", "AttributeType": "S"},
    {"AttributeName": "created_at", "AttributeType": "S"},
]
# GSI keys for product_reviews: lets us look up "has this customer
# already reviewed this product?" in one Query (one-per-customer-per-SKU
# enforcement + viewerReview projection).
CUSTOMER_PRODUCT_INDEX_KEYS = [
    {"AttributeName": "customer_id", "KeyType": "HASH"},
    {"AttributeName": "product_slug", "KeyType": "RANGE"},
]
CUSTOMER_PRODUCT_INDEX_ATTRS = [
    {"AttributeName": "customer_id", "AttributeType": "S"},
    {"AttributeName": "product_slug", "AttributeType": "S"},
]


TABLES = [
    {
        "TableName": "customer_events",
        "KeySchema": PK_SK,
        "AttributeDefinitions": PK_SK_ATTRS + STATUS_INDEX_ATTRS,
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "status-index",
                "KeySchema": STATUS_INDEX_KEYS,
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "customer_consent",
        "KeySchema": PK_SK,
        "AttributeDefinitions": PK_SK_ATTRS,
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "customer_auth",
        "KeySchema": PK_SK,
        "AttributeDefinitions": PK_SK_ATTRS,
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "jobs",
        "KeySchema": PK_SK,
        "AttributeDefinitions": PK_SK_ATTRS + STATUS_INDEX_ATTRS,
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "status-index",
                "KeySchema": STATUS_INDEX_KEYS,
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    # --- ecommerce tables ----------------------------------------------------
    {
        "TableName": "products",
        "KeySchema": PK_SK,
        "AttributeDefinitions": PK_SK_ATTRS,
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "categories",
        "KeySchema": PK_SK,
        "AttributeDefinitions": PK_SK_ATTRS,
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "product_reviews",
        "KeySchema": PK_SK,
        "AttributeDefinitions": PK_SK_ATTRS + CUSTOMER_PRODUCT_INDEX_ATTRS,
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "customer-product-index",
                "KeySchema": CUSTOMER_PRODUCT_INDEX_KEYS,
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "review_votes",
        "KeySchema": PK_SK,
        "AttributeDefinitions": PK_SK_ATTRS,
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "customer_profile",
        "KeySchema": PK_SK,
        "AttributeDefinitions": PK_SK_ATTRS,
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "cart_items",
        "KeySchema": PK_SK,
        "AttributeDefinitions": PK_SK_ATTRS,
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "wishlist_items",
        "KeySchema": PK_SK,
        "AttributeDefinitions": PK_SK_ATTRS,
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "orders",
        "KeySchema": PK_SK,
        "AttributeDefinitions": PK_SK_ATTRS,
        "BillingMode": "PAY_PER_REQUEST",
    },
    # --- recommender catalog (separate from the storefront `products` table) -
    {
        "TableName": "product_catalog",
        "KeySchema": PK_SK,
        "AttributeDefinitions": PK_SK_ATTRS,
        "BillingMode": "PAY_PER_REQUEST",
    },
]


def create_or_skip(spec: dict) -> str:
    name = spec["TableName"]
    try:
        dynamodb.create_table(**spec)
        return f"created  {name}"
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            return f"exists   {name}"
        raise


def enable_ttl(table_name: str, attribute: str = "expires_at") -> str:
    """Enable DynamoDB TTL on a table. Idempotent.

    Real AWS DynamoDB returns ResourceInUseException if the table isn't
    ACTIVE yet — wait for it. DynamoDB Local creates tables instantly so
    the waiter is a no-op there.
    """
    try:
        dynamodb.get_waiter("table_exists").wait(
            TableName=table_name,
            WaiterConfig={"Delay": 2, "MaxAttempts": 30},
        )
    except Exception:
        # If the waiter itself fails, fall through and let the TTL call
        # surface the real error.
        pass
    try:
        dynamodb.update_time_to_live(
            TableName=table_name,
            TimeToLiveSpecification={
                "Enabled": True,
                "AttributeName": attribute,
            },
        )
        return f"ttl on   {table_name}.{attribute}"
    except ClientError as e:
        # Already enabled with the same attribute → harmless
        msg = str(e)
        if "TimeToLive is already enabled" in msg or "already an active" in msg:
            return f"ttl skip {table_name} (already enabled)"
        raise


def main() -> None:
    print(f"endpoint: {ENDPOINT or 'AWS default (real DynamoDB)'}  region: {REGION}")
    for spec in TABLES:
        print(create_or_skip(spec))
    # TTL on events so old data auto-expires per the customer's retention setting.
    # On real AWS DynamoDB, TTL takes up to 1h to actually start sweeping;
    # the table reports it enabled instantly though.
    print(enable_ttl("customer_events", "expires_at"))


if __name__ == "__main__":
    main()
