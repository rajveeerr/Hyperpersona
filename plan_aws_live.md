# HyperPersona — AWS Live Plan (dynamic-mode)

Picks up from [plan.md](plan.md) and supersedes [plan_remaining.md](plan_remaining.md). AWS creds are now available, so phases 9, 10, 13–16 unblock. This document re-orders the work, deepens the Strands integration, and makes every external dependency a runtime-flippable toggle so mock and real can coexist in the same image.

---

## 0. Design principle — **dynamic modes, not branches**

Every external dependency is fronted by a `Protocol` and a `make_*()` factory that reads an env var. Flipping mock → real is `docker compose up -d` after editing `.env`. No code change, no image rebuild for either side.

### Mode toggles (target end state)

| Env var | Values | Today | Controls |
|---|---|---|---|
| `BEDROCK_MODE` | `mock` \| `real` | mock | [shared/bedrock.py:114](shared/bedrock.py#L114) factory |
| `VECTOR_MODE` | `memory` \| `opensearch` \| `aoss` | opensearch | [shared/vector_store.py:86](shared/vector_store.py#L86) factory |
| `PII_MODE` ✱ | `regex` \| `comprehend` | regex (only mode) | new — [shared/pii.py](shared/pii.py) factory |
| `SUPERVISOR_MODE` ✱ | `manual` \| `strands` \| `agentcore` | manual (only mode) | new — [worker/src/agents/supervisor.py](worker/src/agents/supervisor.py) factory |
| `TRACE_SYNC_MODE` ✱ | `local` \| `s3` | local (only mode) | new — [worker/src/trace_logger.py](worker/src/trace_logger.py) post-job hook |
| `EVENT_PROCESSING_MODE` | `full` \| `tiered` | full | already wired [worker/src/handlers/process_event.py:46](worker/src/handlers/process_event.py#L46) |

✱ = added in this plan. Each new toggle ships with both implementations behind one `Protocol`, identical to how `BedrockClient`/`MockBedrockClient` work today.

### Why this matters

- **Demoability** — flip back to mock if Bedrock has an outage on demo day
- **Cost control** — local CI runs in mock; real only for staging/prod
- **Tests** — every test today runs in mock without AWS calls; we don't lose that
- **Reversibility** — if Strands behaves badly, set `SUPERVISOR_MODE=manual` to restore the current orchestrator

---

## 1. Phase order

| # | Name | Depends on | Duration | Mapping |
|---|---|---|---|---|
| **13** | AWS account, IAM, Bedrock model access | nothing | 30 min | new (prereq for plan.md Phase 4 going real) |
| **14a** | Real Bedrock validation | 13 | 30 min | plan.md Phase 4 (refresh) |
| **14b** | Strands `@tool` wrapping + `SUPERVISOR_MODE` factory | 14a | 2h | plan.md Phases 5+6 |
| **14c** | Trace-logging callback hook for Strands | 14b | 1h | plan.md Phase 6 |
| **15** | Comprehend swap behind `PII_MODE` factory | 13 | 30 min | plan.md Phase 11 |
| **9** | S3 trace sync behind `TRACE_SYNC_MODE` factory | 13 | 2h | plan.md Phase 9 |
| **10a** | AgentCore handler + Dockerfile | 14b, 9 | 2h | plan.md Phase 10 |
| **10b** | `agentcore` branch in `SUPERVISOR_MODE` | 10a | 1h | plan.md Phase 10 |
| **16** | Tenacity retries on Bedrock + sliding-window rate limit | 14a | 1h | plan.md Phase 12 |

**Total: ~10.5h**, can interleave 16 with anything after 14a.

---

## 2. Phase 13 — AWS bootstrap (30 min)

Same as [plan_remaining.md Phase 13](plan_remaining.md). Quick checklist:

1. **IAM user** with these managed policies:
   - `AmazonBedrockFullAccess`
   - `ComprehendFullAccess`
   - `AmazonS3FullAccess`
   - `AWSLambda_FullAccess` + `AmazonBedrockAgentCoreFullAccess` (for Phase 10)
2. **Request Bedrock model access** in console: Anthropic Claude Sonnet 4.5 + Amazon Titan Embed v2 (1–5 min auto-approve).
3. **Update `.env`** — replace the current Gemini stub with:
   ```env
   AWS_ACCESS_KEY_ID=AKIA...
   AWS_SECRET_ACCESS_KEY=...
   AWS_REGION=us-east-1

   BEDROCK_MODE=real
   BEDROCK_REGION=us-east-1
   BEDROCK_TEXT_MODEL=us.anthropic.claude-sonnet-4-5-20250929-v1:0
   BEDROCK_EMBED_MODEL=amazon.titan-embed-text-v2:0
   ```
   The `us.` prefix on the Anthropic model ID is the cross-region inference profile — without it, `AccessDeniedException`.

**Test gate:** `make down && make up && make test-bedrock` — see real Titan vector + non-stub Claude response.

⚠️ Current `.env` has a Gemini key that **must be removed** before any commit (it's plain-text in [.env:5](.env#L5)).

---

## 3. Phase 14 — Bedrock + Strands

The supervisor today is a manual orchestrator at [worker/src/agents/supervisor.py:41-88](worker/src/agents/supervisor.py#L41-L88) that calls tools in a fixed order: `privacy → analyzer`. Strands lets Claude pick the order from a system prompt, makes tool-use observable, and is the prerequisite for AgentCore (Phase 10).

### 14a. Real-Bedrock validation (30 min)

No code changes — just verify the `BEDROCK_MODE=real` path returns sensible outputs at every call site:

```bash
make test-bedrock     # shared/bedrock.py round-trip
make seed-consent && make test-tools
                      # privacy_tool + analyzer_tool with real Claude
make test-e2e         # full pipeline incl. recommender + verifier
```

Watch for:
- Analyzer's `_parse_facts` ([analyzer_tool.py:30](worker/src/agents/tools/analyzer_tool.py#L30)) — real Claude returns valid JSON, the mock fallback at line 41 should not fire
- Verifier — real Claude actually replies "VALID" for accurate drafts ([verifier_tool.py:34](worker/src/agents/tools/verifier_tool.py#L34))
- Complement — `_looks_like_mock` check ([complement_tool.py:98](worker/src/agents/tools/complement_tool.py#L98)) skipped, real LLM ranking used
- ACE thresholds — real Titan vectors cluster at ~0.5 similarity for related text; the 0.12 threshold in [ace_ranking.py:45](shared/ace_ranking.py#L45) starts surfacing facts now (in mock mode it filtered most retrievals)

If verifier or analyzer return malformed output more than ~10% of the time, tune the system prompts before moving on.

### 14b. Strands `@tool` wrapping + `SUPERVISOR_MODE` factory (2h)

#### Step 1 — install Strands

[worker/requirements.txt](worker/requirements.txt) already has `strands-agents>=0.1`. Confirm the Dockerfile picks it up at build time. Verify the API surface:

```python
from strands import Agent, tool
from strands.models import BedrockModel
```

If the version on PyPI has shifted, pin a known-good version. Strands docs: <https://strandsagents.com>.

#### Step 2 — refactor each tool to a factory + `@tool`

The tools today are plain functions that take dependencies as positional args (e.g. `check_privacy(customer_id, text, dynamo)`). Strands `@tool` reads function signature to build the JSON schema Claude sees — so dependencies must be **closed over**, not in the signature.

Apply this pattern to all four tool files:

```python
# worker/src/agents/tools/privacy_tool.py
from strands import tool
from shared.pii import make_pii_redactor   # see Phase 15

def make_privacy_tool(dynamo, redactor):
    @tool
    def check_privacy(customer_id: str, text: str) -> dict:
        """Check the customer's consent record. If they have granted the
        'personalization' scope, redact PII from the text and return it.
        If consent is missing, return allowed=False with a reason.

        Args:
            customer_id: the customer making the request
            text: the raw event text to redact

        Returns:
            A dict with allowed, redacted_text, pii_found.
        """
        consent = dynamo.get_consent(customer_id)
        if not consent:
            return {"allowed": False, "reason": "no_consent_record"}
        if "personalization" not in (consent.get("scopes") or set()):
            return {"allowed": False, "reason": "scope_missing:personalization"}
        redacted, entities = redactor.redact(text)
        return {"allowed": True, "redacted_text": redacted, "pii_found": len(entities)}
    return check_privacy
```

Apply identically to:

| Tool | Factory signature |
|---|---|
| `make_privacy_tool(dynamo, redactor)` | [privacy_tool.py](worker/src/agents/tools/privacy_tool.py) |
| `make_analyzer_tool(bedrock, vectors)` | [analyzer_tool.py](worker/src/agents/tools/analyzer_tool.py) |
| `make_recommender_tool(bedrock, vectors)` | [recommender_tool.py](worker/src/agents/tools/recommender_tool.py) |
| `make_verifier_tool(bedrock)` | [verifier_tool.py](worker/src/agents/tools/verifier_tool.py) |

**Critical:** keep the **plain function** alongside the `@tool` factory. The manual supervisor (and the mock-mode path) needs to call them directly. Don't break that:

```python
# privacy_tool.py keeps both:
def check_privacy(customer_id, text, dynamo, redactor=None):  # for manual mode
    ...

def make_privacy_tool(dynamo, redactor):                       # for Strands mode
    @tool
    def check_privacy_tool(customer_id: str, text: str) -> dict:
        return check_privacy(customer_id, text, dynamo, redactor)
    return check_privacy_tool
```

The mock-mode `MockBedrockClient` does **not** drive Strands — Strands wraps Bedrock through boto3 directly via `BedrockModel`. So the manual path must remain for `BEDROCK_MODE=mock`.

#### Step 3 — refactor `Supervisor`

Replace [worker/src/agents/supervisor.py](worker/src/agents/supervisor.py) with a dispatcher that branches on `SUPERVISOR_MODE`:

```python
import json, logging, time
from typing import Protocol

class SupervisorProtocol(Protocol):
    def run_process_event(self, job_id: str, event: dict) -> dict: ...

# --- Manual implementation (current behavior) ---------------------------
class ManualSupervisor:
    def __init__(self, dynamo, bedrock, vectors, tracer, redactor):
        # ... current __init__ ...
    def run_process_event(self, job_id, event):
        # ... current body, unchanged ...

# --- Strands implementation -------------------------------------------
class StrandsSupervisor:
    SYSTEM_PROMPT = """You are HyperPersona's personalization supervisor.

For each customer event you receive, execute these steps IN ORDER:
  1. Call check_privacy with the customer_id and event text.
  2. If allowed=False, stop and return the privacy reason.
  3. If allowed=True, call analyze_behavior with the redacted_text and
     event_id to extract and store facts.
  4. Return a one-line summary of what you stored.

Use tools only. Do not invent facts. Do not call tools beyond this list."""

    def __init__(self, dynamo, bedrock, vectors, tracer, redactor, settings):
        from strands import Agent
        from strands.models import BedrockModel
        from .tools.privacy_tool import make_privacy_tool
        from .tools.analyzer_tool import make_analyzer_tool
        # ... etc

        model = BedrockModel(
            model_id=settings.bedrock_text_model,
            region_name=settings.bedrock_region,
            max_tokens=2048,
        )
        self.agent = Agent(
            model=model,
            system_prompt=self.SYSTEM_PROMPT,
            tools=[
                make_privacy_tool(dynamo, redactor),
                make_analyzer_tool(bedrock, vectors),
            ],
            callback_handler=tracer.strands_callback,   # see 14c
        )
        self.tracer = tracer

    def run_process_event(self, job_id, event):
        prompt = (
            f"Process this customer event.\n"
            f"customer_id: {event['customer_id']}\n"
            f"event_id: {event['event_id']}\n"
            f"event_type: {event.get('event_type')}\n"
            f"payload: {json.dumps(event.get('payload') or {})}\n"
        )
        # The tracer.strands_callback writes per-step rows during this call
        result = self.agent(prompt)
        return {"status": "ok", "result": str(result)}

# --- Factory ----------------------------------------------------------
def make_supervisor(mode, dynamo, bedrock, vectors, tracer, redactor, settings):
    if mode == "manual":
        return ManualSupervisor(dynamo, bedrock, vectors, tracer, redactor)
    if mode == "strands":
        return StrandsSupervisor(dynamo, bedrock, vectors, tracer, redactor, settings)
    if mode == "agentcore":
        from .agentcore_supervisor import AgentCoreSupervisor   # Phase 10b
        return AgentCoreSupervisor(settings, tracer)
    raise ValueError(f"Unknown SUPERVISOR_MODE: {mode!r}")
```

Then [worker/src/main.py](worker/src/main.py) becomes:

```python
from .agents.supervisor import make_supervisor
from shared.pii import make_pii_redactor

redactor = make_pii_redactor(settings.pii_mode, region=settings.aws_region)
supervisor = make_supervisor(
    mode=settings.supervisor_mode,
    dynamo=dynamo, bedrock=bedrock, vectors=vectors,
    tracer=tracer, redactor=redactor, settings=settings,
)
```

#### Step 4 — config + compose plumbing

[worker/src/config.py](worker/src/config.py) adds:

```python
supervisor_mode: str = "manual"   # manual | strands | agentcore
pii_mode: str = "regex"           # regex | comprehend
trace_sync_mode: str = "local"    # local | s3
s3_traces_bucket: str = "hyperpersona-traces"
agentcore_agent_arn: str = ""
```

[docker-compose.yml](docker-compose.yml) worker block adds env passthroughs:

```yaml
SUPERVISOR_MODE: ${SUPERVISOR_MODE:-manual}
PII_MODE: ${PII_MODE:-regex}
TRACE_SYNC_MODE: ${TRACE_SYNC_MODE:-local}
S3_TRACES_BUCKET: ${S3_TRACES_BUCKET:-hyperpersona-traces}
AGENTCORE_AGENT_ARN: ${AGENTCORE_AGENT_ARN:-}
```

[.env.example](.env.example) gains all the same lines, defaulted to safe values.

**Test gate:**

```bash
# 1. Manual mode (mock OR real bedrock) still works
SUPERVISOR_MODE=manual make test-e2e

# 2. Strands mode with real Bedrock
SUPERVISOR_MODE=strands BEDROCK_MODE=real make down && make up
make test-e2e
make show-trace JOB=<id>
# trace should show: tool_use(check_privacy) → tool_result → tool_use(analyze_behavior) → ...
# instead of the supervisor's hardcoded order
```

### 14c. Trace-logging callback hook (1h)

Strands has a [callback handler](https://strandsagents.com/) that fires on every model call, tool call, and tool result. Hook it into `TraceLogger` so traces in Strands mode read the same shape as manual-mode traces.

Add to [worker/src/trace_logger.py](worker/src/trace_logger.py):

```python
def strands_callback(self, **event):
    """Strands callback signature is keyword-event-shaped. Each event has a
    'type' key plus type-specific fields. Map them onto our trace schema."""
    etype = event.get("type")
    job_id = self._current_job_id  # set by Supervisor before agent invocation
    if etype == "tool_use":
        self.log(job_id, event["tool_name"], "tool_use",
                 event.get("input"), {}, 0.0, "ok")
    elif etype == "tool_result":
        self.log(job_id, event["tool_name"], "tool_result",
                 {}, event.get("output"), event.get("duration_ms", 0.0), "ok")
    elif etype == "model_call":
        self.log(job_id, "model", "generate",
                 {"prompt_tokens": event.get("input_tokens")},
                 {"completion_tokens": event.get("output_tokens")},
                 event.get("duration_ms", 0.0), "ok")
```

`StrandsSupervisor.run_process_event` sets `tracer._current_job_id = job_id` before calling `self.agent(prompt)`. Not the prettiest API but matches the per-job context [trace_logger.py:46-53](worker/src/trace_logger.py#L46-L53) already assumes.

`make show-trace JOB=<id>` then reads exactly the same SQLite rows for both modes, and the merge across worker SQLite files in [shared/trace_reader.py](shared/trace_reader.py) is unchanged.

---

## 4. Phase 15 — AWS Comprehend behind `PII_MODE` (30 min)

Today PII detection is regex-only at [shared/pii.py:9-14](shared/pii.py#L9-L14) — only emails, phones, and naive name-pairs. Comprehend's `detect_pii_entities` covers SSN, credit card, address, IP, MAC, age, license number, etc.

### Implementation

[shared/pii.py](shared/pii.py) gets a Protocol + factory:

```python
from typing import Protocol

class PiiRedactor(Protocol):
    def redact(self, text: str) -> tuple[str, list[dict]]: ...

class RegexRedactor:
    def redact(self, text):
        return redact(text)   # existing module-level function

class ComprehendRedactor:
    def __init__(self, region: str):
        import boto3
        self.client = boto3.client("comprehend", region_name=region)

    def redact(self, text):
        if not text:
            return text, []
        resp = self.client.detect_pii_entities(Text=text, LanguageCode="en")
        entities = resp.get("Entities", [])
        # Replace right-to-left to preserve indices
        result = text
        for ent in sorted(entities, key=lambda e: -e["BeginOffset"]):
            result = result[:ent["BeginOffset"]] + "[REDACTED]" + result[ent["EndOffset"]:]
        return result, [
            {"type": e["Type"], "match": text[e["BeginOffset"]:e["EndOffset"]]}
            for e in entities
        ]

def make_pii_redactor(mode: str, region: str = "us-east-1") -> PiiRedactor:
    if mode == "comprehend":
        return ComprehendRedactor(region)
    return RegexRedactor()
```

Plumbing changes:
- [worker/src/main.py](worker/src/main.py) — call `make_pii_redactor(settings.pii_mode, region=settings.aws_region)`, pass to supervisor factory
- [worker/src/agents/tools/privacy_tool.py](worker/src/agents/tools/privacy_tool.py) — replace `from shared.pii import redact` with calls to the injected `redactor.redact(text)`

**Test gate:**

```bash
PII_MODE=comprehend make restart-worker
make test-tools
# privacy_tool should detect SSN/credit-card/address that regex misses
```

**Cost:** ~$0.0001 per 100 chars. Hackathon-scale (<$1).

**Latency:** 200–500 ms per call — adds noticeable time to every event. Acceptable for personalization use case where ingest is async anyway.

---

## 5. Phase 9 — S3 trace sync behind `TRACE_SYNC_MODE` (2h)

Maps to [plan.md Phase 9](plan.md). Today traces live only in the per-worker SQLite file at [worker/src/trace_logger.py:50](worker/src/trace_logger.py#L50). S3 sync becomes load-bearing in Phase 10 (AgentCore microVM has its own ephemeral filesystem).

### Implementation

New file `shared/s3_sync.py`:

```python
from datetime import datetime, timezone
from typing import Protocol
import logging, os, shutil, tempfile

log = logging.getLogger(__name__)

class TraceSync(Protocol):
    def sync(self, db_path: str, job_id: str) -> str | None: ...
    def fetch_for_job(self, job_id: str, dest_dir: str) -> list[str]: ...

class NoopTraceSync:
    def sync(self, db_path, job_id): return None
    def fetch_for_job(self, job_id, dest_dir): return []

class S3TraceSync:
    def __init__(self, bucket: str, prefix: str = "traces/", region: str = "us-east-1"):
        import boto3
        self.s3 = boto3.client("s3", region_name=region)
        self.bucket = bucket
        self.prefix = prefix

    def sync(self, db_path, job_id):
        if not os.path.exists(db_path):
            return None
        # Copy first — SQLite may be mid-write
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            shutil.copy2(db_path, tmp.name)
            now = datetime.now(timezone.utc)
            key = (
                f"{self.prefix}{now.strftime('%Y/%m/%d')}/"
                f"job_{job_id}_{int(now.timestamp())}.db"
            )
            try:
                self.s3.upload_file(tmp.name, self.bucket, key)
                return key
            finally:
                os.unlink(tmp.name)

    def fetch_for_job(self, job_id, dest_dir):
        # List all objects in today's prefix; download files mentioning job_id.
        # Simple approach for hackathon scale; for real prod, store an
        # index mapping job_id → s3_key in DDB jobs table.
        os.makedirs(dest_dir, exist_ok=True)
        downloaded = []
        # ... (boto3 list_objects_v2 + download)
        return downloaded

def make_trace_sync(mode: str, bucket: str, region: str) -> TraceSync:
    if mode == "s3":
        return S3TraceSync(bucket=bucket, region=region)
    return NoopTraceSync()
```

### Wiring

- [worker/src/job_handler.py:73](worker/src/job_handler.py#L73) — after `update_job_status("completed")`, call `ctx["trace_sync"].sync(tracer.db_path, job_id)` in a thread (don't block the worker loop on a 100-300ms S3 PUT). Or do it best-effort and log failures.
- [worker/src/main.py](worker/src/main.py) — build `trace_sync = make_trace_sync(settings.trace_sync_mode, settings.s3_traces_bucket, settings.aws_region)`, add to `ctx`.
- [server/src/routes/traces.py](server/src/routes/traces.py) — fall back to S3 if local glob returns no rows: `if not rows and settings.trace_sync_mode == "s3": s3_sync.fetch_for_job(...)`.
- New `scripts/setup_s3.py` + `make setup-s3` Makefile target — creates the bucket idempotently.

**Test gate:**

```bash
make setup-s3
TRACE_SYNC_MODE=s3 make restart-worker
curl -X POST .../events -d '...'
# Wait for completion, then:
aws s3 ls s3://hyperpersona-traces/traces/2026/05/06/
make down              # nuke local SQLite files
TRACE_SYNC_MODE=s3 make up
curl .../traces/<job_id>   # should still work — fetched from S3
```

**Risks:** S3 PUT cost is fine (~$0.005 per 1k requests). Latency is the real concern — must be off the critical path.

---

## 6. Phase 10 — AgentCore Runtime deployment

Maps to [plan.md Phase 10](plan.md). Deploy the Strands supervisor to [Bedrock AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/) (Firecracker microVM). Worker stops running the agent in-process; instead it RPCs into AgentCore.

### Why bother

- **Isolation** — agent failures don't crash the worker
- **Independent scaling** — supervisor can scale separately from event ingestion
- **Native AWS observability** — Bedrock AgentCore has built-in CloudWatch hooks
- **Demo wow** — "the agent runs in a Firecracker microVM" is a real differentiator

### 10a. AgentCore handler + Dockerfile (2h)

New directory `agentcore/`:

```
agentcore/
├── Dockerfile             # Python 3.13 + strands + tools
├── requirements.txt       # strands-agents, boto3, opensearch-py, redis
├── agent_handler.py       # AgentCore-compatible request handler
├── deploy.sh              # wraps `agentcore init` + `agentcore deploy`
└── tools/                 # symlinked or copied from worker/src/agents/tools
```

`agent_handler.py` (mirrors `StrandsSupervisor.run_process_event` but as a top-level handler):

```python
import json, os
from strands import Agent
from strands.models import BedrockModel

# Inside the microVM these are constructed once at cold-start
from shared.dynamo import DynamoClient
from shared.bedrock import make_bedrock_client
from shared.vector_store import make_vector_store
from shared.pii import make_pii_redactor
from shared.s3_sync import make_trace_sync
from trace_logger import TraceLogger
from tools.privacy_tool import make_privacy_tool
from tools.analyzer_tool import make_analyzer_tool

dynamo = DynamoClient(endpoint=None, region=os.environ["AWS_REGION"])  # real DDB
bedrock = make_bedrock_client(mode="real", ...)
vectors = make_vector_store(mode="aoss", ...)   # real OpenSearch Serverless
redactor = make_pii_redactor(mode="comprehend", ...)
tracer = TraceLogger("/tmp/agent_traces.db")
trace_sync = make_trace_sync(mode="s3", bucket=os.environ["S3_TRACES_BUCKET"], ...)

model = BedrockModel(
    model_id=os.environ["BEDROCK_TEXT_MODEL"],
    region_name=os.environ["AWS_REGION"],
)
agent = Agent(
    model=model,
    system_prompt=SUPERVISOR_PROMPT,
    tools=[
        make_privacy_tool(dynamo, redactor),
        make_analyzer_tool(bedrock, vectors),
    ],
    callback_handler=tracer.strands_callback,
)

def handler(request):
    job_id = request["job_id"]
    event = request["event"]
    tracer._current_job_id = job_id
    result = agent(f"Process event: {json.dumps(event)}")
    trace_sync.sync(tracer.db_path, job_id)
    return {"job_id": job_id, "result": str(result)}
```

Deploy:

```bash
cd agentcore
agentcore init    # interactive: region, IAM role, runtime
agentcore deploy  # builds + pushes container, registers agent runtime
# Outputs: arn:aws:bedrock-agentcore:us-east-1:<account>:agent-runtime/<id>
```

Save the ARN to `.env`:

```env
AGENTCORE_AGENT_ARN=arn:aws:bedrock-agentcore:...
```

### 10b. `agentcore` branch in `SUPERVISOR_MODE` (1h)

New `worker/src/agents/agentcore_supervisor.py`:

```python
import boto3, json, logging
log = logging.getLogger(__name__)

class AgentCoreSupervisor:
    def __init__(self, settings, tracer):
        self.client = boto3.client(
            "bedrock-agentcore", region_name=settings.aws_region,
        )
        self.agent_arn = settings.agentcore_agent_arn
        self.tracer = tracer

    def run_process_event(self, job_id, event):
        if not self.agent_arn:
            raise RuntimeError("AGENTCORE_AGENT_ARN not set")
        response = self.client.invoke_agent_runtime(
            agentRuntimeArn=self.agent_arn,
            runtimeSessionId=job_id,
            payload=json.dumps({"job_id": job_id, "event": event}),
        )
        body = json.loads(response["output"]["payload"])
        # Traces were already synced to S3 by the microVM; nothing to write here
        return {"status": "ok", "result": body.get("result")}
```

Add the branch to `make_supervisor` (already sketched in 14b).

**Test gate:**

```bash
SUPERVISOR_MODE=agentcore make restart-worker
make test-e2e
# External behavior identical; internally supervisor runs in microVM
make show-trace JOB=<id>
# Server route falls back to S3 via Phase 9 — must work
```

**Risks:**
- AgentCore CLI is new; double-check API shape against current AWS docs
- Cold-start ~5–10s on first invocation; warm calls ~1–2s
- IAM execution role for the microVM needs `bedrock:InvokeModel`, `dynamodb:*`, `s3:PutObject`, `comprehend:DetectPiiEntities`, `aoss:APIAccessAll` on the right resources
- The microVM has its own ephemeral filesystem — `/tmp/agent_traces.db` is local to that VM, which is **why Phase 9 is a hard prereq**

### Optional: OpenSearch Serverless migration

Today OpenSearch runs as a Docker container [docker-compose.yml:104-130](docker-compose.yml#L104-L130). For AgentCore's microVM to talk to it, either:

- (a) keep OpenSearch in EC2/ECS and expose it (cheapest, most work), or
- (b) migrate to **OpenSearch Serverless (AOSS)** — managed, no infra to run

Add `aoss` as a third `VECTOR_MODE` value behind the same factory. The OpenSearch Python client connects identically — just different host + AWS SigV4 auth instead of cleartext HTTP. ~1h of work; can be done lazily.

---

## 7. Phase 16 — Hardening (1h)

Same as [plan_remaining.md Phase 16](plan_remaining.md):

1. **Tenacity retries** on `BedrockClient.embed`/`generate`/`embed_batch` — wrap with `@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))`. Mock client unchanged. Also wrap `ComprehendRedactor.redact`.
2. **Sliding-window rate limit** — current limit is fixed-window [server/src/middleware/rate_limit.py](server/src/middleware/rate_limit.py). Sliding is more accurate at minute boundaries. Use a Redis sorted set of timestamps; trim everything older than `window_s` on each request, count remaining.
3. **Add `tenacity` to both `requirements.txt`** files.

Optional: add CloudWatch JSON-log shipping via boto3-logs if running in ECS.

---

## 8. Documentation + repo hygiene (15 min, do throughout)

- [.env.example](.env.example) — list every new toggle with comments explaining values
- [README.md](README.md) — add a "Modes" section showing the matrix:
  | Scenario | Env settings |
  |---|---|
  | Pure local dev | `BEDROCK_MODE=mock SUPERVISOR_MODE=manual PII_MODE=regex TRACE_SYNC_MODE=local` |
  | Real Bedrock, local supervisor | `BEDROCK_MODE=real SUPERVISOR_MODE=manual` |
  | Real Bedrock, Strands agent | `BEDROCK_MODE=real SUPERVISOR_MODE=strands` |
  | Full prod-like | `BEDROCK_MODE=real SUPERVISOR_MODE=agentcore PII_MODE=comprehend TRACE_SYNC_MODE=s3 VECTOR_MODE=aoss` |
- **DELETE** the Gemini key in [.env:5](.env#L5) — it's a committed secret. Rotate it on Google Cloud Console before pushing anything.

---

## 9. End-state checklist

After all phases:

- [ ] `BEDROCK_MODE=real` — real Claude Sonnet 4.5 + Titan Embed v2 calls everywhere
- [ ] `SUPERVISOR_MODE=strands` — supervisor is a real `strands.Agent`, Claude picks tool order
- [ ] `SUPERVISOR_MODE=agentcore` — supervisor runs in a Firecracker microVM
- [ ] `PII_MODE=comprehend` — production-grade PII detection
- [ ] `TRACE_SYNC_MODE=s3` — traces queryable across worker restarts and microVM lifecycles
- [ ] Tenacity retries + sliding-window rate limit
- [ ] Mock-mode equivalents still pass `make test-e2e` (no regression on offline dev)
- [ ] Original [plan.md](plan.md) Phases 1–12 all green
- [ ] `.env.example` documents all 6 mode toggles
- [ ] No committed secrets

---

## 10. Risks + escape hatches

| Risk | Mitigation |
|---|---|
| Strands SDK API drift breaks tools | `SUPERVISOR_MODE=manual` reverts to current orchestrator without rebuild |
| Claude refuses to call tools in correct order | Strengthen `SUPERVISOR_PROMPT`; in worst case fall back to manual |
| AgentCore cold-starts hurt p99 latency | Stay on `SUPERVISOR_MODE=strands` (in-process) for the recommend path; only use AgentCore for ingest |
| Comprehend misses domain-specific PII | Layer regex *before* Comprehend (defense in depth) |
| S3 sync latency leaks into the request path | Run sync in a `concurrent.futures` thread, don't await it |
| AWS bill surprise | Set a $50 billing alert in CloudWatch before flipping `BEDROCK_MODE=real` |
