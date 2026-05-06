"""Create OpenSearch KNN indexes for the four vector collections.

Idempotent — re-running with existing indexes is a no-op.

Two transports:
  - Local: OPENSEARCH_HOST/PORT over plain HTTP (default).
  - AOSS:  set AOSS_ENDPOINT to use AWS OpenSearch Serverless via SigV4.
           cluster.health() is unavailable on AOSS, so the readiness probe
           is skipped on that path.

Usage: make setup-opensearch
"""

import os
import time
from urllib.parse import urlparse

from opensearchpy import OpenSearch, RequestsHttpConnection
from opensearchpy.exceptions import RequestError, OpenSearchException


HOST = os.getenv("OPENSEARCH_HOST", "localhost")
PORT = int(os.getenv("OPENSEARCH_PORT", "9200"))
AOSS_ENDPOINT = os.getenv("AOSS_ENDPOINT") or None
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")


COLLECTIONS = ["customer-facts", "behavior-embeddings", "session-summaries", "product-catalog"]


# AOSS VectorSearch collections only support nmslib/faiss (lucene is rejected).
# Local OpenSearch ships lucene; we keep that as the local default.
_KNN_ENGINE = "nmslib" if AOSS_ENDPOINT else "lucene"

_KNN_VECTOR_FIELD = {
    "type": "knn_vector",
    "dimension": 1024,
    "method": {
        "name": "hnsw",
        "space_type": "cosinesimil",
        "engine": _KNN_ENGINE,
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
    for _ in range(max_seconds):
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


def make_client() -> tuple[OpenSearch, bool]:
    """Returns (client, is_aoss)."""
    if AOSS_ENDPOINT:
        import boto3
        from opensearchpy import AWSV4SignerAuth

        parsed = urlparse(AOSS_ENDPOINT)
        host = parsed.hostname or AOSS_ENDPOINT
        port = parsed.port or 443
        creds = boto3.Session().get_credentials()
        if creds is None:
            raise RuntimeError("AOSS_ENDPOINT set but no AWS credentials in env")
        client = OpenSearch(
            hosts=[{"host": host, "port": port}],
            http_auth=AWSV4SignerAuth(creds, AWS_REGION, "aoss"),
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=30,
        )
        return client, True

    client = OpenSearch(
        hosts=[{"host": HOST, "port": PORT}],
        use_ssl=False,
        verify_certs=False,
    )
    return client, False


def main() -> None:
    client, is_aoss = make_client()

    if is_aoss:
        print(f"endpoint: {AOSS_ENDPOINT}  (AOSS / SigV4)")
        # cluster.health() is not exposed on AOSS — skip the readiness probe.
    else:
        print(f"endpoint: {HOST}:{PORT}")
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
