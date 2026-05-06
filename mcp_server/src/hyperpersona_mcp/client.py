"""Async HTTP client wrapping HyperPersona's REST API.

Centralizes auth, base URL, error mapping. MCP tools should never call
httpx directly — they go through this client so token refresh, error
surfacing, and observability are consistent.

Auth flow:
  1. If HYPERPERSONA_JWT is set, use it directly.
  2. Otherwise login via POST /login with email+password.
  3. Token caches in-memory for the process lifetime. We don't persist —
     MCP servers are expected to be ephemeral subprocesses.

Error handling:
  - 401/403 → AuthError so the MCP host can surface a clear message
  - 4xx → HyperPersonaAPIError with the server's detail
  - 5xx → HyperPersonaAPIError with a "service issue" hint
  - timeouts/network → wrapped as HyperPersonaAPIError("upstream timeout")
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import Config

log = logging.getLogger(__name__)


class HyperPersonaAPIError(RuntimeError):
    """Base error raised when the upstream API misbehaves."""


class AuthError(HyperPersonaAPIError):
    """401/403 from the upstream — the MCP host should re-auth."""


class HyperPersonaClient:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._token: str | None = config.jwt or None
        self._http = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=httpx.Timeout(config.request_timeout_s),
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    # ---- auth -----------------------------------------------------------

    async def _ensure_token(self) -> str:
        """Return the cached JWT, logging in on first call if needed."""
        if self._token:
            return self._token
        if not (self._config.email and self._config.password):
            raise AuthError("no JWT and no email/password — cannot authenticate")
        try:
            resp = await self._http.post(
                "/login",
                json={"email": self._config.email, "password": self._config.password},
            )
        except httpx.HTTPError as e:
            raise HyperPersonaAPIError(f"login network error: {e}") from e
        if resp.status_code != 200:
            raise AuthError(f"login failed: {resp.status_code} {resp.text[:200]}")
        body = resp.json()
        self._token = body["token"]
        log.info("hyperpersona-mcp: logged in as %s", body.get("customer_id", "?")[:8])
        return self._token

    async def _request(
        self, method: str, path: str, json: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        """Authenticated request. Refreshes token on 401 once."""
        token = await self._ensure_token()
        headers = {"Authorization": f"Bearer {token}"}
        try:
            resp = await self._http.request(
                method, path, headers=headers, json=json, params=params,
            )
        except httpx.TimeoutException as e:
            raise HyperPersonaAPIError(f"upstream timeout calling {path}: {e}") from e
        except httpx.HTTPError as e:
            raise HyperPersonaAPIError(f"network error calling {path}: {e}") from e

        # Token expired — try once to re-login, then retry the call.
        if resp.status_code == 401 and self._config.email and self._config.password:
            log.info("hyperpersona-mcp: token expired, re-authenticating")
            self._token = None
            token = await self._ensure_token()
            resp = await self._http.request(
                method, path,
                headers={"Authorization": f"Bearer {token}"},
                json=json, params=params,
            )

        if resp.status_code in (401, 403):
            detail = self._safe_detail(resp)
            raise AuthError(f"{resp.status_code}: {detail}")
        if resp.status_code >= 500:
            raise HyperPersonaAPIError(f"upstream {resp.status_code}: service issue")
        if resp.status_code >= 400:
            detail = self._safe_detail(resp)
            raise HyperPersonaAPIError(f"{resp.status_code}: {detail}")
        return resp.json() if resp.content else {}

    @staticmethod
    def _safe_detail(resp: httpx.Response) -> str:
        try:
            data = resp.json()
            return str(data.get("detail") or data.get("error") or data)[:200]
        except Exception:
            return resp.text[:200]

    # ---- public API surface that MCP tools call ------------------------

    async def whoami(self) -> dict:
        """Resolve the current customer_id via /consent (any auth'd route works)."""
        # We don't have a /me endpoint yet, so use /consent — it returns
        # the customer_id from the JWT.
        try:
            return await self._request("GET", "/consent")
        except HyperPersonaAPIError as e:
            # 404 = no consent record yet; that's fine — return minimal shape.
            if "404" in str(e):
                return {"customer_id": None, "scopes": []}
            raise

    async def ingest_event(
        self, event_type: str, payload: dict,
        client_event_id: str | None = None,
        consent_scope: list[str] | None = None,
    ) -> dict:
        import uuid
        body = {
            "client_event_id": client_event_id or str(uuid.uuid4()),
            "event_type": event_type,
            "payload": payload,
        }
        if consent_scope:
            body["consent_scope"] = consent_scope
        return await self._request("POST", "/events", json=body)

    async def get_recommendation(self, context: str, limit: int = 5) -> dict:
        return await self._request(
            "GET", "/recommend",
            params={"context": context, "limit": limit},
        )

    async def get_consent(self) -> dict:
        return await self._request("GET", "/consent")

    async def update_consent(
        self, scopes: list[str], data_retention_days: int = 90,
    ) -> dict:
        return await self._request(
            "POST", "/consent",
            json={"scopes": scopes, "data_retention_days": data_retention_days},
        )

    async def delete_customer_data(self) -> dict:
        return await self._request("DELETE", "/customer")

    async def get_recommendation_trace(self, job_id: str) -> Any:
        return await self._request("GET", f"/traces/{job_id}")
