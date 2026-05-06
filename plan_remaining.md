# HyperPersona — Remaining Work Plan

Picks up from [plan.md](plan.md). Everything below assumes phases 1-8, 11, and 12 are complete (mock-mode build, working `make test-e2e`).

## Summary

| # | Phase | Duration | Blocks on |
| - | ----- | -------- | --------- |
| 13 | AWS account + Bedrock model access | 30 min | credit card |
| 14 | Real Bedrock validation + Strands `@tool` wrap | 1.5h | Phase 13 |
| 15 | AWS Comprehend swap for PII | 30 min | Phase 13 |
| 9 | S3 trace sync (from original plan) | 2h | Phase 13 |
| 10 | AgentCore Runtime deployment (from original plan) | 3h | Phases 13, 14 |
| 16 | Rate limiting + Bedrock retries (final hardening) | 1h | none (can interleave) |

**Total: ~8.5 hours of focused work** after AWS is ready.

Recommended order: 13 → 14 → 15 → 9 → 10 → 16. Dependencies enforce most of this; 16 can slot in anywhere.

## Contract sync note (web + backend)

Before/while executing remaining phases, keep these docs in lockstep:
- `apps/web/API_HANDOVER_STATUS.md` for "implemented vs pending" API truth
- `apps/web/API_REQUIREMENTS.md` for target API/event contract
- `apps/web/FE_PLAN.md` for frontend tracking SDK and context-enrichment expectations

Tracking context expected across event ingestion includes device, local time/day, traffic source/referrer, coarse geo, optional weather, and scroll depth/purchase/return/search outcomes (consent-gated).

---

## Phase 13 — AWS account setup

**Goal:** AWS account ready, IAM user with the right permissions, Bedrock model access approved, creds in `.env`.

**Prerequisites:** credit card, ~30 min, ability to receive verification SMS.

**Steps:**

1. **Sign up at aws.amazon.com** (~15 min)
   - "Personal" account is fine — or use a Cognizant sandbox if available
   - Provide payment method (free-tier covers most things; Bedrock/Comprehend are pay-per-use, ~$0.001/1k tokens for Haiku, ~$0.003/1k for Sonnet)
   - Phone verification via SMS

2. **Create IAM user** (~10 min)
   - IAM console → Users → Create user
   - Programmatic access only (no console password needed)
   - Attach managed policies:
     - `AmazonBedrockFullAccess`
     - `AmazonDynamoDBFullAccess` *(only if migrating off DynamoDB Local)*
     - `AmazonS3FullAccess` *(for Phase 9)*
     - `AmazonOpenSearchServiceFullAccess` *(only if migrating off the local container)*
     - `ComprehendFullAccess` *(for Phase 15)*
     - `AWSLambda_FullAccess` and `AmazonBedrockAgentCoreFullAccess` *(for Phase 10)*
   - Generate access key → save the AKIA… and secret somewhere safe
   - **Never commit the secret.** It goes in `.env`, which is git-ignored.

3. **Request Bedrock model access** (~5 min)
   - Bedrock console → "Model access" (left sidebar)
   - Request access for: Anthropic Claude (Sonnet 4.5 minimum), Amazon Titan Text Embed v2
   - Approval is automatic and usually takes 1-5 minutes
   - Models with `us.` prefix (e.g. `us.anthropic.claude-sonnet-4-5-20250929-v1:0`) use cross-region inference profiles — these are what you actually invoke

4. **Update `.env`:**
   ```env
   AWS_ACCESS_KEY_ID=AKIA...
   AWS_SECRET_ACCESS_KEY=...
   AWS_REGION=us-east-1

   BEDROCK_MODE=real
   BEDROCK_REGION=us-east-1
   BEDROCK_TEXT_MODEL=us.anthropic.claude-sonnet-4-5-20250929-v1:0
   BEDROCK_EMBED_MODEL=amazon.titan-embed-text-v2:0
   ```

**Test checkpoint:**
```bash
make down && make up
make test-bedrock
# Should print:
#   mode:        real
#   embed dims:  1024
#   embed sample: [<real Titan floats>]
#   generate:    4
```

**Risks/gotchas:**
- Bedrock isn't free-tier — but typical hackathon usage is under $5 total
- Region matters: us-east-1 has the broadest model availability
- The `us.` model ID prefix is required for Anthropic models — without it you get `AccessDeniedException`
- If `make test-bedrock` returns "AccessDenied" → check model access approval status in console

---

## Phase 14 — Real Bedrock validation + Strands `@tool` wrap

**Goal:** Verify real Bedrock returns sensible outputs at every call site; upgrade `Supervisor` from a manual Python orchestrator to a real `strands.Agent` that lets Claude pick the tool-call sequence.

**Prerequisites:** Phase 13 complete; `make test-bedrock` returns real responses.

**Files to modify:**

| File | Change |
| ---- | ------ |
| [worker/src/agents/tools/privacy_tool.py](worker/src/agents/tools/privacy_tool.py) | Add `@tool` decorator + type annotations on all params |
| [worker/src/agents/tools/analyzer_tool.py](worker/src/agents/tools/analyzer_tool.py) | Same |
| [worker/src/agents/tools/recommender_tool.py](worker/src/agents/tools/recommender_tool.py) | Same |
| [worker/src/agents/tools/verifier_tool.py](worker/src/agents/tools/verifier_tool.py) | Same |
| [worker/src/agents/supervisor.py](worker/src/agents/supervisor.py) | Replace manual orchestrator with `strands.Agent(model=..., tools=[...])` |
| [worker/src/handlers/process_event.py](worker/src/handlers/process_event.py) | Invoke the agent with the event as input |

**Strands integration notes:**
- Strands `@tool` reads the function's type hints to build the tool schema Claude sees
- Tools that close over `dynamo`, `bedrock`, `vectors` need a factory pattern: `make_privacy_tool(dynamo)` → returns a `@tool`-decorated closure
- The supervisor's system prompt becomes the orchestration logic — Claude reads it and picks tool order

**Steps:**

1. Sanity-check each tool individually with real Bedrock:
   ```bash
   make test-tools
   ```
   - Privacy: confirm consent check still works (tool doesn't call Bedrock — should be unchanged)
   - Analyzer: confirm Claude returns valid JSON facts (may need prompt tuning)
   - Recommender: confirm draft offers are sensible
   - Verifier: confirm "VALID" responses return for accurate drafts

2. Refactor each tool to a factory + `@tool`:
   ```python
   # worker/src/agents/tools/privacy_tool.py
   from strands import tool

   def make_privacy_tool(dynamo):
       @tool
       def check_privacy(customer_id: str, text: str) -> dict:
           """Check consent and redact PII for a customer event."""
           # ... existing body
       return check_privacy
   ```

3. Rewrite `Supervisor`:
   ```python
   from strands import Agent
   from strands.models import BedrockModel

   class Supervisor:
       def __init__(self, dynamo, bedrock, vectors, tracer, settings):
           model = BedrockModel(
               model_id=settings.bedrock_text_model,
               region_name=settings.bedrock_region,
           )
           self.agent = Agent(
               model=model,
               system_prompt=SUPERVISOR_PROMPT,
               tools=[
                   make_privacy_tool(dynamo),
                   make_analyzer_tool(bedrock, vectors),
                   make_recommender_tool(bedrock, vectors),
                   make_verifier_tool(bedrock),
               ],
           )

       def run_process_event(self, job_id, event):
           prompt = f"Process this event: {json.dumps(event)}"
           result = self.agent(prompt)
           # Extract structured result, log trace
           return {"status": "ok", "result": str(result)}
   ```

4. Hook trace logger into Strands' callback API (Strands has built-in observability hooks)

5. Run end-to-end:
   ```bash
   make test-e2e
   make show-trace JOB=<id>   # should now show Claude's tool-calling chain
   ```

**Test checkpoint:**
- All 4 tools work individually with real Bedrock
- Supervisor agent successfully orchestrates a process_event end-to-end
- Trace shows Claude actually picking the tool order (not just our hardcoded sequence)

**Duration:** 1.5h (1h coding + 30 min prompt tuning if needed)

**Risks/gotchas:**
- Strands SDK is new and the API may have shifted — check current docs at https://strandsagents.com
- Real Bedrock latency: each call is 1-3s, so an agent loop with 4 tool calls takes 5-12s
- Claude may not call tools in the right order without a strong system prompt
- The mock-mode `MockBedrockClient` won't drive Strands — Strands wraps Bedrock directly via boto3, not through our wrapper

---

## Phase 15 — AWS Comprehend swap for PII detection

**Goal:** Replace the regex PII redactor with AWS Comprehend's `detect_pii_entities` for production-grade coverage (names, addresses, SSNs, credit cards, etc.).

**Prerequisites:** Phase 13 complete; ComprehendFullAccess on IAM user.

**Files:**

| File | Change |
| ---- | ------ |
| [shared/pii.py](shared/pii.py) | Add `ComprehendRedactor` class alongside existing regex `redact()`. Add `make_pii_redactor(mode, region)` factory. |
| [worker/src/agents/tools/privacy_tool.py](worker/src/agents/tools/privacy_tool.py) | Use factory based on `PII_MODE` env var |
| [worker/src/config.py](worker/src/config.py) | Add `pii_mode: str = "mock"` |
| [docker-compose.yml](docker-compose.yml) | Add `PII_MODE` env var (passes through `${PII_MODE:-mock}`) |
| [.env.example](.env.example) | Document `PII_MODE=real` |

**Steps:**

1. Write `ComprehendRedactor`:
   ```python
   class ComprehendRedactor:
       def __init__(self, region: str):
           import boto3
           self.client = boto3.client("comprehend", region_name=region)

       def redact(self, text: str) -> tuple[str, list[dict]]:
           if not text:
               return text, []
           response = self.client.detect_pii_entities(
               Text=text, LanguageCode="en"
           )
           entities = response.get("Entities", [])
           # Replace right-to-left to preserve indices
           result = text
           for ent in sorted(entities, key=lambda e: -e["BeginOffset"]):
               result = result[:ent["BeginOffset"]] + "[REDACTED]" + result[ent["EndOffset"]:]
           return result, [
               {"type": e["Type"], "match": text[e["BeginOffset"]:e["EndOffset"]]}
               for e in entities
           ]
   ```

2. Add factory:
   ```python
   class _RegexRedactor:
       def redact(self, text: str): return redact(text)  # existing function

   def make_pii_redactor(mode: str, region: str = "us-east-1"):
       if mode == "real":
           return ComprehendRedactor(region)
       return _RegexRedactor()
   ```

3. Update `privacy_tool` to call `redactor.redact(text)` instead of bare `redact(text)`

4. Test:
   ```bash
   PII_MODE=real make test-tools
   # Privacy tool should detect more PII categories than regex (addresses, SSNs)
   ```

**Test checkpoint:** Privacy tool redacts names, emails, phones, addresses, SSNs, credit-card numbers — anything Comprehend recognizes.

**Duration:** 30 min

**Risks/gotchas:**
- Comprehend pricing: ~$0.0001 per 100 chars — negligible at hackathon scale
- Per-call latency: 200-500ms — adds noticeable time to every event
- Only English is well-supported

---

## Phase 9 — S3 trace sync *(from original plan.md)*

**Goal:** Worker syncs the SQLite trace file to S3 after every job completion. Server reads traces from S3 when not locally available.

**Prerequisites:** Phase 13 complete; S3 bucket created.

**Files:**

| File | Change |
| ---- | ------ |
| [shared/s3_sync.py](shared/s3_sync.py) | New — `S3TraceSync` class wrapping boto3 S3 |
| [worker/src/job_handler.py](worker/src/job_handler.py) | After job completion, call `s3_sync.sync(db_path)` |
| [server/src/routes/traces.py](server/src/routes/traces.py) | If local SQLite doesn't have the job_id, fall back to downloading from S3 |
| [scripts/setup_s3.py](scripts/setup_s3.py) | New — create the bucket if it doesn't exist |
| [worker/src/config.py](worker/src/config.py) and [server/src/config.py](server/src/config.py) | Add `s3_traces_bucket: str = "hyperpersona-traces"` |
| [docker-compose.yml](docker-compose.yml) | Add `S3_TRACES_BUCKET` env var |
| [Makefile](Makefile) | `make setup-s3`, `make list-s3-traces` |

**Sync strategy:**
- After each job completes (in `job_handler.dispatch`), upload the entire SQLite file to `s3://hyperpersona-traces/traces/{YYYY}/{MM}/{DD}/traces_{ts}.db`
- Filename includes timestamp so concurrent jobs don't collide
- Server's `GET /traces/{job_id}` first checks local SQLite; if not found, lists S3 by prefix and downloads matching file(s)

**Steps:**

1. Write `S3TraceSync` class with `sync()`, `download()`, `list_traces()` methods
2. Add `make setup-s3` target that creates the bucket via boto3
3. Modify `job_handler.dispatch` to call sync after `update_job_status("completed")`
4. Modify `traces.py` route to fall back to S3 lookup
5. Test:
   ```bash
   make setup-s3
   curl -X POST -H "X-API-Key: test-key" http://localhost:8000/events ...
   aws s3 ls s3://hyperpersona-traces/traces/
   curl http://localhost:8000/traces/<job_id>  # works even after worker restart
   ```

**Test checkpoint:**
- Restart the worker container — traces from before are still queryable
- `aws s3 ls s3://hyperpersona-traces/traces/2026/05/03/` shows uploaded files

**Duration:** 2h

**Risks/gotchas:**
- S3 PutObject latency adds ~100-300ms per job — make it async or wrap in a thread to not block
- Concurrent uploads: SQLite file may be locked momentarily; copy then upload
- S3 storage cost: $0.023/GB/month — negligible for traces

---

## Phase 10 — AgentCore Runtime deployment *(from original plan.md)*

**Goal:** Deploy the supervisor agent to Bedrock AgentCore Runtime (Firecracker microVM). Worker stops running the agent in-process — instead it invokes the AgentCore endpoint.

**Prerequisites:** Phases 13, 14 complete; AgentCore enabled in your AWS region.

**Files:**

| File | Change |
| ---- | ------ |
| [agentcore/Dockerfile](agentcore/Dockerfile) | New — Python 3.13 base + Strands + tools, AgentCore-compatible entrypoint |
| [agentcore/agent_handler.py](agentcore/agent_handler.py) | New — request handler invoking the Strands `Agent` |
| [agentcore/requirements.txt](agentcore/requirements.txt) | New — strands, boto3, opensearch-py |
| [agentcore/deploy.sh](agentcore/deploy.sh) | New — wraps `agentcore init` + `agentcore deploy` |
| [worker/src/agentcore_client.py](worker/src/agentcore_client.py) | New — `AgentCoreClient` wrapping `bedrock-agentcore` boto3 |
| [worker/src/handlers/process_event.py](worker/src/handlers/process_event.py) | Replace local `supervisor.run_process_event(...)` with `agentcore_client.invoke(...)` |
| [worker/src/config.py](worker/src/config.py) | Add `agentcore_agent_arn: str` |

**Steps:**

1. **Build the AgentCore handler** (mirrors local supervisor):
   ```python
   # agentcore/agent_handler.py
   def handler(request):
       job_id = request["job_id"]
       event = request["event"]
       result = agent(f"Process event: {json.dumps(event)}")
       s3_sync.sync("/tmp/agent_traces.db")  # Phase 9 reuse
       return {"job_id": job_id, "result": str(result)}
   ```

2. **Initialize AgentCore project:**
   ```bash
   cd agentcore
   agentcore init  # interactive — picks region, runtime, IAM role
   ```

3. **Deploy:**
   ```bash
   agentcore deploy
   # Returns: arn:aws:bedrock-agentcore:us-east-1:<account>:agent-runtime/abc123
   ```

4. **Save ARN to `.env`:**
   ```env
   AGENTCORE_AGENT_ARN=arn:aws:bedrock-agentcore:...
   ```

5. **Write `worker/src/agentcore_client.py`:**
   ```python
   class AgentCoreClient:
       def __init__(self, agent_arn, region):
           self.client = boto3.client("bedrock-agentcore", region_name=region)
           self.agent_arn = agent_arn

       def invoke(self, job_id, event):
           response = self.client.invoke_agent_runtime(
               agentRuntimeArn=self.agent_arn,
               runtimeSessionId=job_id,
               payload=json.dumps({"job_id": job_id, "event": event}),
           )
           return json.loads(response["output"]["payload"])
   ```

6. **Modify worker `process_event.handle`** to use `ctx["agentcore"]` instead of `ctx["supervisor"]`. Keep both available so you can swap via env var (`SUPERVISOR_MODE=local|agentcore`).

7. **Test:**
   ```bash
   make test-e2e
   # Same external behavior — internally, supervisor runs in a microVM
   make show-trace JOB=<id>
   # Traces synced to S3 from inside the microVM
   ```

**Test checkpoint:**
- `aws s3 ls s3://hyperpersona-traces/` shows traces from AgentCore-driven jobs
- Trace timestamps line up with curl request times
- Worker logs show `agentcore.invoke succeeded` instead of local supervisor logs

**Duration:** 3h

**Risks/gotchas:**
- AgentCore is newer — CLI behavior and SDK shape may have changed
- IAM role for AgentCore execution needs to be created (the `agentcore init` flow handles this in most cases)
- Cold-start latency on first invocation: ~5-10s; subsequent calls cached
- Each invocation costs roughly $0.0001 per 1k tokens of input/output (similar to direct Bedrock)
- The microVM has its own filesystem — `/tmp/agent_traces.db` is local; sync to S3 (Phase 9) is now load-bearing

---

## Phase 16 — Rate limiting + Bedrock retries (final hardening)

**Goal:** Sliding-window rate limit on the API, retry-with-backoff on every Bedrock call.

**Files:**

| File | Change |
| ---- | ------ |
| [server/src/middleware/rate_limit.py](server/src/middleware/rate_limit.py) | New — Redis sliding window per `X-API-Key` |
| [server/src/main.py](server/src/main.py) | Mount middleware after auth |
| [shared/bedrock.py](shared/bedrock.py) | Wrap `embed/generate` with `tenacity` retry decorator |
| [server/requirements.txt](server/requirements.txt) | Already has redis; add `tenacity` if needed |
| [worker/requirements.txt](worker/requirements.txt) | Add `tenacity` |

**Steps:**

1. Implement sliding-window rate limit:
   ```python
   # server/src/middleware/rate_limit.py
   class RateLimitMiddleware(BaseHTTPMiddleware):
       def __init__(self, app, redis_client, limit=100, window_s=60):
           super().__init__(app)
           self.redis = redis_client
           self.limit = limit
           self.window_s = window_s

       async def dispatch(self, request, call_next):
           key = request.headers.get("x-api-key", "anonymous")
           bucket = f"ratelimit:{key}:{int(time.time() // self.window_s)}"
           count = self.redis.incr(bucket)
           if count == 1:
               self.redis.expire(bucket, self.window_s + 1)
           if count > self.limit:
               return JSONResponse(429, {"error": "rate limit exceeded"})
           return await call_next(request)
   ```

2. Wrap Bedrock calls:
   ```python
   from tenacity import retry, stop_after_attempt, wait_exponential

   class BedrockClient:
       @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
       def embed(self, text: str) -> list[float]:
           ...
   ```

3. Test:
   ```bash
   # Rate limit
   for i in {1..150}; do
     curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: test-key" http://localhost:8000/health
   done | sort | uniq -c
   # Should see ~100x 200 then 50x 429
   ```

**Test checkpoint:**
- 100 requests in <1 min → all 200
- 101st request → 429
- Bedrock call survives a transient network error (mock by killing/restarting the container mid-call)

**Duration:** 1h

---

## End state

After all six phases, you have:

- ✅ Real AWS Bedrock for all LLM calls (Strands-orchestrated agent)
- ✅ Real AWS Comprehend for PII detection
- ✅ Trace archive in S3 (queryable across worker restarts and microVM lifecycles)
- ✅ Supervisor running in a Firecracker microVM via AgentCore
- ✅ Rate limiting + per-call retries
- ✅ Full plan.md compliance

**At that point the project is complete relative to the original spec.** Anything further is real prod hardening: monitoring, alerting, multi-region, autoscaling, load tests, observability via OpenTelemetry, etc.
