"""Provision AWS OpenSearch Serverless (AOSS) and create the four indexes.

Idempotent — safe to re-run. Walks the AOSS resource graph:

  1. Encryption policy   (KMS-managed key for the collection)
  2. Network policy      (PUBLIC access — no VPC for hackathon simplicity)
  3. Data access policy  (lets the running role read+write the collection)
  4. Collection          (VECTORSEARCH type, optimized for k-NN)
  5. Wait for ACTIVE     (~2-3 minutes on first create)
  6. Create 4 indexes    (customer-facts, behavior-embeddings, session-summaries, product-catalog)

Prints the collection endpoint at the end — copy into .env as AOSS_ENDPOINT,
flip VECTOR_MODE=aoss, then `make down && make up`.

Usage:
    docker compose exec worker python /app/scripts/setup_aoss.py
or:
    make setup-aoss
"""

import json
import os
import sys
import time

import boto3
from botocore.exceptions import ClientError


COLLECTION_NAME = os.getenv("AOSS_COLLECTION_NAME", "hyperpersona-vectors")
REGION = os.getenv("AWS_REGION", "us-east-1")

# All four resources share the same name for clarity.
ENCRYPTION_POLICY_NAME = COLLECTION_NAME
NETWORK_POLICY_NAME = COLLECTION_NAME
DATA_ACCESS_POLICY_NAME = COLLECTION_NAME

INDEXES = ["customer-facts", "behavior-embeddings", "session-summaries", "product-catalog"]


_KNN_VECTOR_FIELD = {
    "type": "knn_vector",
    "dimension": 1024,
    "method": {
        "name": "hnsw",
        "space_type": "cosinesimil",
        "engine": "faiss",  # AOSS recommends faiss for vector search
    },
}

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


def _body_for(name: str) -> dict:
    return PRODUCT_INDEX_BODY if name == "product-catalog" else INDEX_BODY


def _create_or_update_policy(aoss, name: str, type_: str, policy: list[dict]) -> str:
    """Idempotent create — ConflictException means it exists, fall back to update.
    AOSS rejects updates with no diff, so treat 'No changes' as success."""
    try:
        aoss.create_security_policy(
            name=name, type=type_, policy=json.dumps(policy),
        )
        return "created"
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") != "ConflictException":
            raise
        existing = aoss.get_security_policy(name=name, type=type_)
        version = existing["securityPolicyDetail"]["policyVersion"]
        try:
            aoss.update_security_policy(
                name=name, type=type_, policyVersion=version, policy=json.dumps(policy),
            )
            return "updated"
        except ClientError as e2:
            msg = str(e2)
            if "No changes detected" in msg:
                return "unchanged"
            raise


def _ensure_collection(aoss, name: str) -> str:
    """Idempotent create. Returns the collection ID.

    Type is VECTORSEARCH because we need k-NN. VECTORSEARCH rejects
    client-supplied document IDs, so the OpenSearchClient stores our
    intended doc_id as an `external_id` field instead — losing per-id
    upsert idempotency, but ACE ranking dedupes facts by content anyway
    so the practical impact is small.
    """
    existing = aoss.batch_get_collection(names=[name]).get("collectionDetails", [])
    if existing:
        c = existing[0]
        print(f"  collection already exists  id={c['id']}  type={c.get('type')}  status={c['status']}")
        return c["id"]
    resp = aoss.create_collection(
        name=name,
        type="VECTORSEARCH",
        description="HyperPersona personalization vectors (knn)",
    )
    cid = resp["createCollectionDetail"]["id"]
    print(f"  collection created          id={cid}  type=VECTORSEARCH  (waiting for ACTIVE...)")
    return cid


def _wait_for_active(aoss, name: str, timeout_seconds: int = 600) -> dict:
    """Poll batch_get_collection until status=ACTIVE."""
    deadline = time.time() + timeout_seconds
    last_status = "?"
    while time.time() < deadline:
        details = aoss.batch_get_collection(names=[name]).get("collectionDetails", [])
        if details:
            c = details[0]
            last_status = c["status"]
            if last_status == "ACTIVE":
                return c
            if last_status == "FAILED":
                raise RuntimeError(f"collection {name} entered FAILED state")
        time.sleep(15)
    raise TimeoutError(
        f"collection {name} did not become ACTIVE within {timeout_seconds}s "
        f"(last status: {last_status})"
    )


def _caller_arn() -> str:
    """The role/user that this script is running as — needs read+write on AOSS."""
    sts = boto3.client("sts", region_name=REGION)
    arn = sts.get_caller_identity()["Arn"]
    # Assumed-role ARNs need to be converted to the role ARN for AOSS data
    # access policies. e.g.
    #   arn:aws:sts::123:assumed-role/RoleName/SessionName
    # → arn:aws:iam::123:role/RoleName
    if ":assumed-role/" in arn:
        parts = arn.split(":assumed-role/")
        account = parts[0].split("::")[1]
        role_name = parts[1].split("/")[0]
        return f"arn:aws:iam::{account}:role/{role_name}"
    return arn


def _create_indexes(collection_endpoint: str) -> None:
    """Create the four indexes on the AOSS collection via SigV4-auth'd HTTP."""
    from opensearchpy import (
        AWSV4SignerAuth,
        OpenSearch,
        RequestsHttpConnection,
    )
    from opensearchpy.exceptions import RequestError

    host = collection_endpoint.replace("https://", "").rstrip("/")
    credentials = boto3.Session().get_credentials()
    auth = AWSV4SignerAuth(credentials, REGION, "aoss")
    client = OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=30,
    )

    for name in INDEXES:
        try:
            client.indices.create(index=name, body=_body_for(name))
            print(f"  index created    {name}")
        except RequestError as e:
            if "resource_already_exists_exception" in str(e):
                print(f"  index exists     {name}")
            else:
                raise


def main() -> int:
    aoss = boto3.client("opensearchserverless", region_name=REGION)
    role_arn = _caller_arn()
    print(f"caller       : {role_arn}")
    print(f"collection   : {COLLECTION_NAME}")
    print(f"region       : {REGION}")
    print()

    # 1. Encryption policy — required before collection create.
    print("--- encryption policy ---")
    enc_status = _create_or_update_policy(
        aoss, ENCRYPTION_POLICY_NAME, "encryption",
        {
            "Rules": [{
                "Resource": [f"collection/{COLLECTION_NAME}"],
                "ResourceType": "collection",
            }],
            "AWSOwnedKey": True,
        },
    )
    print(f"  {enc_status}: {ENCRYPTION_POLICY_NAME}")
    print()

    # 2. Network policy — PUBLIC for hackathon (no VPC peering needed).
    print("--- network policy ---")
    net_status = _create_or_update_policy(
        aoss, NETWORK_POLICY_NAME, "network",
        [{
            "Rules": [
                {
                    "Resource": [f"collection/{COLLECTION_NAME}"],
                    "ResourceType": "collection",
                },
                {
                    "Resource": [f"collection/{COLLECTION_NAME}"],
                    "ResourceType": "dashboard",
                },
            ],
            "AllowFromPublic": True,
        }],
    )
    print(f"  {net_status}: {NETWORK_POLICY_NAME}")
    print()

    # 3. Data access policy — lets our role read+write the collection.
    print("--- data access policy ---")
    try:
        aoss.create_access_policy(
            name=DATA_ACCESS_POLICY_NAME,
            type="data",
            policy=json.dumps([{
                "Rules": [
                    {
                        "Resource": [f"collection/{COLLECTION_NAME}"],
                        "Permission": [
                            "aoss:CreateCollectionItems",
                            "aoss:DeleteCollectionItems",
                            "aoss:UpdateCollectionItems",
                            "aoss:DescribeCollectionItems",
                        ],
                        "ResourceType": "collection",
                    },
                    {
                        "Resource": [f"index/{COLLECTION_NAME}/*"],
                        "Permission": [
                            "aoss:CreateIndex",
                            "aoss:DeleteIndex",
                            "aoss:UpdateIndex",
                            "aoss:DescribeIndex",
                            "aoss:ReadDocument",
                            "aoss:WriteDocument",
                        ],
                        "ResourceType": "index",
                    },
                ],
                "Principal": [role_arn],
                "Description": "HyperPersona worker + server role",
            }]),
        )
        print(f"  created: {DATA_ACCESS_POLICY_NAME}")
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConflictException":
            existing = aoss.get_access_policy(name=DATA_ACCESS_POLICY_NAME, type="data")
            version = existing["accessPolicyDetail"]["policyVersion"]
            try:
                aoss.update_access_policy(
                    name=DATA_ACCESS_POLICY_NAME,
                    type="data",
                    policyVersion=version,
                    policy=json.dumps([{
                        "Rules": [
                            {
                                "Resource": [f"collection/{COLLECTION_NAME}"],
                                "Permission": [
                                    "aoss:CreateCollectionItems",
                                    "aoss:DeleteCollectionItems",
                                    "aoss:UpdateCollectionItems",
                                    "aoss:DescribeCollectionItems",
                                ],
                                "ResourceType": "collection",
                            },
                            {
                                "Resource": [f"index/{COLLECTION_NAME}/*"],
                                "Permission": [
                                    "aoss:CreateIndex",
                                    "aoss:DeleteIndex",
                                    "aoss:UpdateIndex",
                                    "aoss:DescribeIndex",
                                    "aoss:ReadDocument",
                                    "aoss:WriteDocument",
                                ],
                                "ResourceType": "index",
                            },
                        ],
                        "Principal": [role_arn],
                        "Description": "HyperPersona worker + server role",
                    }]),
                )
                print(f"  updated: {DATA_ACCESS_POLICY_NAME}")
            except ClientError as e2:
                if "No changes detected" in str(e2):
                    print(f"  unchanged: {DATA_ACCESS_POLICY_NAME}")
                else:
                    raise
        else:
            raise
    print()

    # 4. Collection
    print("--- collection ---")
    _ensure_collection(aoss, COLLECTION_NAME)
    print()

    # 5. Wait for ACTIVE
    print("--- waiting for ACTIVE ---")
    coll = _wait_for_active(aoss, COLLECTION_NAME)
    endpoint = coll["collectionEndpoint"]
    print(f"  ACTIVE  endpoint={endpoint}")
    print()

    # 6. Create indexes (data plane via SigV4-signed HTTPS)
    print("--- indexes ---")
    _create_indexes(endpoint)
    print()

    print("=" * 60)
    print(f"AOSS_ENDPOINT={endpoint}")
    print()
    print("Add to .env:")
    print(f"  VECTOR_MODE=aoss")
    print(f"  AOSS_ENDPOINT={endpoint}")
    print()
    print("Then: make down && make up && make test-e2e")
    return 0


if __name__ == "__main__":
    sys.exit(main())
