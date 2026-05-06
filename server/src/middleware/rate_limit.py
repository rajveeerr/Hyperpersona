"""Per-customer fixed-window rate limit (request rate, not event rate).

Counter keyed on (customer_id, current_minute) in Redis. Increment on every
request; reject with 429 once we cross the limit. The 5-second TTL slop
on the bucket key keeps Redis tidy without affecting accuracy.

Mounted AFTER JWTAuthMiddleware so unauth'd requests hit 401 first and
the resolved customer_id is available on request.state. We fall back to
the client IP (or "anonymous") if state has no customer_id — covers the
small number of authed paths that might bypass JWT in the future.

Bypassed paths: PUBLIC_PATHS in auth.py + /metrics/queue (must always be
observable, even under overload).
"""

import logging
import time

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


log = logging.getLogger(__name__)

_BYPASS_PATHS = {
    "/health", "/", "/docs", "/openapi.json", "/redoc",
    "/login", "/register", "/metrics/queue",
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        redis_client,
        limit: int,
        window_s: int = 60,
    ) -> None:
        super().__init__(app)
        self.redis = redis_client
        self.limit = limit
        self.window_s = window_s

    async def dispatch(self, request: Request, call_next):
        if request.url.path in _BYPASS_PATHS:
            return await call_next(request)

        # JWTAuthMiddleware ran first and stamped customer_id on request.state.
        identity = getattr(request.state, "customer_id", None) or (
            request.client.host if request.client else "anonymous"
        )
        window = int(time.time() // self.window_s)
        bucket = f"rate:cust_req:{identity}:{window}"

        count = self.redis.incr(bucket)
        if count == 1:
            self.redis.expire(bucket, self.window_s + 5)

        if count > self.limit:
            retry_after = self.window_s - (int(time.time()) % self.window_s)
            log.warning(
                "request rate limit exceeded",
                extra={"identity": identity, "count": count, "limit": self.limit},
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "request rate limit exceeded",
                    "limit": self.limit,
                    "window_seconds": self.window_s,
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
