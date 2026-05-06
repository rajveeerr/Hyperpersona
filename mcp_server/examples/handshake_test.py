"""MCP handshake-only smoke — proves the protocol layer works.

This script does NOT require the upstream HyperPersona REST API to be
reachable. It only exercises the MCP wire protocol: spawn the server,
initialize the session, list tools / resources / prompts.

Useful for proving the package is integrable even when the backend is
in a partial state (e.g. expired AWS creds for the upstream service).
"""

from __future__ import annotations

import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def run() -> int:
    # Dummy JWT so Config.from_env() doesn't refuse to start.
    server_params = StdioServerParameters(
        command="hyperpersona-mcp",
        env={
            "HYPERPERSONA_BASE_URL": os.getenv("HYPERPERSONA_BASE_URL", "http://server:8000"),
            "HYPERPERSONA_JWT": "dummy-token-for-handshake-test",
            "PATH": os.environ.get("PATH", ""),
        },
    )

    print("=" * 70)
    print("MCP HANDSHAKE TEST — protocol-only, no upstream API call")
    print("=" * 70)

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            init_result = await session.initialize()
            print(f"\n✓ Server name    : {init_result.serverInfo.name}")
            print(f"✓ Server version : {init_result.serverInfo.version}")
            print(f"✓ Protocol version: {init_result.protocolVersion}")

            tools = await session.list_tools()
            print(f"\n✓ Tools advertised ({len(tools.tools)}):")
            for t in tools.tools:
                desc = (t.description or "").splitlines()[0][:65]
                print(f"    • {t.name:30}  {desc}")
                # Show input schema — proves FastMCP generated it correctly
                schema = t.inputSchema or {}
                props = schema.get("properties", {})
                if props:
                    args = ", ".join(
                        f"{k}: {v.get('type', '?')}"
                        for k, v in list(props.items())[:4]
                    )
                    print(f"      args: ({args})")

            resources = await session.list_resources()
            print(f"\n✓ Resources advertised ({len(resources.resources)}):")
            for r in resources.resources:
                print(f"    • {r.uri}")

            try:
                prompts = await session.list_prompts()
                print(f"\n✓ Prompts advertised ({len(prompts.prompts)}):")
                for p in prompts.prompts:
                    print(f"    • {p.name}")
            except Exception as e:
                print(f"\n  (prompts list: {type(e).__name__})")

    print()
    print("=" * 70)
    print("MCP PROTOCOL LAYER WORKS")
    print("Any MCP-aware client can connect; tool calls will succeed once the")
    print("upstream HyperPersona REST API is reachable with valid creds.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
