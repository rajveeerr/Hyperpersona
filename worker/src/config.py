from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379"
    dynamodb_endpoint: str = "http://localhost:8001"
    aws_region: str = "us-east-1"

    # Bedrock — flip to "real" once AWS creds are available
    bedrock_mode: str = "mock"
    bedrock_region: str = "us-east-1"
    bedrock_text_model: str = "anthropic.claude-sonnet-4-5-20250929-v1:0"
    bedrock_embed_model: str = "amazon.titan-embed-text-v2:0"

    # Vector store — "memory" (process-local) or "opensearch" (real cluster)
    vector_mode: str = "opensearch"
    opensearch_host: str = "opensearch"
    opensearch_port: int = 9200

    # Trace SQLite path — shared volume between worker and server
    traces_db_path: str = "/app/traces/agent_traces.db"

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
