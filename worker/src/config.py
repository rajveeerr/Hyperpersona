from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379"
    dynamodb_endpoint: str = "http://localhost:8001"
    aws_region: str = "us-east-1"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
