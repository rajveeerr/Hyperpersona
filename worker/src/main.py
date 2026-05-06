import logging

from shared.bedrock import make_bedrock_client
from shared.dynamo import DynamoClient
from shared.logging_config import configure_json_logging
from shared.pii import make_pii_redactor
from shared.queue import make_job_queue, make_redis
from shared.s3_sync import make_trace_sync
from shared.vector_store import make_vector_store

from .agents.recommend_supervisor import make_recommend_supervisor
from .agents.supervisor import make_supervisor
from .config import settings
from .job_handler import dispatch
from .trace_logger import TraceLogger

configure_json_logging()
log = logging.getLogger("worker")


def main() -> None:
    redis_client = make_redis(settings.redis_url)
    job_queue = make_job_queue(
        mode=settings.queue_mode,
        redis_client=redis_client,
        sqs_queue_url=settings.sqs_queue_url,
        region=settings.aws_region,
    )
    dynamo = DynamoClient(endpoint=settings.dynamodb_endpoint, region=settings.aws_region)
    # Build one Bedrock client per task. Each task can use a different
    # text model (Sonnet for cheap/routine work, Opus for judgment-heavy);
    # they all share Titan for embeddings since there's no upside to
    # switching that.
    def _bedrock(text_model: str):
        return make_bedrock_client(
            mode=settings.bedrock_mode,
            region=settings.bedrock_region,
            text_model=text_model,
            embed_model=settings.bedrock_embed_model,
        )

    analyzer_model = settings.bedrock_analyzer_model or settings.bedrock_text_model
    recommender_model = settings.bedrock_recommender_model or settings.bedrock_text_model
    verifier_model = settings.bedrock_verifier_model or settings.bedrock_text_model

    bedrock = _bedrock(settings.bedrock_text_model)              # default / fallback
    bedrock_analyzer = _bedrock(analyzer_model)
    bedrock_recommender = _bedrock(recommender_model)
    bedrock_verifier = _bedrock(verifier_model)
    log.info(
        "bedrock per-task models: analyzer=%s recommender=%s verifier=%s orchestrator=%s",
        analyzer_model.rsplit("/", 1)[-1],
        recommender_model.rsplit("/", 1)[-1],
        verifier_model.rsplit("/", 1)[-1],
        (settings.bedrock_orchestrator_model or settings.bedrock_text_model).rsplit("/", 1)[-1],
    )
    vectors = make_vector_store(
        mode=settings.vector_mode,
        host=settings.opensearch_host,
        port=settings.opensearch_port,
        aoss_endpoint=settings.aoss_endpoint,
        region=settings.aws_region,
    )
    tracer = TraceLogger(settings.traces_db_dir)
    redactor = make_pii_redactor(mode=settings.pii_mode, region=settings.aws_region)
    trace_sync = make_trace_sync(
        mode=settings.trace_sync_mode,
        bucket=settings.s3_traces_bucket,
        region=settings.aws_region,
    )
    supervisor = make_supervisor(
        mode=settings.supervisor_mode,
        dynamo=dynamo, bedrock=bedrock_analyzer, vectors=vectors,
        tracer=tracer, settings=settings, redactor=redactor,
    )
    recommend_supervisor = make_recommend_supervisor(
        mode=settings.recommend_mode,
        bedrock_recommender=bedrock_recommender,
        bedrock_verifier=bedrock_verifier,
        vectors=vectors,
        tracer=tracer, settings=settings,
        dynamo=dynamo,
    )

    ctx = {
        "dynamo": dynamo,
        "bedrock": bedrock,
        "vectors": vectors,
        "tracer": tracer,
        "supervisor": supervisor,
        "recommend_supervisor": recommend_supervisor,
        "trace_sync": trace_sync,
        "queue": job_queue,
        "redis": redis_client,
        "settings": settings,
    }

    redis_client.ping()
    log.info(
        "worker started, waiting for jobs (queue=%s, bedrock=%s, vectors=%s, "
        "supervisor=%s, recommend=%s, pii=%s, trace_sync=%s)",
        settings.queue_mode, settings.bedrock_mode, settings.vector_mode,
        settings.supervisor_mode, settings.recommend_mode, settings.pii_mode,
        settings.trace_sync_mode,
    )

    while True:
        try:
            popped = job_queue.pop(timeout=20)
            if popped is None:
                continue
            try:
                dispatch(popped.payload, ctx)
            finally:
                # ack regardless — completed and failed jobs are both
                # finalized in DDB by job_handler. SQS visibility-timeout
                # redelivery would re-process a job we already marked failed.
                popped.ack()
        except KeyboardInterrupt:
            log.info("worker shutting down")
            break
        except Exception:
            log.exception("worker loop error — continuing")


if __name__ == "__main__":
    main()
