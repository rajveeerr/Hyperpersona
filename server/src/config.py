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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
