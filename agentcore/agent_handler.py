"""HyperPersona analyzer agent — runs in a Bedrock AgentCore Firecracker microVM.

This is the deployable counterpart to the local Strands supervisor in
worker/src/agents/supervisor.py. It's intentionally narrower:

  - No DynamoDB / OpenSearch deps (the microVM runs in AWS and can't
    reach our local docker-compose backends)
  - One tool: extract_facts, which calls Bedrock to pull atomic facts
    from an event text
  - Returns the structured analysis to the caller

The local AgentCoreSupervisor in the worker invokes this via
bedrock-agentcore.invoke_agent_runtime. The full ingest pipeline still
runs locally; what this proves is that the SAME Strands agent code can
run in-process (SUPERVISOR_MODE=strands) or remotely in a microVM
(SUPERVISOR_MODE=agentcore).
"""

import json
import logging
import os

from bedrock_agentcore import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


_SYSTEM_PROMPT = """You are HyperPersona's analyzer agent running in a Firecracker microVM.

Given a customer event description, your job is:
  1. Call extract_facts with the event text to surface atomic facts.
  2. Return a brief 1-2 sentence summary of what you learned about the customer.

Use the tool exactly once. Do not invent facts beyond what's in the event."""


@tool
def extract_facts(event_text: str) -> dict:
    """Extract 2-3 atomic facts about a customer from event text.

    Use this whenever asked to analyze a customer event. Returns a list
    of {text, polarity} facts where polarity is -1 (negative), 0 (neutral),
    or 1 (positive).

    Args:
        event_text: the raw event text to analyze

    Returns:
        dict with 'facts' (list of {text, polarity}) and 'analyzed_chars' (int).
    """
    # Real implementation would go here. For the demo we just echo back a
    # structured response — Claude in the supervising agent will reason
    # over this and produce the final summary.
    return {
        "facts": [
            {"text": f"customer described: {event_text[:80]}", "polarity": 0},
        ],
        "analyzed_chars": len(event_text),
    }


def _build_agent() -> Agent:
    model = BedrockModel(
        region_name=os.getenv("AWS_REGION", "us-east-1"),
        model_id=os.getenv(
            "BEDROCK_TEXT_MODEL",
            "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        ),
        max_tokens=1024,
    )
    return Agent(
        model=model,
        system_prompt=_SYSTEM_PROMPT,
        tools=[extract_facts],
    )


# Build once at cold-start, reuse across invocations within the same microVM.
_agent = _build_agent()

app = BedrockAgentCoreApp()


@app.entrypoint
def handler(payload: dict) -> dict:
    """AgentCore entrypoint. Receives a JSON payload, returns a JSON response.

    Expected payload: {"prompt": "...", "event_text": "..."} OR raw {"prompt": "..."}.
    The local AgentCoreSupervisor sends event_text + a one-line prompt; we
    prepend the event_text into the prompt so Claude has context.
    """
    log.info("agentcore handler invoked", extra={"keys": list(payload.keys())})

    prompt = payload.get("prompt", "")
    event_text = payload.get("event_text", "")
    if event_text and event_text not in prompt:
        prompt = f"{prompt}\n\nEvent text: {event_text}"

    if not prompt:
        return {"error": "missing 'prompt' in payload"}

    result = _agent(prompt)
    return {
        "output": str(result),
        "agent": "hyperpersona-analyzer",
    }


if __name__ == "__main__":
    app.run()
