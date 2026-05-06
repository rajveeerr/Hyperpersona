"""Environment-driven configuration for the HyperPersona MCP server.

The server is a thin proxy between an MCP client (Claude Desktop, custom
LLM apps, AWS Bedrock agents) and HyperPersona's REST API. Every setting
here lives in the host's environment so the same package works against
local dev (http://localhost:8000) or production (https://api.hyperpersona.dev).

Auth model — pick ONE of these on startup:
  Option A: HYPERPERSONA_JWT
    A pre-issued bearer token. Used for short-lived sessions (e.g. when
    a retailer's identity service mints a JWT for one shopper and passes
    it to their LLM stack).

  Option B: HYPERPERSONA_EMAIL + HYPERPERSONA_PASSWORD
    The MCP server logs in on startup via POST /login and caches the
    JWT for the lifetime of the process. Used for headless dev/demo
    use where there's no per-request auth surface.

Auth fails fast if neither option is set — the server refuses to start.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Immutable view of the environment at startup."""

    # Where the HyperPersona REST API is reachable. Default to local dev.
    base_url: str

    # Pre-issued JWT (option A). Empty string when not provided.
    jwt: str

    # Login credentials (option B). Empty when not provided.
    email: str
    password: str

    # HTTP timeout in seconds for any single REST call.
    request_timeout_s: float

    # Optional client-side override of the default recommendation cache key.
    # When set, recommendations land in a tenant-scoped namespace.
    tenant_id: str

    @classmethod
    def from_env(cls) -> "Config":
        cfg = cls(
            base_url=os.getenv("HYPERPERSONA_BASE_URL", "http://localhost:8000").rstrip("/"),
            jwt=os.getenv("HYPERPERSONA_JWT", "").strip(),
            email=os.getenv("HYPERPERSONA_EMAIL", "").strip(),
            password=os.getenv("HYPERPERSONA_PASSWORD", "").strip(),
            request_timeout_s=float(os.getenv("HYPERPERSONA_TIMEOUT_S", "60")),
            tenant_id=os.getenv("HYPERPERSONA_TENANT_ID", "").strip(),
        )
        if not cfg.jwt and not (cfg.email and cfg.password):
            raise RuntimeError(
                "HyperPersona MCP needs either HYPERPERSONA_JWT (preferred) "
                "or HYPERPERSONA_EMAIL + HYPERPERSONA_PASSWORD set in the "
                "environment. See README for setup."
            )
        return cfg
