"""Per-customer sliding-window rate limit (request rate, not event rate).

Sliding window via a Redis sorted set keyed on (customer_id). Each
request adds an entry with score=now (epoch seconds). On every request
we drop entries older than `window_s` and check ZCARD against the limit.

Why sliding over fixed-window: a fixed-window counter resets at the
top of every minute, so a client can do `limit` requests at 12:59:59
and another `limit` at 13:00:01 — 2× burst at the boundary. The
sliding window enforces the limit over any 60-second rolling window,
which is what most callers actually want.

Mounted AFTER JWTAuthMiddleware so unauth'd requests hit 401 first and
the resolved customer_id is available on request.state. We fall back to
the client IP (or "anonymous") if state has no customer_id.

Bypassed paths: PUBLIC_PATHS in auth.py + /metrics/queue (must always
be observable, even under overload).
"""

import logging
import time
import uuid

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
        key = f"rate:cust_req:{identity}"
        now = time.time()
        cutoff = now - self.window_s

        # Trim then count, in one round-trip.
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, cutoff)
        pipe.zcard(key)
        _, count = pipe.execute()

        if count >= self.limit:
            # Find the oldest entry in window — Retry-After is when it ages out.
            oldest = self.redis.zrange(key, 0, 0, withscores=True)
            retry_after = max(
                1,
                int((oldest[0][1] + self.window_s) - now) if oldest else self.window_s,
            )
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

        # Under the limit — record this request. Member is unique per call so
        # ZADD is always an insert (never a no-op overwrite).
        member = f"{now}:{uuid.uuid4().hex[:8]}"
        pipe = self.redis.pipeline()
        pipe.zadd(key, {member: now})
        pipe.expire(key, self.window_s + 5)
        pipe.execute()

        return await call_next(request)
