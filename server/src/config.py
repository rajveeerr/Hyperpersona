from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379"
    dynamodb_endpoint: str = "http://localhost:8001"
    aws_region: str = "us-east-1"

    api_key: str = "test-key"
    # Directory containing per-worker SQLite trace files. Server globs
    # everything in this dir matching agent_traces_*.db.
    traces_db_dir: str = "/app/traces"
    opensearch_host: str = "opensearch"
    opensearch_port: int = 9200

    # Backpressure / rate limits (Step 4)
    max_queue_depth: int = 10000
    max_events_per_customer_per_min: int = 100
    max_requests_per_key_per_min: int = 1000

    # JWT auth — used by middleware/auth.py and routes/auth.py
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24

    # Bedrock — server uses embed() to vectorize search queries.
    bedrock_mode: str = "mock"
    bedrock_region: str = "us-east-1"
    bedrock_text_model: str = "anthropic.claude-sonnet-4-5-20250929-v1:0"
    bedrock_embed_model: str = "amazon.titan-embed-text-v2:0"

    # Vector store — same modes the worker uses.
    vector_mode: str = "opensearch"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
