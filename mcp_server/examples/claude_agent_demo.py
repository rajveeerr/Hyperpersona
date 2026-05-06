"""End-to-end demo: Claude as an MCP host, choosing HyperPersona tools.

Spawns hyperpersona-mcp as an MCP server, connects it to a real Claude
agent via the Anthropic SDK + MCP client SDK, and lets Claude decide
which tools to call to answer a customer query.

This is the demo that proves "any LLM can use HyperPersona via MCP" —
because here, the actual decision-making is Claude's, not ours.

Required env:
  ANTHROPIC_API_KEY    direct Anthropic API key (sk-ant-...)
  HYPERPERSONA_BASE_URL  same as integration_test.py
  HYPERPERSONA_JWT       JWT for the test customer

If you don't have ANTHROPIC_API_KEY, run examples/integration_test.py
instead — it exercises the same MCP surface programmatically, just
without using a real LLM as the orchestrator.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.request
import uuid

from anthropic import Anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


BASE_URL = os.getenv("HYPERPERSONA_BASE_URL", "http://server:8000")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")


USER_QUERY = (
    "I just bought Wildcraft trail running shoes for ₹4,999. "
    "Record this as a purchase event for me, then suggest what else "
    "I might need for a hiking trip this weekend."
)


def _register_customer() -> tuple[str, str]:
    email = f"demo_{uuid.uuid4().hex[:10]}@example.com"
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


async def run() -> int:
    if not ANTHROPIC_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set. See test 3 (integration_test.py) "
              "for the no-API-key alternative.", file=sys.stderr)
        return 2

    print("=" * 70)
    print("CLAUDE-AS-AGENT MCP DEMO")
    print("=" * 70)

    token, customer_id = _register_customer()
    print(f"\ncustomer_id : {customer_id}")
    print(f"jwt         : {token[:32]}...")

    server_params = StdioServerParameters(
        command="hyperpersona-mcp",
        env={
            "HYPERPERSONA_BASE_URL": BASE_URL,
            "HYPERPERSONA_JWT": token,
            "PATH": os.environ.get("PATH", ""),
        },
    )

    anthropic = Anthropic(api_key=ANTHROPIC_KEY)

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tool_list = await session.list_tools()

            # Translate MCP tool schemas → Anthropic tool schemas.
            anthropic_tools = [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "input_schema": t.inputSchema or {"type": "object", "properties": {}},
                }
                for t in tool_list.tools
            ]
            print(f"\nMCP tools advertised to Claude: {len(anthropic_tools)}")
            for t in anthropic_tools:
                print(f"  • {t['name']}")

            print(f"\nuser query → {USER_QUERY!r}")
            print()

            messages: list[dict] = [{"role": "user", "content": USER_QUERY}]

            # Up to 5 turns of tool-use ↔ result, then final answer.
            for turn in range(1, 6):
                resp = anthropic.messages.create(
                    model="claude-sonnet-4-5",
                    max_tokens=2048,
                    tools=anthropic_tools,
                    messages=messages,
                )

                # Append Claude's reply to the conversation.
                messages.append({"role": "assistant", "content": resp.content})

                # Handle tool calls — if Claude asks for a tool, we route it
                # through our MCP session and feed the result back in.
                tool_uses = [b for b in resp.content if b.type == "tool_use"]
                texts = [b.text for b in resp.content if b.type == "text"]

                if texts:
                    for t in texts:
                        if t.strip():
                            print(f"[turn {turn}] claude says: {t.strip()[:300]}")

                if not tool_uses:
                    print(f"\n[turn {turn}] claude has no more tool calls — done.")
                    break

                tool_results: list[dict] = []
                for tu in tool_uses:
                    print(f"[turn {turn}] claude calls: {tu.name}({json.dumps(tu.input)[:120]})")
                    mcp_result = await session.call_tool(tu.name, tu.input)
                    # Concat text content blocks to a single string for the result message.
                    output_text = "".join(
                        c.text for c in mcp_result.content
                        if hasattr(c, "text")
                    )
                    print(f"           result preview: {output_text[:200]}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": output_text,
                    })

                messages.append({"role": "user", "content": tool_results})

    print()
    print("=" * 70)
    print("CLAUDE-AS-AGENT DEMO COMPLETE")
    print("Claude chose tools autonomously based on the user query.")
    print("Every tool call went through hyperpersona-mcp → REST → real AWS.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
