"""Quick scanner for DynamoDB Local tables.

Usage (inside server container):
  python /app/scripts/scan.py customer_events
  python /app/scripts/scan.py jobs
  python /app/scripts/scan.py customer_consent
"""

import json
import os
import sys

import boto3

ENDPOINT = os.getenv("DYNAMODB_ENDPOINT", "").strip() or None
REGION = os.getenv("AWS_REGION", "us-east-1")


def main() -> None:
    table_name = sys.argv[1] if len(sys.argv) > 1 else "customer_events"
    dynamodb = boto3.resource("dynamodb", endpoint_url=ENDPOINT, region_name=REGION)
    resp = dynamodb.Table(table_name).scan()
    items = resp.get("Items", [])
    print(f"{table_name}: {len(items)} item(s)")
    print(json.dumps(items, default=str, indent=2))


if __name__ == "__main__":
    main()
