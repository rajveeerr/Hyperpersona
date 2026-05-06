"""HyperPersona MCP server — exposes our personalization platform to MCP clients.

What an MCP client gets when it connects to us:

  TOOLS (actions the client's LLM can invoke):
    - ingest_event          : record a customer event (page view, purchase, etc.)
    - get_recommendation    : fetch a personalized offer + product list
    - update_consent        : update DPDP/GDPR scopes for the customer
    - delete_customer_data  : right-to-erasure wipe (all stores, atomic)
    - get_recommendation_trace : pull the chain-of-verification audit trail
                                 for one prior recommendation

  RESOURCES (read-only context the client's LLM can pull):
    - hyperpersona://customer/profile    : consent + retention summary
    - hyperpersona://customer/recommendations : recent recommendation history

Single-customer model (Phase 1):
  Each MCP server instance is bound to ONE customer via the configured
  JWT (or email+password login). All tools act on "this customer".
  Phase 2 adds tenant/admin auth so one MCP can switch between customers.

How the client uses this:
  Claude Desktop, Anthropic SDK clients, AWS Bedrock agents, or any
  LLM-aware app implementing the MCP transport spec can spawn this
  server (stdio) or connect to a hosted instance (HTTP/SSE).
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys

from mcp.server.fastmcp import FastMCP

from .client import AuthError, HyperPersonaAPIError, HyperPersonaClient
from .config import Config

# Configure logging to stderr so stdout stays clean for the MCP JSON-RPC stream.
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("hyperpersona-mcp")


# Single FastMCP instance — registers tools/resources/prompts via decorators.
mcp = FastMCP(
    name="hyperpersona",
    instructions=(
        "HyperPersona is an agentic personalization platform. Use these "
        "tools to ingest customer events, fetch verified personalized "
        "recommendations, and manage consent/erasure. Every recommendation "
        "is grounded in stored customer facts and runs through a chain-of-"
        "verification (an Opus 4.5 verifier) so the offer text never "
        "contains fabricated products, prices, or promotions. Use "
        "get_recommendation_trace to see the per-step audit trail when you "
        "need to explain a recommendation to a human."
    ),
)


# Lazy-built singleton — created on first tool call so import is cheap.
_client: HyperPersonaClient | None = None


def _get_client() -> HyperPersonaClient:
    global _client
    if _client is None:
        cfg = Config.from_env()
        _client = HyperPersonaClient(cfg)
        log.info("hyperpersona-mcp: targeting %s", cfg.base_url)
    return _client


# ============================================================================
# TOOLS
# ============================================================================


@mcp.tool()
async def ingest_event(
    event_type: str,
    payload: dict,
    consent_scope: list[str] | None = None,
) -> dict:
    """Record a customer event (page_view, purchase, return, etc.).

    The event is enqueued via SQS and processed asynchronously by HyperPersona's
    Strands agentic pipeline — privacy gate (Comprehend PII redaction), then
    one of three analysis tools chosen by the agent based on event_type:
    full fact extraction (purchase/add_to_cart), low-signal store-only
    (page_view/scroll), or dispute-extraction (return/complaint).

    Args:
        event_type: e.g. "purchase", "add_to_cart", "page_view", "return"
        payload: event-specific fields (e.g. {"product": "...", "price": 159})
        consent_scope: optional list of scopes this event needs (defaults to ["analytics"])

    Returns:
        {"event_id": "...", "job_id": "...", "status": "queued"}
    """
    try:
        return await _get_client().ingest_event(
            event_type=event_type,
            payload=payload,
            consent_scope=consent_scope,
        )
    except AuthError as e:
        return {"error": "auth_failed", "detail": str(e)}
    except HyperPersonaAPIError as e:
        return {"error": "upstream_failed", "detail": str(e)}


@mcp.tool()
async def get_recommendation(
    context: str,
    limit: int = 5,
) -> dict:
    """Generate a personalized recommendation for the current customer.

    Behind the scenes: HyperPersona's Strands recommend agent (Sonnet 4.5
    orchestrator + Opus 4.5 recommender + Opus 4.5 verifier) chooses
    between three response paths:

      - Normal: ACE-ranked facts → Opus draft → Opus verifier (chain-of-
        verification). Every claim in the offer is cited to a source fact.
      - Cold-start: when no customer signal exists, returns trending
        products with a generic offer (no LLM cost).
      - Clarify-intent: when the customer has 3+ contradicting signals,
        returns a clarifying question instead of guessing.

    The response includes the path taken so the calling LLM can render
    appropriate UI (offer card vs question vs trending list).

    Args:
        context: the customer's stated intent (e.g. "looking for trail shoes")
        limit: max number of products in the recommendation

    Returns:
        {"offer": "...", "products": [...], "facts_used": N, "path": "...",
         "verifier_status": "...", "conflicts": [...], "job_id": "..."}
    """
    try:
        return await _get_client().get_recommendation(context=context, limit=limit)
    except AuthError as e:
        return {"error": "auth_failed", "detail": str(e)}
    except HyperPersonaAPIError as e:
        return {"error": "upstream_failed", "detail": str(e)}


@mcp.tool()
async def update_consent(
    scopes: list[str],
    data_retention_days: int = 90,
) -> dict:
    """Update the customer's consent scopes (DPDP / GDPR compliance).

    Common scopes: "personalization", "analytics", "marketing".
    Without "personalization", the customer's events are still recorded
    for analytics but no recommendations are generated. data_retention_days
    sets the DynamoDB TTL on every event row written for this customer.

    Args:
        scopes: list of scope strings the customer has agreed to
        data_retention_days: TTL in days (default 90)

    Returns:
        {"customer_id": "...", "scopes": [...], "data_retention_days": N}
    """
    try:
        return await _get_client().update_consent(
            scopes=scopes, data_retention_days=data_retention_days,
        )
    except AuthError as e:
        return {"error": "auth_failed", "detail": str(e)}
    except HyperPersonaAPIError as e:
        return {"error": "upstream_failed", "detail": str(e)}


@mcp.tool()
async def delete_customer_data() -> dict:
    """Atomically erase all data for the current customer (DPDP / GDPR right-to-erasure).

    Wipes:
      - All event rows in DynamoDB customer_events table
      - The consent record in customer_consent
      - All vectors in OpenSearch (customer-facts, behavior-embeddings,
        session-summaries — filtered by customer_id)
      - All Redis cache keys (offers, rate-limit counters)

    Synchronous — returns counts when fully complete, typically <500ms.
    Use this in response to a customer's data-erasure request.

    Returns:
        {"customer_id": "...", "events_deleted": N, "consent_deleted": bool,
         "redis_keys_deleted": N, "vector_collections_cleared": N}
    """
    try:
        return await _get_client().delete_customer_data()
    except AuthError as e:
        return {"error": "auth_failed", "detail": str(e)}
    except HyperPersonaAPIError as e:
        return {"error": "upstream_failed", "detail": str(e)}


@mcp.tool()
async def get_recommendation_trace(job_id: str) -> dict:
    """Fetch the chain-of-verification audit trail for a previous recommendation.

    Use this when an LLM agent needs to explain WHY a recommendation was made
    — e.g. customer-support contexts where the agent must justify the offer
    a customer received. The trace shows every model_call, tool_call, fact
    retrieved, and whether the verifier passed or rewrote the draft.

    Args:
        job_id: the job_id returned by a prior get_recommendation call

    Returns:
        list of step records (agent_name, step, input, output, duration_ms,
        timestamp, status) — the full audit trail for one recommendation.
    """
    try:
        rows = await _get_client().get_recommendation_trace(job_id)
        return {"job_id": job_id, "steps": rows}
    except AuthError as e:
        return {"error": "auth_failed", "detail": str(e)}
    except HyperPersonaAPIError as e:
        return {"error": "upstream_failed", "detail": str(e)}


# ============================================================================
# RESOURCES — read-only context the LLM can pull into its window
# ============================================================================


@mcp.resource("hyperpersona://customer/profile")
async def customer_profile() -> str:
    """The current customer's profile — consent scopes, retention setting.

    Use this resource to give the calling LLM background on who it's serving
    before deciding what to recommend or how to respond.
    """
    try:
        consent = await _get_client().get_consent()
        return json.dumps({
            "customer_id": consent.get("customer_id"),
            "consent_scopes": consent.get("scopes", []),
            "data_retention_days": consent.get("data_retention_days"),
            "last_updated": consent.get("last_updated"),
            "source": "hyperpersona-mcp",
        }, indent=2)
    except AuthError as e:
        return json.dumps({"error": "auth_failed", "detail": str(e)})
    except HyperPersonaAPIError as e:
        return json.dumps({"error": "upstream_failed", "detail": str(e)})


@mcp.resource("hyperpersona://system/info")
async def system_info() -> str:
    """Static metadata about this HyperPersona deployment.

    Exposed as a resource so MCP hosts can render version + capability info
    in their UI (e.g. "powered by HyperPersona v0.1.0").
    """
    return json.dumps({
        "name": "HyperPersona",
        "version": "0.1.0",
        "tagline": "Agentic personalization with chain-of-verification.",
        "tools": [
            "ingest_event", "get_recommendation", "update_consent",
            "delete_customer_data", "get_recommendation_trace",
        ],
        "resources": ["customer/profile", "system/info"],
        "verifier": "claude-opus-4-5 (chain-of-verification on every offer)",
        "vector_store": "AWS OpenSearch Serverless",
        "queue": "AWS SQS",
        "compliance": ["DPDP Act 2023", "GDPR", "CCPA"],
    }, indent=2)


# ============================================================================
# PROMPTS — templated reusable prompts the host can offer to its users
# ============================================================================


@mcp.prompt()
async def explain_recommendation(job_id: str) -> str:
    """Return a customer-facing explanation of why a particular recommendation was made.

    Useful for customer support agents handling 'why did you recommend this?'
    questions. The prompt asks the calling LLM to read the trace via
    get_recommendation_trace and produce a friendly explanation grounded in
    the facts and behavior signals.
    """
    return (
        f"A customer wants to understand why we made recommendation {job_id}.\n"
        f"\n"
        f"1. Call the get_recommendation_trace tool with job_id={job_id!r} "
        f"to fetch the audit trail.\n"
        f"2. Read each step. Identify: which facts the recommender used, "
        f"whether the verifier passed or rewrote the draft, and which "
        f"agent path was taken (normal / cold_start / clarify).\n"
        f"3. Write a 2-3 sentence customer-facing explanation that:\n"
        f"   - Cites the actual facts (e.g. \"You recently purchased X\")\n"
        f"   - Avoids technical jargon (no 'Opus', no 'verifier')\n"
        f"   - Honestly says 'we asked you to clarify because...' if the "
        f"path was clarify\n"
        f"   - Says 'this was a popular pick because we don't know your "
        f"preferences yet' if the path was cold_start\n"
        f"\n"
        f"Output ONLY the explanation text. No preamble."
    )


# ============================================================================
# Entry point
# ============================================================================


def main() -> None:
    """Run the MCP server over stdio.

    Invoked by `hyperpersona-mcp` shell command (see pyproject.toml's
    [project.scripts] entry point).
    """
    try:
        Config.from_env()
    except RuntimeError as e:
        log.error("startup failed: %s", e)
        sys.exit(2)

    log.info("hyperpersona-mcp v0.1.0 starting (stdio transport)")
    asyncio.run(_run())


async def _run() -> None:
    try:
        await mcp.run_stdio_async()
    finally:
        if _client is not None:
            await _client.aclose()


if __name__ == "__main__":
    main()
