"""Bedrock client wrapper.

Real-only — talks to AWS Bedrock for embeddings and Claude generations.
Use `make_bedrock_client(...)` to construct; the function exists so the
rest of the codebase doesn't import boto3 directly and so future provider
swaps stay confined here.
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol

from .retry import aws_retry

log = logging.getLogger(__name__)


class BedrockClientProtocol(Protocol):
    def embed(self, text: str) -> list[float]: ...
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
    def generate(self, prompt: str, system: str = "", max_tokens: int = 1024) -> str: ...


# --- Real client ---------------------------------------------------------

class BedrockClient:
    """Talks to AWS Bedrock. Requires valid AWS creds in the environment."""

    def __init__(self, region: str, text_model: str, embed_model: str):
        import boto3  # imported lazily so callers without boto3 don't fail at import time
        self.client = boto3.client("bedrock-runtime", region_name=region)
        self.text_model = text_model
        self.embed_model = embed_model

    @aws_retry()
    def embed(self, text: str) -> list[float]:
        response = self.client.invoke_model(
            modelId=self.embed_model,
            body=json.dumps({"inputText": text}),
        )
        return json.loads(response["body"].read())["embedding"]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Parallel-fire N embed calls. Titan's API only takes one text per
        call, so 'batch' here means concurrent invocations on a thread pool.
        Wall-clock time becomes ~max(call_latency) instead of sum, capped by
        Bedrock's per-account TPS limits.
        """
        if not texts:
            return []
        with ThreadPoolExecutor(max_workers=min(8, len(texts))) as pool:
            return list(pool.map(self.embed, texts))

    @aws_retry()
    def generate(self, prompt: str, system: str = "", max_tokens: int = 1024) -> str:
        body: dict = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }
        if system:
            body["system"] = system
        response = self.client.invoke_model(
            modelId=self.text_model,
            body=json.dumps(body),
        )
        result = json.loads(response["body"].read())
        return result["content"][0]["text"]


# --- Factory -------------------------------------------------------------

def make_bedrock_client(
    mode: str,
    region: str,
    text_model: str,
    embed_model: str,
) -> BedrockClientProtocol:
    """Build a Bedrock client. `mode` is kept on the signature for backward
    compatibility with existing call sites + the BEDROCK_MODE env var, but
    only `"real"` is supported now — anything else raises so a misconfig
    surfaces loudly instead of silently falling back to a stub.
    """
    if mode != "real":
        raise ValueError(
            f"BEDROCK_MODE={mode!r} is not supported — only 'real' remains. "
            "Set BEDROCK_MODE=real and provide valid AWS creds."
        )
    log.info("BedrockClient: real mode (region=%s, text=%s, embed=%s)",
             region, text_model, embed_model)
    return BedrockClient(region=region, text_model=text_model, embed_model=embed_model)
