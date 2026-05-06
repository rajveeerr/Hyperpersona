import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from shared.logging_config import configure_json_logging

from .config import settings
from .deps import redis_client
from .middleware.auth import JWTAuthMiddleware
from .middleware.rate_limit import RateLimitMiddleware
from .routes import auth as auth_route
from .routes import consent as consent_route
from .routes import customer as customer_route
from .routes import events as events_route
from .routes import jobs as jobs_route
from .routes import metrics as metrics_route
from .routes import recommend as recommend_route
from .routes import traces as traces_route

configure_json_logging()
log = logging.getLogger("server")

app = FastAPI(title="HyperPersona Server", version="0.14.0")

# Middleware order: last added runs FIRST. JWT auth must run before rate
# limit so unauth'd requests get 401 (and the rate limit can read the
# resolved customer_id from request.state).
app.add_middleware(
    RateLimitMiddleware,
    redis_client=redis_client,
    limit=settings.max_requests_per_key_per_min,
    window_s=60,
)
app.add_middleware(JWTAuthMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error", extra={"path": request.url.path})
    return JSONResponse(
        status_code=500,
        content={"error": "internal server error"},
    )


app.include_router(auth_route.router)
app.include_router(consent_route.router)
app.include_router(customer_route.router)
app.include_router(events_route.router)
app.include_router(jobs_route.router)
app.include_router(metrics_route.router)
app.include_router(recommend_route.router)
app.include_router(traces_route.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "server"}


@app.get("/")
def root() -> dict:
    return {"service": "hyperpersona-server", "version": "0.13.0"}
