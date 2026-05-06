"""HyperPersona MCP server.

Exposes HyperPersona's agentic personalization platform via the
Model Context Protocol so any MCP-aware LLM client (Claude Desktop,
Anthropic SDK, AWS Bedrock agents) can ingest events, fetch verified
recommendations, manage consent, and pull audit trails as first-class
tools and resources.

Run as a subprocess via the `hyperpersona-mcp` console script (see
pyproject.toml).
"""

__version__ = "0.1.0"
