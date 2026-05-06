"""Module-level singletons.

Every route used to instantiate its own DynamoClient and Redis pool. Five
routes × N server replicas = a lot of duplicate connections to DDB and
Redis. One client per process is plenty.

Two Redis clients on purpose:
  - redis_client       — sync; used by middleware, cache, and most routes
                         (their ops are sub-ms and fine inside async handlers)
  - redis_async        — async; used by /recommend's long BRPOP wait so a
                         single uvicorn process can multiplex many in-flight
                         /recommend requests instead of pinning a thread per
                         request for up to 30s.

Usage in routes:
    from ..deps import dynamo, redis_client, redis_async, vectors
"""

import redis.asyncio as aioredis

from shared.bedrock import make_bedrock_client
from shared.dynamo import DynamoClient
from shared.queue import make_job_queue, make_redis
from shared.vector_store import make_vector_store

from .config import settings


dynamo = DynamoClient(
    endpoint=settings.dynamodb_endpoint,
    region=settings.aws_region,
)

redis_client = make_redis(settings.redis_url)

# Async Redis for the /recommend BRPOP. Same Redis instance, just non-blocking.
redis_async = aioredis.from_url(settings.redis_url, decode_responses=True)

# Job queue (Redis or SQS). Per-job result channel still uses Redis.
job_queue = make_job_queue(
    mode=settings.queue_mode,
    redis_client=redis_client,
    sqs_queue_url=settings.sqs_queue_url,
    region=settings.aws_region,
)

vectors = make_vector_store(
    mode=settings.vector_mode,
    host=settings.opensearch_host,
    port=settings.opensearch_port,
    aoss_endpoint=settings.aoss_endpoint,
    region=settings.aws_region,
)

# Bedrock — server uses embed() to vectorize search queries against the
# product-catalog OpenSearch index. Mock mode (SHA256) works for dev with
# no AWS creds.
bedrock = make_bedrock_client(
    mode=settings.bedrock_mode,
    region=settings.bedrock_region,
    text_model=settings.bedrock_text_model,
    embed_model=settings.bedrock_embed_model,
)
