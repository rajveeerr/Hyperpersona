from fastapi import FastAPI

from .config import settings

app = FastAPI(title="HyperPersona Server", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok", "service": "server"}


@app.get("/")
def root():
    return {
        "service": "hyperpersona-server",
        "version": "0.1.0",
        "redis": settings.redis_url,
        "dynamodb": settings.dynamodb_endpoint,
    }
