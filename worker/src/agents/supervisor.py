"""Supervisor — orchestrates the privacy → analyzer pipeline for one event.

Two implementations behind a Protocol, picked at startup by SUPERVISOR_MODE:

  - ManualSupervisor  fixed-order orchestrator. Calls privacy_tool then
                      analyzer_tool. Works in BEDROCK_MODE=mock or real.
                      The default — used in tests and demos.

  - StrandsSupervisor wraps a strands.Agent that gets a system prompt and
                      the @tool versions of privacy + analyzer. Claude
                      picks the order. Requires BEDROCK_MODE=real because
                      Strands talks to Bedrock through boto3 directly,
                      bypassing MockBedrockClient.

  - AgentCoreSupervisor (Phase 10) — invokes a remote agent runtime in a
                      Firecracker microVM. Stub raises NotImplementedError
                      until 10a/10b ship.

Use make_supervisor(...) to build the right one.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable, Protocol

from shared.bedrock import BedrockClientProtocol
from shared.dynamo import DynamoClient
from shared.pii import PiiRedactor
from shared.vector_store import VectorStoreProtocol

from ..trace_logger import TraceLogger
from .tools import analyzer_tool, privacy_tool

log = logging.getLogger(__name__)


class SupervisorProtocol(Protocol):
    def run_process_event(self, job_id: str, event: dict) -> dict: ...


# --- Manual ---------------------------------------------------------------


class ManualSupervisor:
    """Hand-rolled orchestrator: privacy → (if blocked, stop) → analyzer.

    This is the only path that works in BEDROCK_MODE=mock since the mock
    Bedrock client is not wired into Strands' BedrockModel.
    """

    def __init__(
        self,
        dynamo: DynamoClient,
        bedrock: BedrockClientProtocol,
        vectors: VectorStoreProtocol,
        tracer: TraceLogger,
        redactor: PiiRedactor | None = None,
    ) -> None:
        self.dynamo = dynamo
        self.bedrock = bedrock
        self.vectors = vectors
        self.tracer = tracer
        self.redactor = redactor

    def run_process_event(self, job_id: str, event: dict) -> dict:
        customer_id = event["customer_id"]
        event_id = event["event_id"]
        event_text = self._serialize_event(event)

        self.tracer.log(
            job_id, "supervisor", "start",
            {"customer_id": customer_id, "event_id": event_id},
            {"event_text_len": len(event_text), "mode": "manual"},
            0.0, "ok",
        )

        privacy = self._step(
            job_id, "privacy", "check_privacy",
            {"customer_id": customer_id, "text_len": len(event_text)},
            lambda: privacy_tool.check_privacy(
                customer_id, event_text, self.dynamo, redactor=self.redactor,
            ),
        )

        if not privacy.get("allowed"):
            self.tracer.log(
                job_id, "supervisor", "blocked",
                {}, {"reason": privacy.get("reason")},
                0.0, "ok",
            )
            return {"status": "blocked", "reason": privacy.get("reason")}

        analysis = self._step(
            job_id, "analyzer", "analyze_behavior",
            {"customer_id": customer_id, "event_id": event_id,
             "redacted_text_len": len(privacy["redacted_text"])},
            lambda: analyzer_tool.analyze_behavior(
                customer_id,
                privacy["redacted_text"],
                event_id,
                self.bedrock,
                self.vectors,
            ),
        )

        self.tracer.log(
            job_id, "supervisor", "end",
            {}, {"status": "ok", **analysis},
            0.0, "ok",
        )
        return {"status": "ok", **analysis}

    def _step(
        self,
        job_id: str,
        agent_name: str,
        step: str,
        input_data: Any,
        fn: Callable[[], Any],
    ) -> Any:
        start = time.time()
        try:
            output = fn()
            duration = (time.time() - start) * 1000
            self.tracer.log(job_id, agent_name, step, input_data, output, duration, "ok")
            return output
        except Exception as e:
            duration = (time.time() - start) * 1000
            self.tracer.log(
                job_id, agent_name, step, input_data,
                {"error": f"{type(e).__name__}: {e}"},
                duration, "error",
            )
            raise

    @staticmethod
    def _serialize_event(event: dict) -> str:
        parts = [f"event_type: {event.get('event_type', 'unknown')}"]
        for k, v in (event.get("payload") or {}).items():
            parts.append(f"{k}: {v}")
        return "; ".join(parts)


# Backward-compat alias — older imports use `Supervisor`.
Supervisor = ManualSupervisor


# --- Strands --------------------------------------------------------------


_STRANDS_SYSTEM_PROMPT = """You are HyperPersona's personalization supervisor.

You receive a customer event and must route it to the right analysis path.

STEP 1 — ALWAYS call check_privacy_tool(customer_id=<id>, text=<event_text>) first.
  If allowed=False, STOP. Return the reason verbatim. Do NOT call any other tools.

STEP 2 — If allowed=True, look at the event_type and pick EXACTLY ONE analysis tool:

  ┌──────────────────────────────────────────┬──────────────────────────────────┐
  │ event_type                                │ tool to call                     │
  ├──────────────────────────────────────────┼──────────────────────────────────┤
  │ page_view, scroll, hover, search_no_click│ skip_low_signal_tool             │
  │   (low-signal — embed only, no facts)     │                                  │
  ├──────────────────────────────────────────┼──────────────────────────────────┤
  │ return, complaint, refund, support_ticket│ extract_dispute_reasons_tool     │
  │   (dispute — extract negative signals)    │                                  │
  ├──────────────────────────────────────────┼──────────────────────────────────┤
  │ purchase, add_to_cart, save, search,      │ analyze_behavior_tool            │
  │ checkout, wishlist_add                    │                                  │
  │   (high-signal — full fact extraction)    │                                  │
  └──────────────────────────────────────────┴──────────────────────────────────┘

For ANY analysis tool you choose, pass EXACTLY:
  - customer_id = the same customer_id
  - event_text  = the 'redacted_text' field from step 1 (NEVER the raw text)
  - event_id    = the event_id provided in the prompt

STEP 3 — Return a one-line summary:
  "stored N facts (tool=<tool>) for customer <id>" — or the privacy reason if blocked.

Strict rules:
  - Privacy ALWAYS runs first. No exceptions.
  - Pick ONE analysis tool — do NOT call multiple analyzers.
  - Use redacted_text from privacy, never raw event_text. PII must stay redacted.
  - If event_type doesn't match any row above, default to analyze_behavior_tool."""


class StrandsSupervisor:
    """Strands-driven orchestrator. Claude decides the tool order subject to
    the system prompt. Requires BEDROCK_MODE=real."""

    def __init__(
        self,
        dynamo: DynamoClient,
        bedrock: BedrockClientProtocol,
        vectors: VectorStoreProtocol,
        tracer: TraceLogger,
        settings,
        redactor: PiiRedactor | None = None,
    ) -> None:
        self.dynamo = dynamo
        self.bedrock = bedrock
        self.vectors = vectors
        self.tracer = tracer
        self.settings = settings
        self.redactor = redactor

        # Build the BedrockModel once and reuse across invocations.
        # Orchestrator routes between privacy + analyzer tools — Sonnet is
        # the right fit (cheaper, faster than Opus). Falls back to
        # bedrock_text_model if orchestrator_model is unset.
        from strands.models import BedrockModel
        orchestrator_model = settings.bedrock_orchestrator_model or settings.bedrock_text_model
        self._model = BedrockModel(
            region_name=settings.bedrock_region,
            model_id=orchestrator_model,
            max_tokens=2048,
        )

    def run_process_event(self, job_id: str, event: dict) -> dict:
        from strands import Agent

        from .tools.analyzer_tool import make_analyzer_tool
        from .tools.dispute_tool import make_extract_dispute_reasons_tool
        from .tools.privacy_tool import make_privacy_tool
        from .tools.skip_low_signal_tool import make_skip_low_signal_tool

        customer_id = event["customer_id"]
        event_id = event["event_id"]
        event_text = ManualSupervisor._serialize_event(event)

        self.tracer.log(
            job_id, "supervisor", "start",
            {"customer_id": customer_id, "event_id": event_id,
             "event_type": event.get("event_type", "unknown")},
            {"event_text_len": len(event_text), "mode": "strands"},
            0.0, "ok",
        )

        # Four tools: privacy (always first) + three branching analysis tools
        # the orchestrator picks between based on event_type.
        agent = Agent(
            model=self._model,
            system_prompt=_STRANDS_SYSTEM_PROMPT,
            tools=[
                make_privacy_tool(self.dynamo, redactor=self.redactor),
                make_analyzer_tool(self.bedrock, self.vectors),
                make_skip_low_signal_tool(self.bedrock, self.vectors),
                make_extract_dispute_reasons_tool(self.bedrock, self.vectors),
            ],
            hooks=[self.tracer.make_strands_hook(job_id)],
        )

        prompt = (
            f"Process this customer event.\n"
            f"customer_id: {customer_id}\n"
            f"event_id: {event_id}\n"
            f"event_type: {event.get('event_type', 'unknown')}\n"
            f"payload: {json.dumps(event.get('payload') or {}, default=str)}\n"
            f"event_text: {event_text}\n"
        )

        start = time.time()
        try:
            result = agent(prompt)
            duration = (time.time() - start) * 1000
            self.tracer.log(
                job_id, "supervisor", "end",
                {}, {"status": "ok", "result": str(result)[:500]},
                duration, "ok",
            )
            return {"status": "ok", "result": str(result)}
        except Exception as e:
            duration = (time.time() - start) * 1000
            self.tracer.log(
                job_id, "supervisor", "end",
                {}, {"error": f"{type(e).__name__}: {e}"},
                duration, "error",
            )
            raise


# --- AgentCore (Phase 10 — stub) ----------------------------------------


class AgentCoreSupervisor:
    """Invokes a Strands agent deployed to Bedrock AgentCore Runtime.

    The deployed agent (in [agentcore/agent_handler.py](agentcore/agent_handler.py))
    is a slimmed-down analyzer — it has no DynamoDB or OpenSearch deps, since
    those backends live inside our local docker-compose and can't be reached
    from the AWS microVM. So this supervisor doesn't run the full
    privacy → analyzer pipeline; it sends the event text to the remote
    agent and writes the response into the trace.

    Demonstrates that the SAME Strands agent code (privacy + analyzer
    factories) can run in-process (SUPERVISOR_MODE=strands) or in a
    Firecracker microVM (SUPERVISOR_MODE=agentcore). To make agentcore
    functionally equivalent to strands, the AWS-managed-data-stores
    migration (DynamoDB + OpenSearch Serverless) is required.

    Requires AGENTCORE_AGENT_ARN to be set in env.
    """

    def __init__(self, settings, tracer: TraceLogger) -> None:
        self.settings = settings
        self.tracer = tracer
        if not getattr(settings, "agentcore_agent_arn", ""):
            raise RuntimeError(
                "SUPERVISOR_MODE=agentcore requires AGENTCORE_AGENT_ARN to be set. "
                "Run `agentcore deploy` from agentcore/ to get one."
            )
        # Lazily build the client so import-time isn't fatal when the env
        # has the wrong shape; we'll surface a clear error on first call.
        import boto3
        self._client = boto3.client(
            "bedrock-agentcore", region_name=settings.aws_region,
        )
        self._agent_arn = settings.agentcore_agent_arn

    def run_process_event(self, job_id: str, event: dict) -> dict:
        import json as _json
        import time as _time
        import uuid as _uuid

        customer_id = event["customer_id"]
        event_id = event["event_id"]
        event_text = ManualSupervisor._serialize_event(event)

        self.tracer.log(
            job_id, "supervisor", "start",
            {"customer_id": customer_id, "event_id": event_id},
            {"event_text_len": len(event_text), "mode": "agentcore",
             "agent_arn": self._agent_arn[-40:]},
            0.0, "ok",
        )

        # AgentCore requires session IDs to be 33+ chars. UUIDs are 36.
        # Tying the session to the job_id would cap us at 36 (job_ids are
        # also UUIDs); just use a fresh UUID per invocation.
        session_id = str(_uuid.uuid4())
        payload = _json.dumps({
            "prompt": "Analyze this customer event and extract atomic facts.",
            "event_text": event_text,
            "customer_id": customer_id,
            "event_id": event_id,
        }).encode("utf-8")

        start = _time.time()
        try:
            response = self._client.invoke_agent_runtime(
                agentRuntimeArn=self._agent_arn,
                runtimeSessionId=session_id,
                payload=payload,
            )
        except Exception as e:
            duration = (_time.time() - start) * 1000
            self.tracer.log(
                job_id, "agentcore", "invoke_agent_runtime",
                {"event_id": event_id},
                {"error": f"{type(e).__name__}: {e}"},
                duration, "error",
            )
            raise

        # Response body is a streaming bytes object — drain it.
        body_bytes = response["response"].read() if hasattr(response.get("response"), "read") else b""
        try:
            body = _json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except (UnicodeDecodeError, _json.JSONDecodeError):
            body = {"raw": body_bytes[:200].decode("utf-8", errors="replace")}

        duration = (_time.time() - start) * 1000
        self.tracer.log(
            job_id, "agentcore", "invoke_agent_runtime",
            {"event_id": event_id, "session_id": session_id, "payload_len": len(payload)},
            {"output_preview": str(body.get("output", body))[:300]},
            duration, "ok",
        )

        self.tracer.log(
            job_id, "supervisor", "end",
            {}, {"status": "ok", "result": str(body.get("output", body))[:300]},
            0.0, "ok",
        )
        return {"status": "ok", "result": body.get("output", str(body))}


# --- Factory --------------------------------------------------------------


def make_supervisor(
    mode: str,
    dynamo: DynamoClient,
    bedrock: BedrockClientProtocol,
    vectors: VectorStoreProtocol,
    tracer: TraceLogger,
    settings,
    redactor: PiiRedactor | None = None,
) -> SupervisorProtocol:
    """Build the supervisor implementation for the current SUPERVISOR_MODE.

    `strands` requires BEDROCK_MODE=real; we raise early if not, so the
    worker fails loudly at startup instead of mid-job.
    """
    if mode == "manual":
        log.info("Supervisor: manual (bedrock=%s)", settings.bedrock_mode)
        return ManualSupervisor(
            dynamo=dynamo, bedrock=bedrock, vectors=vectors,
            tracer=tracer, redactor=redactor,
        )
    if mode == "strands":
        if settings.bedrock_mode != "real":
            raise RuntimeError(
                "SUPERVISOR_MODE=strands requires BEDROCK_MODE=real "
                f"(got {settings.bedrock_mode!r}). Strands talks to Bedrock "
                "via boto3 directly and cannot use MockBedrockClient."
            )
        orchestrator = settings.bedrock_orchestrator_model or settings.bedrock_text_model
        log.info("Supervisor: strands (orchestrator=%s analyzer=%s region=%s)",
                 orchestrator.rsplit("/", 1)[-1],
                 getattr(bedrock, "text_model", "?").rsplit("/", 1)[-1],
                 settings.bedrock_region)
        return StrandsSupervisor(
            dynamo=dynamo, bedrock=bedrock, vectors=vectors,
            tracer=tracer, settings=settings, redactor=redactor,
        )
    if mode == "agentcore":
        log.info("Supervisor: agentcore (stub — Phase 10 not yet shipped)")
        return AgentCoreSupervisor(settings=settings, tracer=tracer)
    raise ValueError(
        f"Unknown SUPERVISOR_MODE: {mode!r} (expected manual | strands | agentcore)"
    )
