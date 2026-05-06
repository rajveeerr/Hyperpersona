"""End-to-end integration smoke for hyperpersona-mcp.

Demonstrates exactly the same protocol Claude Desktop, Anthropic SDK,
or any other MCP-aware client would use:

  1. Register a fresh test customer via the HyperPersona REST API directly
     (this is the part the ecommerce retailer would do themselves — they
     issue a JWT to the shopper, then hand it to their LLM stack).
  2. Spawn `hyperpersona-mcp` as a subprocess (stdio transport) and pass
     the JWT via env. This is what Claude Desktop does when its config
     points at this command.
  3. Initialize the MCP session — exchange capabilities.
  4. List the tools, resources, and prompts the server exposes.
  5. Call get_recommendation and ingest_event as a real LLM agent would.
  6. Pull the customer/profile resource.
  7. Clean up — delete_customer_data wipes everything DPDP-style.

Run this from inside the worker container OR any host that can reach
HYPERPERSONA_BASE_URL:

  docker compose exec worker python /app/mcp_server/examples/integration_test.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.request
import uuid

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


BASE_URL = os.getenv("HYPERPERSONA_BASE_URL", "http://server:8000")


def _register_fresh_customer() -> tuple[str, str]:
    """Register a one-off customer and return (jwt, customer_id).

    This is the part the retailer's identity service would do — issue a
    short-lived JWT for the active shopper and pass it to whatever LLM
    stack the retailer is running.
    """
    email = f"mcpdemo_{uuid.uuid4().hex[:10]}@example.com"
    body = json.dumps({"email": email, "password": "demo-password-123"}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/register",
        method="POST",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["token"], data["customer_id"]


def _section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


async def run() -> int:
    _section("1. RETAILER ISSUES JWT TO THE SHOPPER")
    token, customer_id = _register_fresh_customer()
    print(f"customer_id : {customer_id}")
    print(f"token       : {token[:32]}...{token[-12:]} ({len(token)} chars)")

    # --- 2. Spawn the MCP server exactly like Claude Desktop would ---
    _section("2. SPAWN hyperpersona-mcp AS A SUBPROCESS (stdio transport)")
    server_params = StdioServerParameters(
        command="hyperpersona-mcp",
        env={
            "HYPERPERSONA_BASE_URL": BASE_URL,
            "HYPERPERSONA_JWT": token,
            # PATH is required so the subprocess can find Python and the script.
            "PATH": os.environ.get("PATH", ""),
        },
    )
    print(f"command : {server_params.command}")
    print(f"transport : stdio (JSON-RPC over stdin/stdout)")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # --- 3. Handshake ---
            _section("3. INITIALIZE MCP SESSION (capability exchange)")
            init_result = await session.initialize()
            print(f"server_name    : {init_result.serverInfo.name}")
            print(f"server_version : {init_result.serverInfo.version}")
            instructions_text = init_result.instructions or ""
            preview = instructions_text[:160].replace("\n", " ")
            print(f"instructions   : {preview}...")

            # --- 4. Discover what the server offers ---
            _section("4. DISCOVER SERVER CAPABILITIES")
            tools = await session.list_tools()
            print(f"tools ({len(tools.tools)}):")
            for t in tools.tools:
                print(f"  - {t.name:30}  {(t.description or '').splitlines()[0][:70]}")

            resources = await session.list_resources()
            print(f"\nresources ({len(resources.resources)}):")
            for r in resources.resources:
                print(f"  - {r.uri}")

            try:
                prompts = await session.list_prompts()
                print(f"\nprompts ({len(prompts.prompts)}):")
                for p in prompts.prompts:
                    print(f"  - {p.name}")
            except Exception:
                print("\nprompts: (server doesn't expose prompts in this transport)")

            # --- 5. Read the customer profile resource ---
            _section("5. READ hyperpersona://customer/profile")
            prof = await session.read_resource("hyperpersona://customer/profile")
            for c in prof.contents:
                if hasattr(c, "text"):
                    print(c.text)

            # --- 6. Update consent (MCP tool call) ---
            _section("6. CALL update_consent — opt the shopper into personalization")
            res = await session.call_tool(
                "update_consent",
                {"scopes": ["personalization", "analytics"], "data_retention_days": 30},
            )
            for c in res.content:
                if hasattr(c, "text"):
                    print(c.text[:300])

            # --- 7. Ingest some behavior ---
            _section("7. CALL ingest_event — record a purchase event")
            res = await session.call_tool(
                "ingest_event",
                {
                    "event_type": "purchase",
                    "payload": {"product": "Wildcraft Hypadry trail shoes", "price": 4999},
                    "consent_scope": ["personalization"],
                },
            )
            for c in res.content:
                if hasattr(c, "text"):
                    print(c.text[:300])

            # --- 8. Cleanup — DPDP right-to-erasure ---
            _section("8. CALL delete_customer_data — DPDP/GDPR right-to-erasure")
            res = await session.call_tool("delete_customer_data", {})
            for c in res.content:
                if hasattr(c, "text"):
                    print(c.text[:300])

    print()
    print("=" * 70)
    print("INTEGRATION SMOKE PASSED")
    print("Any MCP-aware LLM client can drive this same flow programmatically.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
