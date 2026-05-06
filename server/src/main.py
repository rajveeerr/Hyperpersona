import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from shared.logging_config import configure_json_logging

from .config import settings
from .deps import bedrock, dynamo, redis_client, vectors
from .middleware.auth import JWTAuthMiddleware
from .middleware.rate_limit import RateLimitMiddleware
from .routes import auth as auth_route
from .routes import catalog as catalog_route
from .routes import checkout as checkout_route
from .routes import complement as complement_route
from .routes import consent as consent_route
from .routes import customer as customer_route
from .routes import events as events_route
from .routes import jobs as jobs_route
from .routes import me_cart as me_cart_route
from .routes import me_orders as me_orders_route
from .routes import me_profile as me_profile_route
from .routes import me_wishlist as me_wishlist_route
from .routes import metrics as metrics_route
from .routes import recommend as recommend_route
from .routes import reviews as reviews_route
from .routes import search as search_route
from .routes import similar_price as similar_price_route
from .routes import traces as traces_route
from .services.catalog_snapshot import CatalogSnapshot
from .services.catalog_writer import CatalogWriter

configure_json_logging()
log = logging.getLogger("server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Build the catalog snapshot once at startup. If Dynamo is empty
    # (fresh stack, no seed yet) this just logs zero rows — the seed
    # script populates Dynamo and a server reload triggers a refresh.
    snapshot = CatalogSnapshot(dynamo)
    try:
        snapshot.refresh()
    except Exception:
        log.exception("catalog snapshot refresh failed at startup — endpoints will return empty until seeded")
    app.state.catalog = snapshot
    app.state.catalog_writer = CatalogWriter(
        dynamo=dynamo, bedrock=bedrock, vectors=vectors, snapshot=snapshot,
    )
    app.state.bedrock = bedrock
    app.state.vectors = vectors
    yield


app = FastAPI(title="HyperPersona Server", version="0.14.0", lifespan=lifespan)

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
# CORS runs FIRST (last added). Preflight OPTIONS short-circuits before
# auth/rate-limit so the browser handshake doesn't get a 401.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error", extra={"path": request.url.path})
    return JSONResponse(
        status_code=500,
        content={"error": "internal server error"},
    )


app.include_router(auth_route.router)
app.include_router(complement_route.router)
app.include_router(consent_route.router)
app.include_router(customer_route.router)
app.include_router(events_route.router)
app.include_router(jobs_route.router)
app.include_router(metrics_route.router)
app.include_router(recommend_route.router)
app.include_router(similar_price_route.router)
app.include_router(traces_route.router)
# Ecommerce routes (M1)
app.include_router(catalog_route.router)
app.include_router(search_route.router)
# Ecommerce routes (M2)
app.include_router(reviews_route.router)
app.include_router(me_profile_route.router)
app.include_router(me_orders_route.router)
# Ecommerce routes (M3)
app.include_router(me_cart_route.router)
app.include_router(me_wishlist_route.router)
app.include_router(checkout_route.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "server"}


@app.get("/")
def root() -> dict:
    return {"service": "hyperpersona-server", "version": "0.13.0"}
