"""Vector store with two implementations.

InMemoryVectorStore — Python-dict, cosine similarity. Mock for dev.
OpenSearchClient    — real OpenSearch (added in Phase 7).

Both implement the VectorStoreProtocol below. Tools reference the protocol
type; swapping the backend doesn't change tool code.
"""

from typing import Protocol


class VectorStoreProtocol(Protocol):
    def upsert(
        self,
        collection: str,
        doc_id: str,
        vector: list[float],
        metadata: dict,
    ) -> None: ...

    def search(
        self,
        collection: str,
        query: list[float],
        k: int = 8,
        filter_customer: str | None = None,
    ) -> list[dict]: ...

    def delete_by_customer(self, collection: str, customer_id: str) -> None: ...


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


class InMemoryVectorStore:
    """Process-local vector store. State is lost on worker restart.

    Vectors are assumed unit-normalized (mock and real Titan both produce
    unit vectors), so cosine similarity == dot product.
    """

    def __init__(self) -> None:
        self._collections: dict[str, dict[str, dict]] = {}

    def upsert(
        self,
        collection: str,
        doc_id: str,
        vector: list[float],
        metadata: dict,
    ) -> None:
        coll = self._collections.setdefault(collection, {})
        coll[doc_id] = {"vector": vector, "metadata": metadata}

    def search(
        self,
        collection: str,
        query: list[float],
        k: int = 8,
        filter_customer: str | None = None,
    ) -> list[dict]:
        coll = self._collections.get(collection, {})
        results = []
        for doc_id, doc in coll.items():
            md = doc["metadata"]
            if filter_customer and md.get("customer_id") != filter_customer:
                continue
            similarity = _dot(query, doc["vector"])
            results.append({"id": doc_id, "similarity": similarity, **md})
        results.sort(key=lambda r: r["similarity"], reverse=True)
        return results[:k]

    def delete_by_customer(self, collection: str, customer_id: str) -> None:
        coll = self._collections.get(collection, {})
        to_drop = [
            doc_id
            for doc_id, doc in coll.items()
            if doc["metadata"].get("customer_id") == customer_id
        ]
        for doc_id in to_drop:
            del coll[doc_id]


def make_vector_store(
    mode: str = "memory",
    host: str = "opensearch",
    port: int = 9200,
    aoss_endpoint: str = "",
    region: str = "us-east-1",
) -> VectorStoreProtocol:
    if mode == "memory":
        return InMemoryVectorStore()
    if mode == "opensearch":
        from .opensearch import OpenSearchClient
        return OpenSearchClient(host=host, port=port)
    if mode == "aoss":
        if not aoss_endpoint:
            raise ValueError("VECTOR_MODE=aoss requires AOSS_ENDPOINT to be set")
        # AOSS endpoint format: https://abc123.us-east-1.aoss.amazonaws.com
        # opensearch-py wants just the host, no scheme.
        host_only = aoss_endpoint.replace("https://", "").replace("http://", "").rstrip("/")
        from .opensearch import OpenSearchClient
        return OpenSearchClient(
            host=host_only, port=443, use_ssl=True, aoss=True, region=region,
        )
    raise ValueError(f"Unknown vector store mode: {mode!r}")
