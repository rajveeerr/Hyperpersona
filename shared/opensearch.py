"""OpenSearch-backed vector store. Implements VectorStoreProtocol.

One class, two backends:
  - Local OpenSearch: HTTP, no auth (dev container at port 9200).
  - AWS OpenSearch Serverless (AOSS): HTTPS + SigV4 auth, port 443. AOSS
    rejects `refresh=*` query params and client-supplied document IDs in
    VECTORSEARCH collections, so the AOSS branch drops both.

Lazy connection — opensearch-py doesn't actually hit the cluster until
the first request, so constructing an OpenSearchClient is safe even
before the cluster is up.
"""

import logging

from opensearchpy import OpenSearch, RequestsHttpConnection
from opensearchpy.exceptions import NotFoundError, OpenSearchException

log = logging.getLogger(__name__)


class OpenSearchClient:
    def __init__(
        self,
        host: str,
        port: int = 9200,
        use_ssl: bool = False,
        aoss: bool = False,
        region: str = "us-east-1",
    ) -> None:
        self.is_aoss = aoss
        if aoss:
            # OpenSearch Serverless: SigV4 with the running role's creds.
            # boto3.Session() picks up AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY
            # + AWS_SESSION_TOKEN from env automatically. Timeout is 60s for
            # cold-start tolerance — first request to a freshly-warmed AOSS
            # collection can take ~30-40s.
            import boto3
            from opensearchpy import AWSV4SignerAuth

            credentials = boto3.Session().get_credentials()
            if credentials is None:
                raise RuntimeError(
                    "AOSS requested but no AWS credentials found in environment "
                    "(AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY[/AWS_SESSION_TOKEN])"
                )
            self.client = OpenSearch(
                hosts=[{"host": host, "port": port}],
                http_auth=AWSV4SignerAuth(credentials, region, "aoss"),
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection,
                http_compress=True,
                pool_maxsize=20,
                timeout=60,
            )
        else:
            self.client = OpenSearch(
                hosts=[{"host": host, "port": port}],
                http_compress=True,
                use_ssl=use_ssl,
                verify_certs=False,
                ssl_show_warn=False,
                timeout=10,
            )

    def upsert(
        self,
        collection: str,
        doc_id: str,
        vector: list[float],
        metadata: dict,
    ) -> None:
        body = {"vector": vector, **metadata}
        if self.is_aoss:
            # AOSS VECTORSEARCH rejects client-supplied IDs (not via _doc, not
            # via _bulk) — the only accepted shape is POST /{index}/_doc with
            # no ID. AOSS auto-generates the _id and consumers already prefer
            # metadata fields (slug, customer_id) over the doc id, so the
            # generated id is functionally fine. Trade-off: retries create
            # duplicate docs; reconcile_products dedupes by slug.
            resp = self.client.index(index=collection, body=body)
            if resp.get("result") not in {"created", "updated"}:
                raise OpenSearchException(f"AOSS index errored: {resp}")
        else:
            self.client.index(
                index=collection,
                id=doc_id,
                body=body,
                refresh="wait_for",
            )

    def search(
        self,
        collection: str,
        query: list[float],
        k: int = 8,
        filter_customer: str | None = None,
    ) -> list[dict]:
        knn_query = {"vector": {"vector": query, "k": k}}

        if filter_customer:
            body: dict = {
                "size": k,
                "query": {
                    "bool": {
                        "must": [{"knn": knn_query}],
                        "filter": [{"term": {"customer_id": filter_customer}}],
                    }
                },
            }
        else:
            body = {"size": k, "query": {"knn": knn_query}}

        try:
            resp = self.client.search(index=collection, body=body)
        except NotFoundError:
            log.warning("OpenSearch index %s does not exist yet", collection)
            return []
        except OpenSearchException as e:
            log.warning("OpenSearch search failed for %s: %s", collection, e)
            return []

        results: list[dict] = []
        for hit in resp["hits"]["hits"]:
            source = dict(hit["_source"])
            source.pop("vector", None)
            results.append({
                "id": hit["_id"],
                "similarity": hit["_score"],
                **source,
            })
        return results

    def delete_by_customer(self, collection: str, customer_id: str) -> None:
        try:
            kwargs: dict = {
                "index": collection,
                "body": {"query": {"term": {"customer_id": customer_id}}},
            }
            if not self.is_aoss:
                kwargs["refresh"] = True
            self.client.delete_by_query(**kwargs)
        except (NotFoundError, OpenSearchException) as e:
            log.warning("delete_by_customer failed for %s: %s", collection, e)
