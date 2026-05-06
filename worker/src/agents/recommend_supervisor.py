"""Recommend supervisor — orchestrates recommender → verifier.

Two implementations behind a Protocol, picked at startup by RECOMMEND_MODE:

  - ManualRecommendSupervisor  fixed two-step pipeline matching the
                               legacy generate_recommendation handler.
                               Works in BEDROCK_MODE=mock or real.

  - StrandsRecommendSupervisor wraps a strands.Agent with the two tools.
                               Same trace plumbing as StrandsSupervisor.
                               Requires BEDROCK_MODE=real.

Use make_recommend_supervisor(...) to build the right one.

Output contract: both implementations return the same dict shape so the
generate_recommendation handler can serialize one result format.
"""

from __future__ import annotations

import logging
import time
from typing import Protocol

from shared.bedrock import BedrockClientProtocol
from shared.vector_store import VectorStoreProtocol

from ..trace_logger import TraceLogger

log = logging.getLogger(__name__)


class RecommendSupervisorProtocol(Protocol):
    def run_recommend(self, job_id: str, customer_id: str, context: str) -> dict: ...


# --- Manual ---------------------------------------------------------------


class ManualRecommendSupervisor:
    """Flat recommender → verifier pipeline.

    Recommender and verifier each get their own Bedrock client because
    they're different tasks: recommender wants creative+grounded text,
    verifier wants accurate judgment. In production, both run on Opus 4.7;
    in dev they fall back to whatever bedrock_text_model is set.
    """

    def __init__(
        self,
        bedrock_recommender: BedrockClientProtocol,
        bedrock_verifier: BedrockClientProtocol,
        vectors: VectorStoreProtocol,
        tracer: TraceLogger,
    ) -> None:
        self.bedrock_recommender = bedrock_recommender
        self.bedrock_verifier = bedrock_verifier
        self.vectors = vectors
        self.tracer = tracer

    def run_recommend(self, job_id: str, customer_id: str, context: str) -> dict:
        from .tools import recommender_tool, verifier_tool

        self.tracer.log(
            job_id, "supervisor", "start_recommend",
            {"customer_id": customer_id, "context_len": len(context)},
            {"mode": "manual"}, 0.0, "ok",
        )

        # 1. Recommender draft (Opus for premium creative+grounded text)
        t0 = time.time()
        rec = recommender_tool.generate_recommendation(
            customer_id, context, self.bedrock_recommender, self.vectors,
        )
        self.tracer.log(
            job_id, "recommender", "generate_recommendation",
            {"customer_id": customer_id, "context_len": len(context),
             "model": getattr(self.bedrock_recommender, "text_model", "?").rsplit("/", 1)[-1]},
            rec, (time.time() - t0) * 1000, "ok",
        )

        # 2. Verifier (Opus for highest-accuracy judgment)
        t0 = time.time()
        source_summary = (
            f"context={context}; "
            f"facts_used={rec['facts_used']}; "
            f"behaviors_used={rec['behaviors_used']}; "
            f"summaries_used={rec.get('summaries_used', 0)}"
        )
        verified = verifier_tool.verify_recommendation(
            rec["offer"], source_summary, self.bedrock_verifier,
        )
        self.tracer.log(
            job_id, "verifier", "verify_recommendation",
            {"draft_len": len(rec.get("offer", "")),
             "model": getattr(self.bedrock_verifier, "text_model", "?").rsplit("/", 1)[-1]},
            verified, (time.time() - t0) * 1000, "ok",
        )

        result = _build_result(rec, verified)
        self.tracer.log(
            job_id, "supervisor", "end_recommend",
            {}, {"verifier_status": verified["status"]},
            0.0, "ok",
        )
        return result


# --- Strands --------------------------------------------------------------


_STRANDS_RECOMMEND_PROMPT = """You are HyperPersona's recommendation supervisor.

For each customer recommendation request, execute these steps IN ORDER:
  1. Call generate_recommendation_tool with the provided context to get a
     draft offer plus the source data it used.
  2. Call verify_recommendation_tool, passing the draft offer and a
     short source summary string from step 1.
  3. Return a one-line confirmation that you generated and verified the
     recommendation.

Do not skip the verifier. Do not call any tools beyond
generate_recommendation_tool and verify_recommendation_tool. Do not invent
facts."""


class StrandsRecommendSupervisor:
    """Strands-driven recommend pipeline.

    Three models in play, each picked for its task:
      - Orchestrator (BedrockModel for the Agent): Sonnet — the agent just
        routes between two tools; doesn't need Opus reasoning.
      - Recommender tool: Opus — creative + grounded offer text.
      - Verifier tool:    Opus — judgment accuracy.

    Requires BEDROCK_MODE=real.
    """

    def __init__(
        self,
        bedrock_recommender: BedrockClientProtocol,
        bedrock_verifier: BedrockClientProtocol,
        vectors: VectorStoreProtocol,
        tracer: TraceLogger,
        settings,
    ) -> None:
        self.bedrock_recommender = bedrock_recommender
        self.bedrock_verifier = bedrock_verifier
        self.vectors = vectors
        self.tracer = tracer
        self.settings = settings

        # Orchestrator picks tool order; Sonnet is plenty.
        from strands.models import BedrockModel
        orchestrator_model = settings.bedrock_orchestrator_model or settings.bedrock_text_model
        self._model = BedrockModel(
            region_name=settings.bedrock_region,
            model_id=orchestrator_model,
            max_tokens=2048,
        )

    def run_recommend(self, job_id: str, customer_id: str, context: str) -> dict:
        from strands import Agent, tool

        from .tools.recommender_tool import generate_recommendation
        from .tools.verifier_tool import verify_recommendation

        self.tracer.log(
            job_id, "supervisor", "start_recommend",
            {"customer_id": customer_id, "context_len": len(context)},
            {"mode": "strands"}, 0.0, "ok",
        )

        # Captures populated by the @tool closures during the agent run.
        # We can't rely on Claude returning structured data — we build the
        # response from these.
        capture: dict[str, dict | None] = {"recommender": None, "verifier": None}

        # Bind dependencies into closures so Claude only sees user-meaningful args.
        # Each tool gets the bedrock client matched to its task.
        bedrock_recommender = self.bedrock_recommender
        bedrock_verifier = self.bedrock_verifier
        vectors = self.vectors

        @tool
        def generate_recommendation_tool(query_context: str) -> dict:
            """Generate a personalized offer from the customer's stored facts and behavior.

            Args:
                query_context: the situation or intent
                    (e.g., "looking for outdoor gear")

            Returns:
                A dict with 'offer' (the draft text), 'facts_used',
                'behaviors_used', 'summaries_used', 'conflicts'.
            """
            result = generate_recommendation(customer_id, query_context, bedrock_recommender, vectors)
            capture["recommender"] = result
            return result

        @tool
        def verify_recommendation_tool(draft_offer: str, source_context: str) -> dict:
            """Fact-check a draft offer against the source data.

            Args:
                draft_offer: the recommendation text to verify
                source_context: short summary string of the source data
                    used to ground the recommendation

            Returns:
                A dict with 'status' ('valid'|'corrected') and 'final_offer'.
            """
            result = verify_recommendation(draft_offer, source_context, bedrock_verifier)
            capture["verifier"] = result
            return result

        agent = Agent(
            model=self._model,
            system_prompt=_STRANDS_RECOMMEND_PROMPT,
            tools=[generate_recommendation_tool, verify_recommendation_tool],
            hooks=[self.tracer.make_strands_hook(job_id)],
        )

        prompt = (
            f"Generate a personalized offer for this customer.\n"
            f"context: {context}\n"
        )

        start = time.time()
        try:
            agent(prompt)
        except Exception as e:
            duration = (time.time() - start) * 1000
            self.tracer.log(
                job_id, "supervisor", "end_recommend",
                {}, {"error": f"{type(e).__name__}: {e}"},
                duration, "error",
            )
            raise

        rec = capture["recommender"] or {}
        ver = capture["verifier"] or {}

        result = _build_result(rec, ver)

        self.tracer.log(
            job_id, "supervisor", "end_recommend",
            {}, {"verifier_status": ver.get("status", "missing")},
            (time.time() - start) * 1000, "ok",
        )
        return result


# --- Helpers --------------------------------------------------------------


def _build_result(rec: dict, ver: dict) -> dict:
    """Common result shape — both supervisor implementations return this."""
    return {
        "offer": (ver.get("final_offer")
                  if ver.get("final_offer") is not None
                  else rec.get("offer", "")),
        "verifier_status": ver.get("status", "missing"),
        "facts_retrieved": rec.get("facts_retrieved", 0),
        "facts_used": rec.get("facts_used", 0),
        "behaviors_used": rec.get("behaviors_used", 0),
        "summaries_used": rec.get("summaries_used", 0),
        "conflicts": rec.get("conflicts", []),
    }


# --- Factory --------------------------------------------------------------


def make_recommend_supervisor(
    mode: str,
    bedrock_recommender: BedrockClientProtocol,
    bedrock_verifier: BedrockClientProtocol,
    vectors: VectorStoreProtocol,
    tracer: TraceLogger,
    settings,
) -> RecommendSupervisorProtocol:
    if mode == "manual":
        log.info("RecommendSupervisor: manual (rec=%s ver=%s)",
                 getattr(bedrock_recommender, "text_model", "?").rsplit("/", 1)[-1],
                 getattr(bedrock_verifier, "text_model", "?").rsplit("/", 1)[-1])
        return ManualRecommendSupervisor(
            bedrock_recommender=bedrock_recommender,
            bedrock_verifier=bedrock_verifier,
            vectors=vectors, tracer=tracer,
        )
    if mode == "strands":
        if settings.bedrock_mode != "real":
            raise RuntimeError(
                "RECOMMEND_MODE=strands requires BEDROCK_MODE=real "
                f"(got {settings.bedrock_mode!r})."
            )
        orchestrator = settings.bedrock_orchestrator_model or settings.bedrock_text_model
        log.info("RecommendSupervisor: strands (orch=%s rec=%s ver=%s)",
                 orchestrator.rsplit("/", 1)[-1],
                 getattr(bedrock_recommender, "text_model", "?").rsplit("/", 1)[-1],
                 getattr(bedrock_verifier, "text_model", "?").rsplit("/", 1)[-1])
        return StrandsRecommendSupervisor(
            bedrock_recommender=bedrock_recommender,
            bedrock_verifier=bedrock_verifier,
            vectors=vectors, tracer=tracer, settings=settings,
        )
    raise ValueError(
        f"Unknown RECOMMEND_MODE: {mode!r} (expected manual | strands)"
    )
