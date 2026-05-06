"""Scan an OpenSearch collection.

Usage:
  python /app/scripts/scan_vectors.py <collection> [<customer_id>]

Examples:
  python /app/scripts/scan_vectors.py customer-facts
  python /app/scripts/scan_vectors.py customer-facts cust_1

Honors `VECTOR_MODE` from the environment so the script reads from whichever
backend the worker is actually writing to:
  - VECTOR_MODE=aoss      → AWS OpenSearch Serverless (HTTPS + SigV4 via AOSS_ENDPOINT)
  - VECTOR_MODE=opensearch (default) → local Docker OpenSearch (OPENSEARCH_HOST/PORT)

Without this dual-mode behavior, scans against an AOSS-deployed worker silently
return empty even when AOSS has data — the script was always pointing at the
local Docker container.
"""

import json
import os
import sys

from opensearchpy import OpenSearch
from opensearchpy.exceptions import NotFoundError, OpenSearchException


def _build_client() -> OpenSearch:
    mode = os.getenv("VECTOR_MODE", "opensearch").lower()

    if mode == "aoss":
        # Lazy imports so the local-only path doesn't pay the boto3 cost.
        import boto3
        from opensearchpy import RequestsHttpConnection
        from opensearchpy.helpers.signer import RequestsAWSV4SignerAuth

        endpoint = os.environ.get("AOSS_ENDPOINT", "").replace("https://", "").rstrip("/")
        if not endpoint:
            print("error: VECTOR_MODE=aoss but AOSS_ENDPOINT is not set", file=sys.stderr)
            sys.exit(2)
        region = os.getenv("AWS_REGION", "us-east-1")
        creds = boto3.Session().get_credentials()
        if creds is None:
            print(
                "error: VECTOR_MODE=aoss but no AWS credentials found in environment",
                file=sys.stderr,
            )
            sys.exit(2)
        return OpenSearch(
            hosts=[{"host": endpoint, "port": 443}],
            http_auth=RequestsAWSV4SignerAuth(creds, region, "aoss"),
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=20,
        )

    # Local Docker OpenSearch (default)
    host = os.getenv("OPENSEARCH_HOST", "localhost")
    port = int(os.getenv("OPENSEARCH_PORT", "9200"))
    return OpenSearch(
        hosts=[{"host": host, "port": port}],
        use_ssl=False,
        verify_certs=False,
    )


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: scan_vectors.py <collection> [<customer_id>]")
        sys.exit(1)

    collection = sys.argv[1]
    customer_id = sys.argv[2] if len(sys.argv) > 2 else None

    client = _build_client()
    backend = os.getenv("VECTOR_MODE", "opensearch").lower()

    body: dict = {"size": 100, "track_total_hits": True}
    if customer_id:
        body["query"] = {"term": {"customer_id": customer_id}}

    try:
        resp = client.search(index=collection, body=body)
    except NotFoundError:
        hint = "make setup-aoss" if backend == "aoss" else "make setup-opensearch"
        print(f"index {collection!r} does not exist (run {hint})")
        sys.exit(1)
    except OpenSearchException as e:
        print(f"error: {e}")
        sys.exit(1)

    hits = resp["hits"]["hits"]
    total = resp["hits"]["total"]
    if isinstance(total, dict):
        total_value = total.get("value", len(hits))
    else:
        total_value = total
    suffix = f" for {customer_id}" if customer_id else ""
    print(f"{collection} [{backend}]: {len(hits)} of {total_value} shown{suffix}")

    for hit in hits:
        source = dict(hit["_source"])
        source.pop("vector", None)
        source.pop("embedding", None)
        print(f"  id={hit['_id']}  {json.dumps(source)}")


if __name__ == "__main__":
    main()
