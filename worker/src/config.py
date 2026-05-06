from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379"
    dynamodb_endpoint: str = "http://localhost:8001"
    aws_region: str = "us-east-1"

    # Bedrock — flip to "real" once AWS creds are available
    bedrock_mode: str = "mock"
    bedrock_region: str = "us-east-1"
    bedrock_text_model: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    bedrock_embed_model: str = "amazon.titan-embed-text-v2:0"

    # Per-task model assignment. Each defaults to bedrock_text_model when
    # left empty so existing single-model setups keep working. Production
    # mapping:
    #   - analyzer       Sonnet 4.5 (cheaper, fast enough for fact extraction)
    #   - orchestrator   Sonnet 4.5 (Strands tool routing — short, deterministic)
    #   - recommender    Opus 4.7   (creative + grounded — premium quality)
    #   - verifier       Opus 4.7   (highest accuracy on judgment)
    bedrock_analyzer_model: str = ""
    bedrock_orchestrator_model: str = ""
    bedrock_recommender_model: str = ""
    bedrock_verifier_model: str = ""

    # Supervisor — "manual" (current orchestrator), "strands" (Claude picks
    # tool order via strands.Agent), or "agentcore" (Phase 10, stub for now).
    # strands requires bedrock_mode == "real".
    supervisor_mode: str = "manual"

    # Recommend supervisor — same options minus agentcore. Independent of
    # supervisor_mode so the ingest path and recommend path can run different
    # modes (e.g. fast manual ingest + strands-traced recommend).
    recommend_mode: str = "manual"

    # PII detector — "regex" (free, fast, limited) or "comprehend" (AWS,
    # ~$0.0001/100chars, catches SSN/CC/IP/MAC/address that regex misses).
    pii_mode: str = "regex"

    # Trace sync — "local" (default; SQLite stays on the shared volume) or
    # "s3" (after each job, the worker's SQLite file is uploaded to S3 so
    # traces survive worker restarts and the AgentCore microVM lifecycle).
    trace_sync_mode: str = "local"
    s3_traces_bucket: str = ""

    # AgentCore — full ARN of the deployed agent runtime. Required when
    # SUPERVISOR_MODE=agentcore. Set after `agentcore deploy` returns the ARN.
    agentcore_agent_arn: str = ""

    # Job queue backend — "redis" (default; uses redis_url) or "sqs"
    # (durable AWS-managed; requires sqs_queue_url). Per-job result
    # channel stays on Redis regardless.
    queue_mode: str = "redis"
    sqs_queue_url: str = ""

    # Vector store — "memory" (process-local), "opensearch" (Docker
    # container at host:port), or "aoss" (AWS OpenSearch Serverless;
    # requires aoss_endpoint).
    vector_mode: str = "opensearch"
    opensearch_host: str = "opensearch"
    opensearch_port: int = 9200
    aoss_endpoint: str = ""

    # Trace SQLite directory — shared volume between worker and server.
    # Each worker writes its own file (agent_traces_{hostname}.db) inside
    # this dir; the server globs the dir to read across all workers.
    traces_db_dir: str = "/app/traces"

    # Event processing mode:
    #   "full"   — every event runs the full supervisor pipeline (max accuracy)
    #   "tiered" — only HIGH_SIGNAL_EVENT_TYPES run the supervisor; the rest
    #              are cheap-stored and rolled up into session summaries.
    # Default is "full" so we don't trade accuracy for cost until we have to.
    event_processing_mode: str = "full"

    # Tiered-only: number of cheap-stored events before auto-summarize fires.
    # Ignored when event_processing_mode == "full".
    session_flush_threshold: int = 3

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
