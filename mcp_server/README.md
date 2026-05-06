# hyperpersona-mcp

[Model Context Protocol](https://modelcontextprotocol.io) server for **HyperPersona** — agentic personalization with chain-of-verification, for any LLM-aware ecommerce surface.

## What this gives your LLM

Your Claude / Anthropic SDK / AWS Bedrock agent / any MCP-aware client gets:

- **5 tools** to ingest customer events, fetch verified personalized recommendations, manage consent, and pull audit trails
- **2 resources** giving the LLM read-only context about the current customer's profile and the platform's capabilities
- **1 prompt template** for customer-facing recommendation explanations
- **Built-in chain-of-verification** — every offer is fact-checked claim-by-claim by Opus 4.5 against stored customer facts. Hallucinations get rewritten before they reach the customer.
- **DPDP / GDPR ready** — `delete_customer_data` wipes DDB + 3 OpenSearch indexes + Redis atomically in <500ms

## Install

```bash
pip install hyperpersona-mcp
```

Requires Python 3.10+.

## Configure

The server needs to know where your HyperPersona instance lives and how to authenticate. Set these in your environment (for Claude Desktop, you set them inside the `mcpServers` config — see below):

| Var | Purpose | Required |
|---|---|---|
| `HYPERPERSONA_BASE_URL` | URL of your HyperPersona REST API | yes (default `http://localhost:8000`) |
| `HYPERPERSONA_JWT` | Pre-issued JWT bearer token for the customer | one of these |
| `HYPERPERSONA_EMAIL` + `HYPERPERSONA_PASSWORD` | Email/password — the MCP server logs in on startup | one of these |
| `HYPERPERSONA_TIMEOUT_S` | HTTP timeout per request | optional, default 60 |

Auth fails fast if neither `HYPERPERSONA_JWT` nor `HYPERPERSONA_EMAIL` + `HYPERPERSONA_PASSWORD` is set.

## Use with Claude Desktop

Edit `~/.config/claude/claude_desktop_config.json` (or on Windows `%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "hyperpersona": {
      "command": "hyperpersona-mcp",
      "env": {
        "HYPERPERSONA_BASE_URL": "https://api.your-shop.example.com",
        "HYPERPERSONA_EMAIL": "shopper@example.com",
        "HYPERPERSONA_PASSWORD": "your-password"
      }
    }
  }
}
```

Restart Claude Desktop. Open a chat — you'll see "hyperpersona" listed in the MCP servers menu and Claude can now invoke any of the 5 tools.

## Use from a Python script (Anthropic SDK)

```python
from anthropic import Anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="hyperpersona-mcp",
    env={
        "HYPERPERSONA_BASE_URL": "https://api.your-shop.example.com",
        "HYPERPERSONA_JWT": "<your jwt>",
    },
)

async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        result = await session.call_tool(
            "get_recommendation",
            {"context": "looking for trail running shoes", "limit": 5},
        )
        print(result)
```

## Tools exposed

| Tool | Use case |
|---|---|
| `ingest_event` | Record a customer event (page_view, purchase, return, ...) |
| `get_recommendation` | Generate a personalized, fact-checked offer + product list |
| `update_consent` | Update DPDP/GDPR scopes for the customer |
| `delete_customer_data` | Right-to-erasure wipe across all stores |
| `get_recommendation_trace` | Pull the chain-of-verification audit trail for a prior recommendation |

## Resources exposed

| URI | Content |
|---|---|
| `hyperpersona://customer/profile` | Consent scopes, retention setting, customer_id |
| `hyperpersona://system/info` | Platform version + capability summary |

## Prompts exposed

| Prompt | Use case |
|---|---|
| `explain_recommendation` | Walks the calling LLM through producing a customer-facing explanation of why a particular recommendation was made (cites facts, mentions cold-start / clarifying paths) |

## Architecture

```
┌───────────────────────────┐         ┌─────────────────────────────┐
│ MCP Client (Claude        │  stdio  │ hyperpersona-mcp            │
│ Desktop / Anthropic SDK   │◄───────►│ (this package)              │
│ / Bedrock Agent / ...)    │ JSON-RPC│   FastMCP over stdio        │
└───────────────────────────┘         │   5 tools + 2 resources     │
                                       │     + 1 prompt              │
                                       └──────────────┬──────────────┘
                                                      │ HTTPS + JWT
                                                      ▼
                                       ┌─────────────────────────────┐
                                       │ HyperPersona REST API       │
                                       │   FastAPI on AWS            │
                                       │   ↓                         │
                                       │ Strands agentic pipeline    │
                                       │   • Privacy gate (Comprehend)│
                                       │   • Analyzer (Sonnet 4.5)   │
                                       │   • Recommender (Opus 4.5)  │
                                       │   • Verifier (Opus 4.5)     │
                                       │   ↓                         │
                                       │ DDB + AOSS + SQS + S3 + Redis│
                                       └─────────────────────────────┘
```

## License

MIT — use it commercially, integrate freely, contribute upstream.
