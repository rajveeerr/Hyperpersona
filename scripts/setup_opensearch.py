"""Create OpenSearch KNN indexes for the three vector collections.

Idempotent — re-running with existing indexes is a no-op.

Usage: make setup-opensearch
"""

import os
import time

from opensearchpy import OpenSearch
from opensearchpy.exceptions import RequestError, OpenSearchException


HOST = os.getenv("OPENSEARCH_HOST", "localhost")
PORT = int(os.getenv("OPENSEARCH_PORT", "9200"))


COLLECTIONS = ["customer-facts", "behavior-embeddings", "session-summaries", "product-catalog"]


_KNN_VECTOR_FIELD = {
    "type": "knn_vector",
    "dimension": 1024,
    "method": {
        "name": "hnsw",
        "space_type": "cosinesimil",
        "engine": "lucene",
    },
}

# Customer-data collections (facts, behaviors, sessions) — vectors keyed by
# customer_id, used for personalization retrieval.
INDEX_BODY = {
    "settings": {"index": {"knn": True}},
    "mappings": {
        "properties": {
            "vector": _KNN_VECTOR_FIELD,
            "customer_id": {"type": "keyword"},
            "text": {"type": "text"},
            "source_event": {"type": "keyword"},
            "polarity": {"type": "integer"},
            "timestamp": {"type": "date"},
        }
    },
}

# Product catalog collection — vectors keyed by slug, with structural
# filter fields (vertical, freeDelivery, price, …) for hybrid filter+KNN
# queries.
PRODUCT_INDEX_BODY = {
    "settings": {"index": {"knn": True}},
    "mappings": {
        "properties": {
            "vector": _KNN_VECTOR_FIELD,
            "slug": {"type": "keyword"},
            "name": {"type": "text"},
            "brand": {"type": "keyword"},
            "category": {"type": "keyword"},
            "vertical": {"type": "keyword"},
            "price": {"type": "float"},
            "freeDelivery": {"type": "boolean"},
            "tags": {"type": "keyword"},
        }
    },
}


def _body_for(collection: str) -> dict:
    return PRODUCT_INDEX_BODY if collection == "product-catalog" else INDEX_BODY


def wait_for_cluster(client: OpenSearch, max_seconds: int = 60) -> None:
    for i in range(max_seconds):
        try:
            health = client.cluster.health()
            status = health.get("status")
            if status in ("yellow", "green"):
                print(f"cluster:  {status}")
                return
        except OpenSearchException:
            pass
        time.sleep(1)
    raise TimeoutError("opensearch did not become ready within 60s")


def main() -> None:
    print(f"endpoint: {HOST}:{PORT}")
    client = OpenSearch(
        hosts=[{"host": HOST, "port": PORT}],
        use_ssl=False,
        verify_certs=False,
    )
    wait_for_cluster(client)

    for name in COLLECTIONS:
        try:
            client.indices.create(index=name, body=_body_for(name))
            print(f"created   {name}")
        except RequestError as e:
            if "resource_already_exists_exception" in str(e):
                print(f"exists    {name}")
            else:
                raise


if __name__ == "__main__":
    main()
