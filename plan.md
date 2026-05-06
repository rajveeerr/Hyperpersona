# HyperPersona — Phase-by-Phase Build Plan - personalized recommendations 

## Architecture recap

Three deployment units:

```
┌─────────────────────────────────────┐
│  SERVER (Docker image #1)           │
│  FastAPI / Express                  │
│  Business logic, REST API, auth     │
│  Talks to: DynamoDB, Redis, Worker  │
└──────────────┬──────────────────────┘
               │ enqueues jobs
               ▼
┌─────────────────────────────────────┐
│  WORKER (Docker image #2)           │
│  Python process                     │
│  Picks up jobs from queue           │
│  Orchestrates AgentCore calls       │
│  Talks to: Redis/SQS, AgentCore,   │
│  DynamoDB, OpenSearch, S3           │
└──────────────┬──────────────────────┘
               │ invokes
               ▼
┌─────────────────────────────────────┐
│  AGENTCORE RUNTIME (Firecracker)    │
│  Main supervisor agent (Strands)    │
│  SQLite trace file → syncs to S3   │
│  Sub-agents: privacy, analyzer,    │
│  recommender, verifier             │
│  Talks to: Bedrock, tools via GW   │
└─────────────────────────────────────┘
```

---

## Phase 1 — Project scaffold and local dev environment

**Goal:** Monorepo with both Docker images building and running locally. No business logic yet — just "hello world" from both services and a working docker-compose.

**What to build:**

```
hyperpersona/
├── docker-compose.yml          # server + worker + redis + dynamodb-local
├── docker-compose.infra.yml    # just infra (redis, dynamodb-local, localstack)
├── server/
│   ├── Dockerfile
│   ├── requirements.txt        # fastapi, uvicorn, boto3, pydantic-settings
│   ├── src/
│   │   ├── main.py             # FastAPI app, GET /health returns {"status": "ok"}
│   │   └── config.py           # Pydantic BaseSettings, reads env vars
│   └── tests/
│       └── test_health.py
├── worker/
│   ├── Dockerfile
│   ├── requirements.txt        # boto3, redis, pydantic-settings, strands-agents
│   ├── src/
│   │   ├── main.py             # Entry point, connects to Redis, logs "worker ready"
│   │   └── config.py           # Shared settings
│   └── tests/
│       └── test_worker_boot.py
├── shared/
│   ├── schemas.py              # Pydantic models shared between server and worker
│   └── constants.py            # Queue names, table names, collection names
├── scripts/
│   ├── setup_dynamodb.py       # Create tables in DynamoDB Local
│   └── setup_opensearch.py     # Create collections (placeholder)
├── .env.example
├── Makefile                    # make up, make down, make test, make server, make worker
└── README.md
```

**Steps:**

1. Create the directory structure
2. Write server Dockerfile (Python 3.13, FastAPI)
3. Write worker Dockerfile (Python 3.13)
4. Write docker-compose.yml with: server (port 8000), worker, redis (port 6379), dynamodb-local (port 8001)
5. Server main.py: FastAPI app with GET /health
6. Worker main.py: connects to Redis, prints "worker started", loops waiting for jobs
7. Makefile with shortcuts: `make up`, `make down`, `make logs`, `make test`
8. .env.example with all required vars

**Test checkpoint:**

```bash
make up
curl http://localhost:8000/health   # → {"status": "ok"}
docker logs hyperpersona-worker-1   # → "worker started, waiting for jobs"
```

**Duration:** 1–2 hours

---

## Phase 2 — Data model and DynamoDB tables

**Goal:** All DynamoDB tables created and accessible from both server and worker. Pydantic models defined. CRUD operations tested.

**What to build:**

**shared/schemas.py** — Pydantic models:

```python
class CustomerEvent(BaseModel):
    customer_id: str
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str  # page_view, add_to_cart, purchase, return, search
    payload: dict
    status: str = "pending"  # pending → processing → processed | failed
    consent_scope: set[str] = set()
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class ConsentRecord(BaseModel):
    customer_id: str
    scopes: set[str]  # {"personalization", "analytics", "marketing"}
    data_retention_days: int = 90
    last_updated: str

class Job(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid4()))
    job_type: str  # "process_event", "generate_recommendation", "batch_import"
    payload: dict
    status: str = "queued"  # queued → running → completed | failed
    created_at: str
    completed_at: str | None = None
    error: str | None = None

class Product(BaseModel):
    product_id: str
    name: str
    brand: str
    category: str
    description: str
    tags: list[str] = []
    price: float
    inventory_count: int
    margin_band: str = "medium"  # low | medium | high
    promotion: str | None = None
    active: bool = True
    image_url: str | None = None
    catalog_version: int = 1
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class RecommendationItem(BaseModel):
    product_id: str
    name: str
    score: float
    reason: str
    offer: str | None = None

class RecommendationRecord(BaseModel):
    recommendation_id: str = Field(default_factory=lambda: str(uuid4()))
    customer_id: str
    job_id: str | None = None
    context: str
    items: list[RecommendationItem]
    why: list[str] = []
    avoided: list[str] = []
    confidence: float | None = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
```

**Tables to create:**

| Table | PK | SK | GSI |
|-------|----|----|-----|
| customer_events | CUSTOMER#{id} | EVENT#{timestamp}#{event_id} | status-index (status, created_at) |
| customer_consent | CUSTOMER#{id} | CONSENT | — |
| jobs | JOB#{job_id} | META | status-index (status, created_at) |
| product_catalog | PRODUCT#{product_id} | META | category-index (category, updated_at) |
| recommendations | CUSTOMER#{id} | RECOMMENDATION#{created_at}#{recommendation_id} | job-index (job_id, created_at) |

**Product catalog storage rule:**

Keep products in both a normal DB and a vector DB:

- `product_catalog` in DynamoDB is the source of truth for product_id, price, inventory, margin, promotion, active status, image URL, and catalog_version.
- `product-catalog` in OpenSearch/vector DB is a semantic search index for product descriptions, tags, use cases, style attributes, and embeddings.
- The vector DB should return candidate `product_id` values only. The recommender must hydrate fresh price, inventory, active status, and promotion from DynamoDB before producing the final offer.
- Use `catalog_version` or `updated_at` in both stores to detect stale vector records.

**Files to create/modify:**

- shared/schemas.py — all Pydantic models
- shared/dynamo.py — DynamoDB helper class (put_item, get_item, query, update_status)
- scripts/setup_dynamodb.py — creates all tables in DynamoDB Local
- scripts/seed_products.py — seeds product_catalog and syncs product-catalog vector index
- server/src/main.py — add POST /events endpoint (writes to DynamoDB + enqueues job)
- server/tests/test_events.py — test event creation

**Steps:**

1. Write shared/schemas.py with all models
2. Write shared/dynamo.py with a DynamoClient class wrapping boto3
3. Write scripts/setup_dynamodb.py to create tables
4. Add Product and RecommendationRecord models
5. Add POST /events to server: validate with Pydantic, write to customer_events table, push job to Redis queue
6. Seed a small retail catalog into DynamoDB for demo scenarios
7. Test: POST an event, verify it's in DynamoDB, verify job is in Redis

**Test checkpoint:**

```bash
python scripts/setup_dynamodb.py              # tables created
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"cust_1","event_type":"page_view","payload":{"page":"/shoes"}}'
# → 202, {"event_id": "...", "status": "queued"}

# Verify in DynamoDB:
aws dynamodb scan --table-name customer_events --endpoint-url http://localhost:8001
```

**Duration:** 2–3 hours

---

## Phase 3 — Worker job loop and queue integration

**Goal:** Worker picks up jobs from Redis queue, processes them (stub), updates job status in DynamoDB. End-to-end flow: server enqueues → worker dequeues → status updates.

**What to build:**

- worker/src/queue.py — Redis queue consumer (BRPOP loop or use rq/bullmq equivalent)
- worker/src/job_handler.py — Job dispatcher: reads job_type, routes to handler function
- worker/src/handlers/process_event.py — Stub handler: logs "processing event X", sleeps 1s, marks as "processed"
- worker/src/handlers/generate_recommendation.py — Stub handler for recommendation jobs

**Queue design:**

```
Redis List: "jobs:pending"
Worker does BRPOP → gets job JSON → deserializes → routes to handler → updates DynamoDB
```

Or use **SQS** if you want AWS-native (better for production, but Redis is simpler for local dev).

**Steps:**

1. Write queue.py: BRPOP loop on "jobs:pending", deserialize JSON, call job_handler
2. Write job_handler.py: match on job_type, call appropriate handler
3. Write process_event.py stub: log the event, update customer_events status to "processing" then "processed", update jobs table status
4. Modify server POST /events to push job JSON to Redis list
5. Test the full loop

**Test checkpoint:**

```bash
make up
curl -X POST http://localhost:8000/events \
  -d '{"customer_id":"cust_1","event_type":"purchase","payload":{"product":"shoes","price":99}}'
# Wait 2 seconds
docker logs hyperpersona-worker-1
# → "Processing event abc-123 for customer cust_1"
# → "Event abc-123 marked as processed"

# Verify in DynamoDB:
# customer_events: status = "processed"
# jobs: status = "completed"
```

**Duration:** 2–3 hours

---

## Phase 4 — Bedrock connection and basic agent

**Goal:** Worker can call Amazon Bedrock for embeddings and text generation. A basic Strands agent runs locally and responds to a prompt.

**What to build:**

- shared/bedrock.py — Bedrock client wrapper: embed(text) → vector, generate(prompt) → text
- worker/src/agents/base_agent.py — Minimal Strands agent that can answer a question
- worker/tests/test_bedrock.py — Test embedding and generation calls
- worker/tests/test_agent.py — Test that the agent responds

**shared/bedrock.py:**

```python
import boto3
import json

class BedrockClient:
    def __init__(self, region="us-east-1"):
        self.bedrock = boto3.client("bedrock-runtime", region_name=region)

    def embed(self, text: str) -> list[float]:
        response = self.bedrock.invoke_model(
            modelId="amazon.titan-embed-text-v2:0",
            body=json.dumps({"inputText": text})
        )
        return json.loads(response["body"].read())["embedding"]

    def generate(self, prompt: str, system: str = "") -> str:
        response = self.bedrock.invoke_model(
            modelId="anthropic.claude-sonnet-4-20250514-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [{"role": "user", "content": prompt}],
                "system": system,
                "max_tokens": 1024
            })
        )
        result = json.loads(response["body"].read())
        return result["content"][0]["text"]
```

**worker/src/agents/base_agent.py:**

```python
from strands import Agent
from strands.models import BedrockModel

model = BedrockModel(
    model_id="anthropic.claude-sonnet-4-20250514-v1:0",
    region_name="us-east-1"
)

agent = Agent(
    model=model,
    system_prompt="You are a test agent. Respond concisely."
)

# Test: agent("What is 2+2?")
```

**Steps:**

1. Write shared/bedrock.py
2. Configure AWS credentials in .env (or use IAM role)
3. Test embed() — should return a 1024-dim vector
4. Test generate() — should return text
5. Write base_agent.py with Strands
6. Test agent invocation

**Test checkpoint:**

```bash
cd worker && python -c "
from src.agents.base_agent import agent
result = agent('What is 2+2?')
print(result)
"
# → "4"

cd worker && python -c "
from shared.bedrock import BedrockClient
bc = BedrockClient()
vec = bc.embed('test sentence')
print(f'Embedding dim: {len(vec)}')
"
# → "Embedding dim: 1024"
```

**Duration:** 1–2 hours

---

## Phase 5 — Sub-agents as tools

**Goal:** Four specialized sub-agents built as Strands @tool functions. Each can be called independently and tested in isolation.

**What to build:**

```
worker/src/agents/
├── tools/
│   ├── privacy_tool.py         # Consent check + PII redaction
│   ├── analyzer_tool.py        # Fact extraction + embedding
│   ├── recommender_tool.py     # RAG retrieval + offer generation
│   └── verifier_tool.py        # Chain-of-Verification
├── supervisor.py               # Main agent (Phase 6)
└── base_agent.py               # From Phase 4
```

**privacy_tool.py:**

```python
from strands import tool

@tool
def check_privacy(customer_id: str, event_text: str) -> dict:
    """Check customer consent and redact PII from event text.
    Returns redacted text and consent status."""

    # 1. Check consent in DynamoDB
    consent = dynamo.get_consent(customer_id)
    if not consent or "personalization" not in consent.scopes:
        return {"allowed": False, "reason": "no_consent"}

    # 2. Call Comprehend for PII detection
    pii_response = comprehend.detect_pii_entities(Text=event_text, LanguageCode="en")
    redacted = redact_pii(event_text, pii_response["Entities"])

    return {"allowed": True, "redacted_text": redacted, "pii_found": len(pii_response["Entities"])}
```

**analyzer_tool.py:**

```python
@tool
def analyze_behavior(customer_id: str, event_text: str, event_id: str) -> dict:
    """Extract facts from event, embed them, store in vector memory.
    Returns extracted facts."""

    # 1. Embed event text
    vector = bedrock.embed(event_text)

    # 2. Extract facts via Bedrock (JSON mode)
    facts = bedrock.generate(
        prompt=f"Extract atomic facts from: {event_text}",
        system="Return JSON array of facts. Each fact is a short declarative sentence."
    )

    # 3. Upsert event embedding to OpenSearch
    opensearch.upsert("behavior-embeddings", event_id, vector, {
        "customer_id": customer_id, "text": event_text
    })

    # 4. For each fact: embed + upsert to facts collection
    for fact in parsed_facts:
        fact_vec = bedrock.embed(fact["text"])
        opensearch.upsert("customer-facts", fact["id"], fact_vec, {
            "customer_id": customer_id, "text": fact["text"], "source_event": event_id
        })

    return {"facts_extracted": len(parsed_facts), "event_embedded": True}
```

**recommender_tool.py:**

```python
@tool
def generate_recommendation(customer_id: str, context: str, limit: int = 5) -> dict:
    """Retrieve memory + product candidates, apply ACE/business ranking,
    and generate multiple personalized offers."""

    # 1. Embed context
    query_vec = bedrock.embed(context)

    # 2. Parallel retrieval from customer memory and product catalog
    facts = opensearch.search("customer-facts", query_vec, k=8, filter=customer_id)
    events = opensearch.search("behavior-embeddings", query_vec, k=8, filter=customer_id)
    product_hits = opensearch.search("product-catalog", query_vec, k=20, filter={"active": True})
    session = redis.get(f"session:{customer_id}")

    # 3. ACE ranking (recency, polarity, conflict detection)
    ranked_facts, conflicts = ace_ranking(facts)

    # 4. Hydrate vector candidates from product_catalog source of truth
    product_ids = [hit["product_id"] for hit in product_hits]
    products = dynamo.batch_get_products(product_ids)
    products = [p for p in products if p["active"] and p["inventory_count"] > 0]

    # 5. Rank products with semantic match + customer fit + business rules
    ranked_products = rank_products(products, product_hits, ranked_facts, conflicts)[:limit]

    # 6. Generate offers via Bedrock
    offers = bedrock.generate(
        prompt=build_recommendation_prompt(ranked_facts, events, session, ranked_products, conflicts),
        system=RECOMMENDER_SYSTEM_PROMPT
    )

    return {
        "items": offers["items"],
        "facts_used": len(ranked_facts),
        "products_considered": len(products),
        "conflicts": conflicts,
        "why": offers.get("why", []),
        "avoided": offers.get("avoided", []),
        "confidence": offers.get("confidence")
    }
```

**verifier_tool.py:**

```python
@tool
def verify_recommendation(draft_offer: str, source_context: str) -> dict:
    """Chain-of-Verification: fact-check the draft offer against source data.
    Returns VALID or a corrected offer."""

    verdict = bedrock.generate(
        prompt=f"Draft: {draft_offer}\n\nSource data: {source_context}\n\n"
               "If the draft accurately reflects the source data, reply exactly VALID. "
               "Otherwise, rewrite the recommendation to be accurate.",
        system="You are a fact-checker. Only use information from the source data."
    )

    if verdict.strip() == "VALID":
        return {"status": "valid", "final_offer": draft_offer}
    else:
        return {"status": "corrected", "final_offer": verdict}
```

**Steps:**

1. Write privacy_tool.py — test with a mock customer who has consent and one who doesn't
2. Write analyzer_tool.py — test fact extraction with a sample event (stub OpenSearch for now)
3. Write recommender_tool.py — test with mock data in OpenSearch
4. Write verifier_tool.py — test with a correct draft and an incorrect draft
5. Write unit tests for each tool independently

**Test checkpoint for each tool:**

```bash
# Privacy tool
python -c "
from worker.src.agents.tools.privacy_tool import check_privacy
result = check_privacy(customer_id='cust_1', event_text='John bought shoes at john@email.com')
print(result)
"
# → {"allowed": True, "redacted_text": "[REDACTED] bought shoes at [REDACTED]", "pii_found": 2}

# Verifier tool
python -c "
from worker.src.agents.tools.verifier_tool import verify_recommendation
result = verify_recommendation(
    draft_offer='We recommend Nike shoes based on your love of Nike',
    source_context='Customer returned 3 Nike orders last month'
)
print(result)
"
# → {"status": "corrected", "final_offer": "Based on your recent activity..."}
```

**Duration:** 4–6 hours

---

## Phase 6 — Supervisor agent and job orchestration

**Goal:** The main supervisor agent uses all four sub-agent tools. The worker creates a "job" that the supervisor manages end-to-end. SQLite trace logging begins.

**What to build:**

- worker/src/agents/supervisor.py — Main Strands agent with all 4 tools bound
- worker/src/trace_logger.py — SQLite-based trace logger
- worker/src/handlers/process_event.py — Replace stub with supervisor agent call

**supervisor.py:**

```python
from strands import Agent
from strands.models import BedrockModel
from .tools.privacy_tool import check_privacy
from .tools.analyzer_tool import analyze_behavior
from .tools.recommender_tool import generate_recommendation
from .tools.verifier_tool import verify_recommendation

model = BedrockModel(
    model_id="anthropic.claude-sonnet-4-20250514-v1:0",
    region_name="us-east-1"
)

supervisor = Agent(
    model=model,
    system_prompt="""You are the HyperPersona supervisor agent. You manage the personalization
    pipeline for customer behavior events.

    For each event you receive, execute these steps IN ORDER:
    1. Call check_privacy to verify consent and redact PII
    2. If privacy check passes, call analyze_behavior to extract and store patterns
    3. If analysis succeeds, call generate_recommendation to create a personalized offer
    4. Call verify_recommendation to fact-check the offer before returning it

    If any step fails, stop and report the failure. Always explain what you did.""",
    tools=[check_privacy, analyze_behavior, generate_recommendation, verify_recommendation]
)
```

**trace_logger.py:**

```python
import sqlite3
import json
from datetime import datetime

class TraceLogger:
    def __init__(self, db_path="/tmp/agent_traces.db"):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT,
                agent_name TEXT,
                step TEXT,
                input TEXT,
                output TEXT,
                duration_ms REAL,
                timestamp TEXT,
                status TEXT
            )
        """)
        self.conn.commit()

    def log(self, job_id, agent_name, step, input_data, output_data, duration_ms, status="ok"):
        self.conn.execute(
            "INSERT INTO traces VALUES (NULL,?,?,?,?,?,?,?,?)",
            (job_id, agent_name, step, json.dumps(input_data),
             json.dumps(output_data), duration_ms,
             datetime.utcnow().isoformat(), status)
        )
        self.conn.commit()

    def get_traces(self, job_id):
        cur = self.conn.execute("SELECT * FROM traces WHERE job_id=? ORDER BY id", (job_id,))
        return cur.fetchall()
```

**Updated process_event handler:**

```python
import time
from ..agents.supervisor import supervisor
from ..trace_logger import TraceLogger

tracer = TraceLogger()

def handle_process_event(job):
    job_id = job["job_id"]
    event = job["payload"]

    start = time.time()
    tracer.log(job_id, "supervisor", "start", event, {}, 0)

    # Invoke the supervisor agent with the event
    prompt = f"""Process this customer event:
    Customer: {event['customer_id']}
    Type: {event['event_type']}
    Data: {json.dumps(event['payload'])}"""

    result = supervisor(prompt)

    duration = (time.time() - start) * 1000
    tracer.log(job_id, "supervisor", "complete", {}, {"result": str(result)}, duration)

    # Update DynamoDB status
    dynamo.update_event_status(event["event_id"], "processed")
    dynamo.update_job_status(job_id, "completed")

    return result
```

**Steps:**

1. Write supervisor.py with all 4 tools bound
2. Write trace_logger.py with SQLite
3. Update process_event handler to use supervisor
4. Test: POST an event → worker picks it up → supervisor runs all 4 steps → traces logged to SQLite
5. Query SQLite to verify traces

**Test checkpoint:**

```bash
curl -X POST http://localhost:8000/events \
  -d '{"customer_id":"cust_1","event_type":"purchase","payload":{"product":"trail shoes","price":129}}'

# Wait for worker to process
# Then check traces:
python -c "
from worker.src.trace_logger import TraceLogger
t = TraceLogger()
for trace in t.get_traces('JOB_ID_HERE'):
    print(trace)
"
# Should show: start → privacy_check → analyze → recommend → verify → complete
```

**Duration:** 3–4 hours

---

## Phase 7 — OpenSearch vector memory (ACE layer)

**Goal:** Customer memory and product catalog vector collections working. ACE ranking logic ported. Retrieval + storage tested end-to-end.

**What to build:**

- shared/opensearch.py — OpenSearch Serverless client (or use opensearch-py with local Docker OpenSearch for dev)
- shared/ace_ranking.py — recencyWeight, normalizeKey, polarityScore, conflict detection
- docker-compose.yml — add OpenSearch container for local dev
- scripts/setup_opensearch.py — create 3 collections with 1024-dim cosine index

**Vector collections:**

| Collection | Purpose | Source of truth |
|------------|---------|-----------------|
| customer-facts | Durable extracted customer preferences and facts | OpenSearch + DynamoDB event lineage |
| behavior-embeddings | Raw event memory for semantic retrieval | customer_events |
| session-summaries | Short-term customer/session memory | Redis/DynamoDB |
| product-catalog | Semantic product retrieval | product_catalog DynamoDB table |

**Product catalog sync flow:**

```text
Product created/updated in product_catalog
        |
        v
Build embedding_text from name, brand, category, description, tags, use cases
        |
        v
Generate embedding with Bedrock
        |
        v
Upsert product-catalog vector doc with product_id and catalog_version
```

For the hackathon, `scripts/seed_products.py` can do the whole sync. For production, replace that with DynamoDB Streams -> Lambda/ECS sync worker -> Bedrock embeddings -> OpenSearch upsert.

**shared/ace_ranking.py** (ported from your helpers.ts):

```python
import re
from datetime import datetime

STOPWORDS = {"the","a","an","is","are","was","were","be","been","being",
             "have","has","had","do","does","did","will","would","shall",
             "should","may","might","must","can","could","i","me","my","we",
             "our","you","your","he","him","she","her","it","its","they",
             "them","their","this","that","these","those","and","but","or",
             "so","if","then","than","of","in","on","at","to","for","with",
             "by","from","as","into","about","between","through","after",
             "before","during","above","below","up","down","out","off","over"}

NEGATION_WORDS = {"not","no","never","neither","nor","don't","doesn't",
                  "didn't","won't","wouldn't","can't","couldn't","shouldn't",
                  "isn't","aren't","wasn't","weren't","hardly","barely","scarcely"}

POSITIVE_WORDS = {"love","like","enjoy","prefer","want","favorite","great",
                  "good","best","always","happy","excited"}

FACT_HALF_LIFE_DAYS = 45
FACT_SCORE_THRESHOLD = 0.12
FACT_LIMIT = 6

def recency_weight(days_ago: float) -> float:
    return 0.5 ** (days_ago / FACT_HALF_LIFE_DAYS)

def normalize_key(text: str) -> str:
    tokens = re.findall(r'\w+', text.lower())
    meaningful = [t for t in tokens if t not in STOPWORDS and t not in NEGATION_WORDS]
    return " ".join(meaningful[:4])

def polarity_score(text: str) -> int:
    words = set(text.lower().split())
    has_neg = bool(words & NEGATION_WORDS)
    has_pos = bool(words & POSITIVE_WORDS)
    if has_neg and not has_pos: return -1
    if has_pos and not has_neg: return 1
    return 0

def rank_facts(facts: list[dict]) -> tuple[list[dict], list[str]]:
    """Apply ACE ranking: score, deduplicate, detect conflicts.
    Returns (ranked_facts, conflict_keys)."""

    for f in facts:
        days = (datetime.utcnow() - datetime.fromisoformat(f["timestamp"])).days
        f["recency"] = recency_weight(days)
        f["combined_score"] = f["similarity"] * f["recency"]
        f["key"] = normalize_key(f["text"])
        f["polarity"] = polarity_score(f["text"])

    # Filter below threshold
    facts = [f for f in facts if f["combined_score"] >= FACT_SCORE_THRESHOLD]

    # Group by key, detect conflicts
    groups = {}
    conflicts = []
    for f in facts:
        groups.setdefault(f["key"], []).append(f)

    winners = []
    for key, group in groups.items():
        polarities = {f["polarity"] for f in group}
        if 1 in polarities and -1 in polarities:
            conflicts.append(key)
            winner = max(group, key=lambda f: f["recency"])
        else:
            winner = max(group, key=lambda f: f["combined_score"])
        winners.append(winner)

    winners.sort(key=lambda f: f["combined_score"], reverse=True)
    return winners[:FACT_LIMIT], conflicts
```

**Steps:**

1. Add OpenSearch to docker-compose (use opensearchproject/opensearch:2 for local dev)
2. Write shared/opensearch.py with init_collections, search, upsert, get_by_id
3. Write scripts/setup_opensearch.py to create 4 indexes: customer-facts, behavior-embeddings, session-summaries, product-catalog
4. Write scripts/seed_products.py to seed DynamoDB product_catalog and sync product-catalog vector docs
5. Write shared/ace_ranking.py (above)
6. Write tests for ACE ranking with mock facts (test conflict detection, recency, polarity)
7. Wire analyzer_tool.py to real OpenSearch upserts
8. Wire recommender_tool.py to search customer facts, behavior events, and product-catalog, then hydrate product details from DynamoDB
9. Store every completed recommendation in the recommendations table
10. Test full flow: ingest event -> facts stored -> products retrieved -> multiple ranked recommendations returned

**Test checkpoint:**

```bash
# Test ACE ranking in isolation:
python -c "
from shared.ace_ranking import rank_facts
facts = [
    {'text':'loves Nike shoes','similarity':0.85,'timestamp':'2025-01-01T00:00:00'},
    {'text':'does not like Nike anymore','similarity':0.80,'timestamp':'2026-04-15T00:00:00'},
    {'text':'prefers trail running','similarity':0.90,'timestamp':'2026-04-20T00:00:00'},
]
ranked, conflicts = rank_facts(facts)
print(f'Top facts: {[f[\"text\"] for f in ranked]}')
print(f'Conflicts: {conflicts}')
"
# → Top facts: ['prefers trail running', 'does not like Nike anymore']
# → Conflicts: ['nike shoes']

# Test full ingest → retrieve:
curl -X POST http://localhost:8000/events \
  -d '{"customer_id":"cust_1","event_type":"purchase","payload":{"product":"trail shoes","price":129}}'
# Wait for processing, then:
curl "http://localhost:8000/recommend?customer_id=cust_1&context=looking+for+outdoor+gear"
```

**Duration:** 4–6 hours

---

## Phase 8 — Server API endpoints (business logic)

**Goal:** All REST endpoints working. Server handles auth, validation, rate limiting. Recommendation endpoint returns real personalized offers.

**Endpoints to build:**

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | /health | Liveness check | No |
| POST | /events | Ingest behavior event | API key |
| GET | /recommend | Generate ranked personalized recommendations for a customer/context | API key |
| GET | /recommendations | List recommendation history, optionally filtered by customer_id | API key |
| GET | /recommendations/{recommendation_id} | Get one stored recommendation result | API key |
| POST | /consent | Create/update consent | API key |
| GET | /consent/{customer_id} | Get consent status | API key |
| DELETE | /customer/{customer_id} | Right-to-delete (GDPR) | API key |
| GET | /jobs/{job_id} | Get job status | API key |
| GET | /traces/{job_id} | Get agent traces | API key |
| GET | /catalog/products/{slug}/reviews | Paginated product reviews (PDP) | API key / session |
| POST | /catalog/products/{slug}/reviews | Submit shopper review (rating + text) | Auth |
| PUT | /catalog/products/{slug}/reviews/{id}/helpful | Mark review helpful or not helpful | Auth |

Also wire `POST /events` ingestion for review telemetry (`product_reviews_viewed`, `product_reviews_page_loaded`, `product_review_submitted`, `product_review_engagement`) so workers can treat UGC engagement like other behavioral signals. See `apps/web/API_REQUIREMENTS.md` for full contract text.

**Frontend tracking SDK alignment (new requirement):**

- Add/maintain a lightweight frontend event SDK module to standardize event dispatch (typed API, consent gates, retries/batching, shared context enrichment) instead of feature-by-feature manual emitters.
- SDK should attach contextual metadata where policy allows:
  - device type / OS / browser / user agent
  - local time context (timezone, hour-of-day, day-of-week)
  - traffic source/referrer/UTM attribution
  - coarse IP-derived geo context
  - optional weather context
  - engagement context (scroll depth on listing/search/PDP, viewport)
- Ensure event schema supports purchase, return history, search query, and scroll depth so ranking and recommendations can leverage both intent and outcome signals.

**Files to create/modify:**

- server/src/routes/events.py — POST /events
- server/src/routes/recommend.py - GET /recommend, GET /recommendations, GET /recommendations/{recommendation_id}
- server/src/routes/consent.py — CRUD for consent
- server/src/routes/customer.py — DELETE for right-to-delete
- server/src/routes/jobs.py — Job status lookup
- server/src/routes/traces.py — Trace viewer (reads from S3)
- server/src/middleware/auth.py — API key validation
- server/src/middleware/rate_limit.py — Rate limiting with Redis

**Recommendation flow (GET /recommend):**

```python
@router.get("/recommend")
async def recommend(customer_id: str, context: str, limit: int = 5):
    # 1. Check Redis cache
    cached = redis.get(f"recommendations:{customer_id}:{hash(context)}:{limit}")
    if cached:
        return json.loads(cached)

    # 2. Cache miss — enqueue recommendation job
    job = Job(job_type="generate_recommendation",
              payload={"customer_id": customer_id, "context": context, "limit": limit})
    dynamo.put_job(job)
    redis.lpush("jobs:pending", job.model_dump_json())

    # 3. Wait for result (poll DynamoDB or use Redis pub/sub)
    result = await wait_for_job(job.job_id, timeout=30)

    # 4. Store recommendation history, cache, and return
    dynamo.put_recommendation(result)
    redis.setex(f"recommendations:{customer_id}:{hash(context)}:{limit}", 300, json.dumps(result))
    return result
```

**Expected recommendation response shape:**

```json
{
  "recommendation_id": "...",
  "customer_id": "cust_1",
  "context": "looking for shoes",
  "items": [
    {
      "rank": 1,
      "product_id": "sku_123",
      "name": "Salomon X Ultra 4 GTX",
      "offer": "10% trail bundle discount",
      "score": 0.91,
      "reason": "Matches waterproof hiking intent and recent trail activity"
    }
  ],
  "why": ["Customer searched for waterproof hiking boots"],
  "avoided": ["Nike-heavy offers avoided due to recent returns"],
  "confidence": 0.87,
  "debug": {"job_id": "..."}
}
```

`GET /recommend` should return multiple ranked items by default, not one recommendation. Use `limit=3` or `limit=5` for the demo.

**Recommendation history routes:**

```python
@router.get("/recommendations")
async def list_recommendations(customer_id: str | None = None, limit: int = 20):
    return dynamo.list_recommendations(customer_id=customer_id, limit=limit)

@router.get("/recommendations/{recommendation_id}")
async def get_recommendation(recommendation_id: str):
    return dynamo.get_recommendation(recommendation_id)
```

**Steps:**

1. Write auth middleware (API key from header)
2. Write rate limit middleware (Redis-based)
3. Implement all endpoints
4. Write tests for each endpoint
5. Add recommendation history writes and reads
6. Test full flow: create consent -> ingest events -> get multiple ranked recommendations -> list saved recommendations

**Test checkpoint:**

```bash
# Create consent
curl -X POST http://localhost:8000/consent \
  -H "X-API-Key: test-key" \
  -d '{"customer_id":"cust_1","scopes":["personalization","analytics"]}'

# Ingest events
for i in 1 2 3; do
  curl -X POST http://localhost:8000/events \
    -H "X-API-Key: test-key" \
    -d "{\"customer_id\":\"cust_1\",\"event_type\":\"page_view\",\"payload\":{\"page\":\"/shoes/$i\"}}"
done

# Get recommendation
curl "http://localhost:8000/recommend?customer_id=cust_1&context=looking+for+shoes&limit=5" \
  -H "X-API-Key: test-key"
# -> {"items": [{"rank": 1, "product_id": "...", "offer": "..."}], "confidence": 0.87, ...}

# List saved recommendations
curl "http://localhost:8000/recommendations?customer_id=cust_1&limit=20" \
  -H "X-API-Key: test-key"
```

**Duration:** 4–6 hours

---

## Phase 9 — SQLite trace sync to S3

**Goal:** Agent traces from SQLite are synced to S3 on a schedule. Server can read trace files from S3 for observability.

**What to build:**

- worker/src/s3_sync.py — Syncs SQLite file to S3 bucket
- worker/src/trace_logger.py — Add S3 sync trigger after every N traces or on job completion
- server/src/routes/traces.py — Fetch trace file from S3, query it, return results

**s3_sync.py:**

```python
import boto3
import os
from datetime import datetime

class S3TraceSync:
    def __init__(self, bucket: str, prefix: str = "traces/"):
        self.s3 = boto3.client("s3")
        self.bucket = bucket
        self.prefix = prefix

    def sync(self, db_path: str = "/tmp/agent_traces.db"):
        if not os.path.exists(db_path):
            return

        key = f"{self.prefix}{datetime.utcnow().strftime('%Y/%m/%d')}/traces_{int(datetime.utcnow().timestamp())}.db"
        self.s3.upload_file(db_path, self.bucket, key)
        return key

    def download(self, s3_key: str, local_path: str = "/tmp/downloaded_traces.db"):
        self.s3.download_file(self.bucket, s3_key, local_path)
        return local_path

    def list_traces(self, date: str = None):
        prefix = self.prefix
        if date:
            prefix += f"{date}/"
        response = self.s3.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
        return [obj["Key"] for obj in response.get("Contents", [])]
```

**Sync strategy:**

- After each job completes, sync the SQLite file to S3
- S3 key format: `traces/2026/05/01/traces_{timestamp}.db`
- Worker rotates SQLite file: after sync, create a new empty one
- Server GET /traces/{job_id} downloads the relevant DB from S3, queries it, returns JSON

**Steps:**

1. Create S3 bucket (or use LocalStack for local dev)
2. Write s3_sync.py
3. Modify trace_logger.py to call sync after job completion
4. Modify server traces route to download from S3 and query
5. Test: process event → verify traces synced to S3 → query via API

**Test checkpoint:**

```bash
# Process an event
curl -X POST http://localhost:8000/events \
  -H "X-API-Key: test-key" \
  -d '{"customer_id":"cust_1","event_type":"purchase","payload":{"product":"boots"}}'

# Wait for processing, then check traces
curl "http://localhost:8000/traces/JOB_ID_HERE" -H "X-API-Key: test-key"
# → [{"step":"privacy_check","duration_ms":45,"status":"ok"}, ...]

# Verify in S3
aws s3 ls s3://hyperpersona-traces/traces/2026/05/01/
```

**Duration:** 2–3 hours

---

## Phase 10 — AgentCore deployment

**Goal:** Deploy the supervisor agent to AgentCore Runtime. Worker invokes it remotely instead of running the agent in-process.

**What to build:**

- agentcore/
  - Dockerfile — Container image for the supervisor agent
  - agent_handler.py — AgentCore-compatible request handler
  - deploy.sh — AgentCore CLI deployment script
- worker/src/agentcore_client.py — boto3 client to invoke AgentCore Runtime

**agent_handler.py (runs inside AgentCore microVM):**

```python
from strands import Agent
from strands.models import BedrockModel
from tools.privacy_tool import check_privacy
from tools.analyzer_tool import analyze_behavior
from tools.recommender_tool import generate_recommendation
from tools.verifier_tool import verify_recommendation
from trace_logger import TraceLogger

model = BedrockModel(model_id="anthropic.claude-sonnet-4-20250514-v1:0")

supervisor = Agent(
    model=model,
    system_prompt="...",
    tools=[check_privacy, analyze_behavior, generate_recommendation, verify_recommendation]
)

tracer = TraceLogger("/tmp/agent_traces.db")

def handler(request):
    job_id = request.get("job_id")
    event = request.get("event")

    # Run supervisor agent
    result = supervisor(f"Process event: {json.dumps(event)}")

    # Sync traces to S3
    s3_sync.sync("/tmp/agent_traces.db")

    return {"result": str(result), "job_id": job_id}
```

**worker/src/agentcore_client.py:**

```python
import boto3
import json

class AgentCoreClient:
    def __init__(self, agent_arn: str, region: str = "us-east-1"):
        self.client = boto3.client("bedrock-agentcore", region_name=region)
        self.agent_arn = agent_arn

    def invoke(self, job_id: str, event: dict, session_id: str = None) -> dict:
        response = self.client.invoke_agent_runtime(
            agentRuntimeArn=self.agent_arn,
            runtimeSessionId=session_id or job_id,
            payload=json.dumps({"job_id": job_id, "event": event})
        )
        return json.loads(response["output"]["payload"])
```

**Updated worker flow:**

```
Before:  Worker → runs supervisor agent in-process
After:   Worker → calls AgentCore Runtime → supervisor runs in microVM → returns result
```

**Steps:**

1. Write agent_handler.py and Dockerfile for AgentCore
2. Deploy with AgentCore CLI: `agentcore init`, `agentcore deploy`
3. Note the agent ARN
4. Write agentcore_client.py in worker
5. Modify process_event handler to use agentcore_client instead of local supervisor
6. Test: same curl command, but now the agent runs in a Firecracker microVM
7. Verify traces in S3

**Test checkpoint:**

```bash
# Deploy to AgentCore
cd agentcore && agentcore deploy

# Test via worker (same API as before)
curl -X POST http://localhost:8000/events \
  -H "X-API-Key: test-key" \
  -d '{"customer_id":"cust_1","event_type":"purchase","payload":{"product":"jacket"}}'

# Verify traces came from AgentCore (check S3)
aws s3 ls s3://hyperpersona-traces/traces/
```

**Duration:** 3–4 hours

---

## Phase 11 — Privacy and consent enforcement

**Goal:** Full privacy pipeline working. PII detection, consent gating, right-to-delete, data retention TTL.

**What to build/verify:**

- Consent gate: events rejected if no consent (test with opted-out customer)
- PII redaction: names, emails, phones stripped before embedding
- Right-to-delete API: DELETE /customer/{id} wipes DynamoDB + OpenSearch + Redis
- TTL on DynamoDB events (auto-expiry)

**Right-to-delete implementation:**

```python
@router.delete("/customer/{customer_id}")
async def delete_customer(customer_id: str):
    # 1. Delete all events from DynamoDB
    events = dynamo.query_events(customer_id)
    for event in events:
        dynamo.delete_item("customer_events", event["PK"], event["SK"])

    # 2. Delete consent record
    dynamo.delete_item("customer_consent", f"CUSTOMER#{customer_id}", "CONSENT")

    # 3. Delete from OpenSearch (all 3 collections)
    for collection in ["customer-facts", "behavior-embeddings", "session-summaries"]:
        opensearch.delete_by_customer(collection, customer_id)

    # 4. Delete from Redis
    redis.delete(f"session:{customer_id}")
    redis.delete(f"offer:{customer_id}:*")
    redis.delete(f"profile:{customer_id}:hot")

    return {"deleted": True, "customer_id": customer_id}
```

**Test checkpoint:**

```bash
# Test consent rejection
curl -X POST http://localhost:8000/events \
  -d '{"customer_id":"no_consent_user","event_type":"page_view","payload":{}}'
# Worker logs: "consent check failed, skipping"

# Test PII redaction
curl -X POST http://localhost:8000/events \
  -d '{"customer_id":"cust_1","event_type":"note","payload":{"text":"Call John at john@gmail.com"}}'
# Check OpenSearch: stored text should be "Call [REDACTED] at [REDACTED]"

# Test right-to-delete
curl -X DELETE "http://localhost:8000/customer/cust_1" -H "X-API-Key: test-key"
# Verify: DynamoDB empty, OpenSearch empty, Redis empty for this customer
```

**Duration:** 2–3 hours

---

## Phase 12 — End-to-end integration test and hardening

**Goal:** Full pipeline tested with realistic data. Error handling, retries, logging all working. Ready for demo.

**What to test:**

1. Happy path: consent → ingest 10 events → get recommendation → verify it's personalized
2. Conflict detection: ingest contradictory preferences, verify recommendation handles it
3. Privacy path: no-consent customer gets rejected, PII gets redacted
4. Failure path: Bedrock times out → job retries → eventually fails → status = "failed"
5. Cache path: same recommendation request twice → second is from cache (fast)
6. Delete path: right-to-delete wipes everything
7. Trace path: all agent steps visible in S3 traces

**Integration test script:**

```python
# test_e2e.py
import requests
import time

BASE = "http://localhost:8000"
KEY = {"X-API-Key": "test-key"}

# 1. Create consent
requests.post(f"{BASE}/consent", headers=KEY,
    json={"customer_id": "demo_user", "scopes": ["personalization"]})

# 2. Ingest diverse events
events = [
    {"event_type": "search", "payload": {"query": "waterproof hiking boots"}},
    {"event_type": "page_view", "payload": {"page": "/boots/salomon-x-ultra"}},
    {"event_type": "add_to_cart", "payload": {"product": "Salomon X Ultra", "price": 159}},
    {"event_type": "page_view", "payload": {"page": "/boots/merrell-moab"}},
    {"event_type": "purchase", "payload": {"product": "Salomon X Ultra", "price": 159}},
    {"event_type": "search", "payload": {"query": "trail running socks"}},
]

for e in events:
    r = requests.post(f"{BASE}/events", headers=KEY,
        json={"customer_id": "demo_user", **e})
    print(f"Event: {r.json()['event_id']} → {r.status_code}")
    time.sleep(2)  # Let worker process

# 3. Wait for all processing
time.sleep(10)

# 4. Get recommendation
r = requests.get(f"{BASE}/recommend", headers=KEY,
    params={"customer_id": "demo_user", "context": "going on a hiking trip"})
print(f"\nRecommendation: {r.json()}")

# 5. Get recommendation again (should be cached)
start = time.time()
r = requests.get(f"{BASE}/recommend", headers=KEY,
    params={"customer_id": "demo_user", "context": "going on a hiking trip"})
print(f"Cached response in {(time.time()-start)*1000:.0f}ms")

# 6. Check traces
jobs = r.json().get("debug", {}).get("job_id")
if jobs:
    r = requests.get(f"{BASE}/traces/{jobs}", headers=KEY)
    print(f"\nTraces: {len(r.json())} steps")
```

**Hardening checklist:**

- [ ] All errors return proper HTTP status codes (400, 401, 404, 500)
- [ ] Worker retries failed jobs 3 times with exponential backoff
- [ ] Bedrock calls have timeout (30s) and retry logic
- [ ] OpenSearch calls have timeout (10s)
- [ ] Redis connection handles disconnects gracefully
- [ ] All API endpoints have input validation via Pydantic
- [ ] Rate limiting works (test: send 100 requests rapidly)
- [ ] Logs are structured JSON (timestamp, level, message, context)
- [ ] Docker health checks on both containers

**Duration:** 3–4 hours

---

## Summary timeline

| Phase | What | Duration | Cumulative |
|-------|------|----------|------------|
| 1 | Project scaffold, Docker, local dev | 1–2h | 2h |
| 2 | Data model, DynamoDB, Pydantic | 2–3h | 5h |
| 3 | Worker job loop, queue | 2–3h | 8h |
| 4 | Bedrock connection, basic agent | 1–2h | 10h |
| 5 | Four sub-agent tools | 4–6h | 16h |
| 6 | Supervisor agent, trace logging | 3–4h | 20h |
| 7 | OpenSearch vector memory, ACE ranking | 4–6h | 26h |
| 8 | Server API endpoints | 4–6h | 32h |
| 9 | SQLite trace sync to S3 | 2–3h | 35h |
| 10 | AgentCore deployment | 3–4h | 39h |
| 11 | Privacy and consent | 2–3h | 42h |
| 12 | E2E testing and hardening | 3–4h | 46h |

**Total: ~46 hours of focused work**

For a hackathon, prioritize Phases 1–6 first (the core pipeline working end-to-end, 20 hours). That gives you a demoable product. Phases 7–8 add the full memory and API layer. Phases 9–12 add polish, observability, and the AgentCore sandbox deployment.
