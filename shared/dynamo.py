"""DynamoDB helper used by both server and worker.

Wraps the boto3 resource API so callers pass dicts in/out and don't deal with
the low-level type-marshaled format. Empty Python sets are dropped before
writes because DynamoDB rejects empty StringSets.
"""

from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

from .constants import (
    TABLE_CART_ITEMS,
    TABLE_CATEGORIES,
    TABLE_CUSTOMER_AUTH,
    TABLE_CUSTOMER_CONSENT,
    TABLE_CUSTOMER_EVENTS,
    TABLE_CUSTOMER_PROFILE,
    TABLE_JOBS,
    TABLE_ORDERS,
    TABLE_PRODUCT_REVIEWS,
    TABLE_PRODUCTS,
    TABLE_REVIEW_VOTES,
    TABLE_WISHLIST_ITEMS,
)


def _strip_empty_sets(item: dict) -> dict:
    return {k: v for k, v in item.items() if not (isinstance(v, set) and not v)}


def _coerce_floats(value):
    """DynamoDB rejects Python floats; convert recursively to Decimal.
    Used by ecommerce writes whose payloads contain price/rating/etc."""
    if isinstance(value, float):
        # str() round-trips cleanly: Decimal(str(0.1)) == Decimal('0.1')
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _coerce_floats(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_coerce_floats(v) for v in value]
    return value


class DynamoClient:
    def __init__(self, endpoint: str, region: str = "us-east-1"):
        self.resource = boto3.resource(
            "dynamodb",
            endpoint_url=endpoint,
            region_name=region,
        )

    def table(self, name: str):
        return self.resource.Table(name)

    # --- customer_events ---------------------------------------------------

    def put_event(self, event: dict) -> None:
        item = _strip_empty_sets({
            "PK": f"CUSTOMER#{event['customer_id']}",
            "SK": f"EVENT#{event['event_id']}",
            **event,
        })
        self.table(TABLE_CUSTOMER_EVENTS).put_item(Item=item)

    def batch_put_events(self, events: list[dict]) -> None:
        """Bulk insert. boto3's batch_writer chunks at 25 and retries unprocessed items.

        SK is keyed on event_id alone, so a retry with the same client_event_id
        overwrites the existing row instead of inserting a twin.
        """
        if not events:
            return
        with self.table(TABLE_CUSTOMER_EVENTS).batch_writer() as bw:
            for event in events:
                item = _strip_empty_sets({
                    "PK": f"CUSTOMER#{event['customer_id']}",
                    "SK": f"EVENT#{event['event_id']}",
                    **event,
                })
                bw.put_item(Item=item)

    def get_event(self, customer_id: str, event_id: str) -> dict | None:
        resp = self.table(TABLE_CUSTOMER_EVENTS).get_item(
            Key={
                "PK": f"CUSTOMER#{customer_id}",
                "SK": f"EVENT#{event_id}",
            }
        )
        return resp.get("Item")

    def query_events(self, customer_id: str) -> list[dict]:
        resp = self.table(TABLE_CUSTOMER_EVENTS).query(
            KeyConditionExpression=Key("PK").eq(f"CUSTOMER#{customer_id}")
        )
        return resp.get("Items", [])

    def delete_event(self, customer_id: str, event_id: str) -> None:
        self.table(TABLE_CUSTOMER_EVENTS).delete_item(
            Key={
                "PK": f"CUSTOMER#{customer_id}",
                "SK": f"EVENT#{event_id}",
            }
        )

    def delete_all_events_for_customer(self, customer_id: str) -> int:
        """Delete every event for a customer. Returns count deleted."""
        events = self.query_events(customer_id)
        for event in events:
            self.table(TABLE_CUSTOMER_EVENTS).delete_item(
                Key={"PK": event["PK"], "SK": event["SK"]}
            )
        return len(events)

    def update_event_status(
        self,
        customer_id: str,
        event_id: str,
        status: str,
    ) -> None:
        self.table(TABLE_CUSTOMER_EVENTS).update_item(
            Key={
                "PK": f"CUSTOMER#{customer_id}",
                "SK": f"EVENT#{event_id}",
            },
            UpdateExpression="SET #s = :s",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": status},
        )

    # --- customer_consent --------------------------------------------------

    def put_consent(self, consent: dict) -> None:
        item = _strip_empty_sets({
            "PK": f"CUSTOMER#{consent['customer_id']}",
            "SK": "CONSENT",
            **consent,
        })
        self.table(TABLE_CUSTOMER_CONSENT).put_item(Item=item)

    def get_consent(self, customer_id: str) -> dict | None:
        resp = self.table(TABLE_CUSTOMER_CONSENT).get_item(
            Key={"PK": f"CUSTOMER#{customer_id}", "SK": "CONSENT"}
        )
        return resp.get("Item")

    def delete_consent(self, customer_id: str) -> bool:
        """Returns True if a consent record was deleted, False if not found."""
        existing = self.get_consent(customer_id)
        if not existing:
            return False
        self.table(TABLE_CUSTOMER_CONSENT).delete_item(
            Key={"PK": f"CUSTOMER#{customer_id}", "SK": "CONSENT"}
        )
        return True

    # --- jobs --------------------------------------------------------------

    def put_job(self, job: dict) -> None:
        item = _strip_empty_sets({
            "PK": f"JOB#{job['job_id']}",
            "SK": "META",
            **job,
        })
        self.table(TABLE_JOBS).put_item(Item=item)

    def batch_put_jobs(self, jobs: list[dict]) -> None:
        if not jobs:
            return
        with self.table(TABLE_JOBS).batch_writer() as bw:
            for job in jobs:
                item = _strip_empty_sets({
                    "PK": f"JOB#{job['job_id']}",
                    "SK": "META",
                    **job,
                })
                bw.put_item(Item=item)

    def get_job(self, job_id: str) -> dict | None:
        resp = self.table(TABLE_JOBS).get_item(
            Key={"PK": f"JOB#{job_id}", "SK": "META"}
        )
        return resp.get("Item")

    def update_job_status(
        self,
        job_id: str,
        status: str,
        completed_at: str | None = None,
        error: str | None = None,
    ) -> None:
        update_parts = ["#s = :s"]
        names = {"#s": "status"}
        values = {":s": status}
        if completed_at:
            update_parts.append("completed_at = :c")
            values[":c"] = completed_at
        if error:
            update_parts.append("#e = :e")
            names["#e"] = "error"
            values[":e"] = error
        self.table(TABLE_JOBS).update_item(
            Key={"PK": f"JOB#{job_id}", "SK": "META"},
            UpdateExpression="SET " + ", ".join(update_parts),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )

    # --- customer_auth -----------------------------------------------------

    def put_auth(self, record: dict) -> None:
        """Insert a new auth row. Raises ClientError (ConditionalCheckFailed)
        if the email is already registered."""
        email_key = record["email"].lower()
        item = _strip_empty_sets({
            "PK": f"EMAIL#{email_key}",
            "SK": "AUTH",
            **record,
            "email": email_key,
        })
        self.table(TABLE_CUSTOMER_AUTH).put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(PK)",
        )

    def get_auth_by_email(self, email: str) -> dict | None:
        resp = self.table(TABLE_CUSTOMER_AUTH).get_item(
            Key={"PK": f"EMAIL#{email.lower()}", "SK": "AUTH"}
        )
        return resp.get("Item")

    # --- products ----------------------------------------------------------
    # NOTE: products are also indexed in the OpenSearch product-catalog
    # collection. Mutations MUST go through the CatalogWriter service so
    # both stores stay in sync. Direct callers of put_product / delete
    # bypass that and cause drift; the reconcile script is the recovery.

    def put_product(self, product: dict) -> None:
        item = _strip_empty_sets(_coerce_floats({
            "PK": f"PRODUCT#{product['slug']}",
            "SK": "META",
            **product,
        }))
        self.table(TABLE_PRODUCTS).put_item(Item=item)

    def get_product_by_slug(self, slug: str) -> dict | None:
        resp = self.table(TABLE_PRODUCTS).get_item(
            Key={"PK": f"PRODUCT#{slug}", "SK": "META"}
        )
        return resp.get("Item")

    def scan_products(self) -> list[dict]:
        """Return every product. Catalog is small (~hundreds of SKUs) so
        full-scan is fine; the snapshot service caches the result."""
        items: list[dict] = []
        last_key: dict | None = None
        while True:
            kwargs = {}
            if last_key:
                kwargs["ExclusiveStartKey"] = last_key
            resp = self.table(TABLE_PRODUCTS).scan(**kwargs)
            items.extend(resp.get("Items", []))
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break
        return items

    def delete_product(self, slug: str) -> None:
        self.table(TABLE_PRODUCTS).delete_item(
            Key={"PK": f"PRODUCT#{slug}", "SK": "META"}
        )

    def update_product_review_aggregates(
        self, slug: str, rating: float, review_count: int
    ) -> None:
        """Write-through update for review aggregates. Vector unchanged
        because rating/reviewCount aren't part of the embed text."""
        self.table(TABLE_PRODUCTS).update_item(
            Key={"PK": f"PRODUCT#{slug}", "SK": "META"},
            UpdateExpression="SET rating = :r, reviewCount = :c",
            ExpressionAttributeValues={
                ":r": Decimal(str(rating)),
                ":c": review_count,
            },
        )

    # --- categories --------------------------------------------------------

    def put_category(self, category: dict) -> None:
        item = _strip_empty_sets({
            "PK": "CATEGORY",
            "SK": f"CATEGORY#{category['slug']}",
            **category,
        })
        self.table(TABLE_CATEGORIES).put_item(Item=item)

    def list_categories(self) -> list[dict]:
        resp = self.table(TABLE_CATEGORIES).query(
            KeyConditionExpression=Key("PK").eq("CATEGORY")
        )
        return resp.get("Items", [])

    # --- product_reviews ---------------------------------------------------
    # SK is REVIEW#{review_id} (no created_at prefix) so update + delete
    # don't require knowing the timestamp. created_at lives on the row;
    # services sort in Python after a Query returns.

    def put_review(self, slug: str, review: dict) -> None:
        """Insert a new review. Use ConditionExpression to enforce
        one-per-customer-per-product via the GSI lookup at the service
        layer (we can't condition on a GSI item here, but the service
        checks first via get_viewer_review)."""
        item = _strip_empty_sets(_coerce_floats({
            "PK": f"PRODUCT#{slug}",
            "SK": f"REVIEW#{review['id']}",
            "product_slug": slug,  # GSI sort key
            "customer_id": review.get("customer_id"),  # GSI partition key
            **review,
        }))
        self.table(TABLE_PRODUCT_REVIEWS).put_item(Item=item)

    def list_reviews_for_product(self, slug: str) -> list[dict]:
        """Return all reviews for a product. Pagination + sort handled
        in the service layer; review counts per SKU stay small."""
        resp = self.table(TABLE_PRODUCT_REVIEWS).query(
            KeyConditionExpression=Key("PK").eq(f"PRODUCT#{slug}"),
        )
        return resp.get("Items", [])

    def get_review(self, slug: str, review_id: str) -> dict | None:
        resp = self.table(TABLE_PRODUCT_REVIEWS).get_item(
            Key={"PK": f"PRODUCT#{slug}", "SK": f"REVIEW#{review_id}"},
        )
        return resp.get("Item")

    def get_viewer_review(self, slug: str, customer_id: str) -> dict | None:
        """One Query on the customer-product-index GSI. Used both for
        409-on-duplicate-create and for the viewerReview projection on
        the PDP shape."""
        resp = self.table(TABLE_PRODUCT_REVIEWS).query(
            IndexName="customer-product-index",
            KeyConditionExpression=Key("customer_id").eq(customer_id) & Key("product_slug").eq(slug),
            Limit=1,
        )
        items = resp.get("Items", [])
        return items[0] if items else None

    def update_review_counters(
        self,
        slug: str,
        review_id: str,
        helpful_delta: int,
        not_helpful_delta: int,
    ) -> dict:
        """Atomic counter swap. Returns the new counter values so the
        helpful endpoint can echo them in its response."""
        from decimal import Decimal as _Decimal  # local to keep import surface tight
        resp = self.table(TABLE_PRODUCT_REVIEWS).update_item(
            Key={"PK": f"PRODUCT#{slug}", "SK": f"REVIEW#{review_id}"},
            UpdateExpression=(
                "SET helpfulCount = if_not_exists(helpfulCount, :zero) + :hd, "
                "notHelpfulCount = if_not_exists(notHelpfulCount, :zero) + :nd"
            ),
            ExpressionAttributeValues={
                ":hd": _Decimal(helpful_delta),
                ":nd": _Decimal(not_helpful_delta),
                ":zero": _Decimal(0),
            },
            ReturnValues="ALL_NEW",
        )
        return resp.get("Attributes", {})

    # --- review_votes ------------------------------------------------------

    def get_vote(self, review_id: str, customer_id: str) -> dict | None:
        resp = self.table(TABLE_REVIEW_VOTES).get_item(
            Key={"PK": f"REVIEW#{review_id}", "SK": f"CUSTOMER#{customer_id}"},
        )
        return resp.get("Item")

    def put_vote(self, review_id: str, customer_id: str, vote: str) -> None:
        self.table(TABLE_REVIEW_VOTES).put_item(
            Item={
                "PK": f"REVIEW#{review_id}",
                "SK": f"CUSTOMER#{customer_id}",
                "review_id": review_id,
                "customer_id": customer_id,
                "vote": vote,
            }
        )

    # --- customer_profile --------------------------------------------------

    def profile_get(self, customer_id: str) -> dict | None:
        resp = self.table(TABLE_CUSTOMER_PROFILE).get_item(
            Key={"PK": f"CUSTOMER#{customer_id}", "SK": "PROFILE"}
        )
        return resp.get("Item")

    def profile_put(self, customer_id: str, profile: dict) -> None:
        item = _strip_empty_sets(_coerce_floats({
            "PK": f"CUSTOMER#{customer_id}",
            "SK": "PROFILE",
            **profile,
        }))
        self.table(TABLE_CUSTOMER_PROFILE).put_item(Item=item)

    # --- orders ------------------------------------------------------------

    def orders_put(self, customer_id: str, order: dict) -> None:
        """SK is `ORDER#{id}` (stable) so re-inserts overwrite instead of
        duplicating. Caller (the service) sorts by `placed_at` in Python."""
        item = _strip_empty_sets(_coerce_floats({
            "PK": f"CUSTOMER#{customer_id}",
            "SK": f"ORDER#{order['id']}",
            **order,
        }))
        self.table(TABLE_ORDERS).put_item(Item=item)

    def orders_list(self, customer_id: str) -> list[dict]:
        """All orders for a customer. Sort in the service layer (small N)."""
        resp = self.table(TABLE_ORDERS).query(
            KeyConditionExpression=Key("PK").eq(f"CUSTOMER#{customer_id}"),
        )
        return resp.get("Items", [])

    def orders_delete_all_for_customer(self, customer_id: str) -> int:
        """Used by the demo seeder to keep re-runs idempotent. Returns
        number of rows deleted."""
        rows = self.orders_list(customer_id)
        for row in rows:
            self.table(TABLE_ORDERS).delete_item(
                Key={"PK": row["PK"], "SK": row["SK"]}
            )
        return len(rows)

    # --- cart_items --------------------------------------------------------

    def cart_get(self, customer_id: str) -> list[dict]:
        resp = self.table(TABLE_CART_ITEMS).query(
            KeyConditionExpression=Key("PK").eq(f"CUSTOMER#{customer_id}"),
        )
        return resp.get("Items", [])

    def cart_get_item(self, customer_id: str, product_id: str) -> dict | None:
        resp = self.table(TABLE_CART_ITEMS).get_item(
            Key={"PK": f"CUSTOMER#{customer_id}", "SK": f"CART#{product_id}"},
        )
        return resp.get("Item")

    def cart_put_item(self, customer_id: str, item: dict) -> None:
        record = _strip_empty_sets(_coerce_floats({
            "PK": f"CUSTOMER#{customer_id}",
            "SK": f"CART#{item['product_id']}",
            **item,
        }))
        self.table(TABLE_CART_ITEMS).put_item(Item=record)

    def cart_delete_item(self, customer_id: str, product_id: str) -> bool:
        """Returns True if a row existed and was deleted, False otherwise."""
        existing = self.cart_get_item(customer_id, product_id)
        if not existing:
            return False
        self.table(TABLE_CART_ITEMS).delete_item(
            Key={"PK": f"CUSTOMER#{customer_id}", "SK": f"CART#{product_id}"}
        )
        return True

    def cart_clear(self, customer_id: str) -> int:
        """Wipe every cart row for a customer. Returns count deleted.
        Used by /checkout after the order is written."""
        rows = self.cart_get(customer_id)
        for row in rows:
            self.table(TABLE_CART_ITEMS).delete_item(
                Key={"PK": row["PK"], "SK": row["SK"]}
            )
        return len(rows)

    # --- wishlist_items ----------------------------------------------------

    def wishlist_get(self, customer_id: str) -> list[dict]:
        resp = self.table(TABLE_WISHLIST_ITEMS).query(
            KeyConditionExpression=Key("PK").eq(f"CUSTOMER#{customer_id}"),
        )
        return resp.get("Items", [])

    def wishlist_get_item(self, customer_id: str, product_id: str) -> dict | None:
        resp = self.table(TABLE_WISHLIST_ITEMS).get_item(
            Key={"PK": f"CUSTOMER#{customer_id}", "SK": f"WISH#{product_id}"},
        )
        return resp.get("Item")

    def wishlist_put_item(self, customer_id: str, item: dict) -> None:
        record = _strip_empty_sets({
            "PK": f"CUSTOMER#{customer_id}",
            "SK": f"WISH#{item['product_id']}",
            **item,
        })
        self.table(TABLE_WISHLIST_ITEMS).put_item(Item=record)

    def wishlist_delete_item(self, customer_id: str, product_id: str) -> bool:
        existing = self.wishlist_get_item(customer_id, product_id)
        if not existing:
            return False
        self.table(TABLE_WISHLIST_ITEMS).delete_item(
            Key={"PK": f"CUSTOMER#{customer_id}", "SK": f"WISH#{product_id}"}
        )
        return True
