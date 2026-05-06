"""Seed the products + categories tables and the product-catalog vector index.

Reads the JSON seed files under server/src/data/, then for each product
calls CatalogWriter.upsert_product so Dynamo + OpenSearch + (when run in
the server process) the catalog snapshot stay in lockstep.

Idempotent — re-running overwrites both stores with the current seed
values.

Runs in the SERVER container because it imports the server-side schema
and writer modules. The server container has BEDROCK_* env vars wired:

  make seed-products
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

# Path setup that works in both contexts:
#   - Docker container: /app/{src,shared} are bind-mounted; /app on path.
#   - Host (.venv):    repo_root/{shared,server/src}; need both repo_root
#                       AND repo_root/server on the path so `from src.…`
#                       imports resolve to server/src/.
if Path("/app/src").exists():
    sys.path.insert(0, "/app")
else:
    _here = Path(__file__).resolve()
    _repo = _here.parent.parent
    sys.path.insert(0, str(_repo / "server"))  # makes `import src.…` work
    sys.path.insert(0, str(_repo))              # makes `import shared.…` work

from shared.bedrock import make_bedrock_client  # noqa: E402
from shared.dynamo import DynamoClient  # noqa: E402
from shared.logging_config import configure_json_logging  # noqa: E402
from shared.vector_store import make_vector_store  # noqa: E402

from src.schemas.catalog import Product  # noqa: E402
from src.services.catalog_snapshot import CatalogSnapshot  # noqa: E402
from src.services.catalog_writer import CatalogWriter  # noqa: E402

configure_json_logging()
log = logging.getLogger("seed_products")


# Inside the server container, server/src is bind-mounted at /app/src,
# so the seed JSON lives at /app/src/data/. Outside docker (host venv),
# point at the source-tree copy.
def _default_seed_dir() -> Path:
    if Path("/app/src/data").exists():
        return Path("/app/src/data")
    return Path(__file__).resolve().parent.parent / "server" / "src" / "data"


SEED_DIR = Path(os.getenv("SEED_DATA_DIR", str(_default_seed_dir())))


def _load_json(path: Path) -> list[dict]:
    with path.open() as f:
        return json.load(f)


def main() -> None:
    dynamo = DynamoClient(
        endpoint=os.getenv("DYNAMODB_ENDPOINT", "http://localhost:8001"),
        region=os.getenv("AWS_REGION", "us-east-1"),
    )
    bedrock = make_bedrock_client(
        mode=os.getenv("BEDROCK_MODE", "real"),
        region=os.getenv("BEDROCK_REGION", "us-east-1"),
        text_model=os.getenv("BEDROCK_TEXT_MODEL", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"),
        embed_model=os.getenv("BEDROCK_EMBED_MODEL", "amazon.titan-embed-text-v2:0"),
    )
    vectors = make_vector_store(
        mode=os.getenv("VECTOR_MODE", "opensearch"),
        host=os.getenv("OPENSEARCH_HOST", "opensearch"),
        port=int(os.getenv("OPENSEARCH_PORT", "9200")),
        aoss_endpoint=os.getenv("AOSS_ENDPOINT", ""),
        region=os.getenv("AWS_REGION", "us-east-1"),
    )
    snapshot = CatalogSnapshot(dynamo)  # not refreshed; we just need it for the writer

    writer = CatalogWriter(dynamo=dynamo, bedrock=bedrock, vectors=vectors, snapshot=snapshot)

    # Categories first (Dynamo only — they have no vector counterpart).
    categories = _load_json(SEED_DIR / "categories.seed.json")
    for cat in categories:
        dynamo.put_category(cat)
    log.info("seeded %d categories", len(categories))

    # Products via CatalogWriter so Dynamo + OpenSearch stay in sync.
    products = _load_json(SEED_DIR / "products.seed.json")
    for raw in products:
        product = Product.model_validate(raw)
        writer.upsert_product(product)
    log.info("seeded %d products (Dynamo + product-catalog vectors)", len(products))


if __name__ == "__main__":
    main()
