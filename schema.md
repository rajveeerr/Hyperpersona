#DB SCHEMA


Going table-by-table, column-by-column. The non-obvious bits get more space; the obvious ones (every `customer_id` is a customer ID) get one line.

---

# DynamoDB tables

These are durable, structured records — the books of record.

## `customer_events`

**Purpose:** every behavior signal we receive about a customer. One row per event.

| Column | What it holds | Why it exists |
| --- | --- | --- |
| `PK` | A string like `CUSTOMER#cust_42`. The partition key in DynamoDB. | DynamoDB shards data by partition key. Putting all of one customer's events in the same partition means "fetch all events for cust_42" is a single fast query. |
| `SK` | A string like `EVENT#2026-05-01T12:30:45Z#a3b1...`. The sort key. | Sort key is `EVENT#{timestamp}#{event_id}`. This means events for one customer are automatically stored in chronological order, and we can query "events between time X and Y" cheaply. |
| `customer_id` | `"cust_42"` — bare ID without the `CUSTOMER#` prefix. | Stored as its own column too because GSIs and filters work on attributes, not on parsed PKs. |
| `event_id` | A UUID like `"a3b1-..."`. | Globally unique handle for one event. Used by the worker to update *just this event*, by the recommender as a `source_event` reference, etc. |
| `event_type` | One of `page_view`, `add_to_cart`, `purchase`, `return`, `search`. | Categorical classifier. The agent uses it to decide what kind of facts to extract (a `purchase` is a stronger preference signal than a `page_view`). |
| `payload` | A JSON blob. e.g. `{"product":"Salomon X Ultra","price":159}` or `{"page":"/shoes"}`. | Free-form details specific to this `event_type`. Schema-less because each event type has different fields. |
| `status` | One of `pending`, `processing`, `processed`, `failed`. | Lifecycle: server writes `pending` → worker flips to `processing` while running → `processed` (success) or `failed` (error). Lets us know which events still need attention. |
| `consent_scope` | A set of strings like `{"personalization", "analytics"}`. May be empty. | Snapshot of consent at ingestion time. Even if the customer later revokes, this row remembers what was permitted *when we took it in*. Important for audits. |
| `created_at` | ISO-8601 timestamp string, UTC. | Used in the SK and as the GSI sort key. Strings (not numbers) because ISO-8601 sorts lexicographically the same as chronologically. |

**GSI `status-index`** (status, created_at): a secondary view over the same data. Lets you ask "give me everything still `pending`, oldest first" without scanning the whole table.

---

## `customer_consent`

**Purpose:** what the customer has agreed to. One row per customer. Tiny but central — every other action checks this first.

| Column | What it holds | Why it exists |
| --- | --- | --- |
| `PK` | `CUSTOMER#cust_42`. | Same partition layout as events so a customer's consent and events live together. Future-proof: if you ever switch to single-table design, the keys already line up. |
| `SK` | The literal string `CONSENT`. | DynamoDB requires a sort key on this table. We use a fixed value because there's exactly one consent record per customer. |
| `customer_id` | `"cust_42"`. |  |
| `scopes` | A set: `{"personalization"}` or `{"personalization","analytics","marketing"}`. | Each scope unlocks a category of behavior. `personalization` is required to run the agent. `marketing` is required to use the customer's data in outbound campaigns. |
| `data_retention_days` | Integer, default 90. | How long we're allowed to keep this customer's events. Powers DynamoDB TTL — events older than this are auto-expired by AWS. |
| `last_updated` | ISO timestamp. | When consent last changed. Useful if you have to prove "we got fresh consent on 2026-04-15". |

---

## `jobs`

**Purpose:** bookkeeping for every async unit of work. Whenever the server enqueues something, a job row gets written. This is how we know whether async work succeeded.

| Column | What it holds | Why it exists |
| --- | --- | --- |
| `PK` | `JOB#a7f2-...`. | Each job has a unique partition. (Jobs aren't grouped by customer because lookups are always by `job_id`.) |
| `SK` | The literal string `META`. | Same reason as consent — fixed because one row per `job_id`. |
| `job_id` | UUID. | The handle returned by `POST /events`. The caller can use it later to query status. |
| `job_type` | `process_event`, `generate_recommendation`, or `batch_import`. | Tells the worker which handler to dispatch to. Acts like a tagged union. |
| `payload` | JSON. For `process_event`: `{"event_id":"...","customer_id":"...","created_at":"..."}`. | Whatever the handler needs to do its job. Stays small — we don't put the whole event payload here, just enough to look it up. |
| `status` | `queued`, `running`, `completed`, `failed`. | Lifecycle parallel to event status but for the job itself. A single event can spawn multiple jobs (process, then later recommend). |
| `created_at` | ISO timestamp. | When the server enqueued it. |
| `completed_at` | ISO timestamp, nullable. | Set when the worker finishes. `completed_at - created_at` gives end-to-end latency, useful for dashboards. |
| `error` | Free-form text, nullable. | If a job fails, the worker writes the error message here. Lets you debug without needing logs. |

**GSI `status-index`**: same idea — find all `failed` jobs in the last hour, all `queued` jobs that have been waiting too long, etc.

---

# OpenSearch collections (Phase 7)

Three vector indexes. All three have the same shape (id + customer_id + text + 1024-dim vector + timestamp), but they play different roles on the time axis.

## `customer_facts` (long-term memory)

**Purpose:** distilled, atomic statements about a customer that survive across sessions.

| Column | What it holds | Why it exists |
| --- | --- | --- |
| `id` | UUID per fact. | Primary key in OpenSearch. |
| `customer_id` | The owner of the fact. | Used as a filter at query time so we only retrieve this customer's facts. |
| `text` | A short declarative sentence: `"prefers trail running"`, `"sensitive to >₹16,600"`. | Human-readable. Also fed into the recommender prompt. |
| `vector` | 1024 floats — the Titan embedding of the text. | Enables semantic search: "give me facts similar to *outdoor adventure preferences*" without keyword matching. |
| `source_event` | The `event_id` this fact was extracted from. | Audit trail. If a recommendation cites a fact, we can trace it back to the originating event. |
| `timestamp` | When the fact was extracted (not when the event happened — those can differ). | Used by ACE ranking: a fact from yesterday weighs more than one from a year ago. |
| `polarity` | `+1` (positive), `0` (neutral), `-1` (negative). | Signed sentiment about the topic. Critical for conflict detection: if there's a `+1 "loves Nike"` from 2024 and a `-1 "doesn't like Nike anymore"` from 2026, ACE flags the conflict and prefers the recent one. |

## `behavior_embeddings` (mid-term memory)

**Purpose:** the events themselves, embedded. Lower abstraction than facts.

| Column | What it holds | Why it exists |
| --- | --- | --- |
| `id` | The same UUID as the `event_id` in DynamoDB. | Lets us cross-reference: given a fact's `source_event`, look up the actual event in DynamoDB *and* the embedding here. |
| `customer_id` | Owner. |  |
| `text` | A redacted, human-readable description of the event. | E.g. `"viewed page /boots/salomon"`. PII is stripped (no names, emails) so embeddings can't leak personal data. |
| `vector` | 1024 floats. | Enables: "find sessions similar to this one" or "find events related to this query." |
| `timestamp` | When the event happened. | Recency weighting at retrieval. |

## `session_summaries` (short-term memory)

**Purpose:** rolled-up summaries of recent activity. Bridges Redis hot state and the long-term tier.

| Column | What it holds | Why it exists |
| --- | --- | --- |
| `id` | UUID per summary. |  |
| `customer_id` | Owner. |  |
| `text` | `"Browsed hiking boots, added Salomon to cart, searched for socks"`. | Compressed view of a session. |
| `vector` | 1024 floats. | Same retrieval mechanism as the other two collections. |
| `timestamp` | End-of-session time. | Recency. |

---

# Redis (ephemeral hot state)

Redis isn't a real "table" — it's a key-value store. The DBML representation is symbolic. Each row in the diagram represents one *category* of key.

## `redis_jobs_pending`

**Purpose:** the actual mailbox between server and worker.

| Column | What it holds | Why it exists |
| --- | --- | --- |
| `key` | The literal string `jobs:pending`. | Just one key, holds a Redis **list**. |
| `value` | List of JSON-serialized Jobs. | Server `LPUSH`es onto the head, worker `BRPOP`s from the tail. FIFO. `BRPOP` blocks until something appears. |

## `redis_session`

**Purpose:** what the customer is doing **right now**.

| Column | What it holds | Why it exists |
| --- | --- | --- |
| `key` | `session:cust_42`. | One key per active customer. |
| `value` | JSON: recent pages, last search, items in cart... | Updated on every event. Available to the recommender for "what's the customer doing this minute" context. |
| `ttl_seconds` | Around 30 minutes, refreshed on each update. | If the customer goes idle, the session gets auto-deleted. Periodically the session is summarized into `session_summaries` first. |

## `redis_offer_cache`

**Purpose:** don't re-run the agent for identical recommendation requests.

| Column | What it holds | Why it exists |
| --- | --- | --- |
| `key` | `offer:cust_42:{hash("looking for outdoor gear")}`. | Keyed on customer + a hash of the context string so cache lookups are stable. |
| `value` | The full recommendation JSON returned to the caller last time. | Same request → return cached result. |
| `ttl_seconds` | 300 (5 min). | Recommendations get stale fast — too long and you serve outdated offers; too short and you waste Bedrock $$. |

## `redis_profile_hot`

**Purpose:** keep the most-read fields of the customer profile in memory.

| Column | What it holds | Why it exists |
| --- | --- | --- |
| `key` | `profile:cust_42:hot`. | Per-customer. |
| `value` | A small JSON: tier, segment, top categories, last event time. | Without this, every event ingest hits DynamoDB to read the same fields. Redis cuts that to a sub-millisecond memory read. |

---

# S3 (cold trace archive — Phase 9)

## `s3_traces`

**Purpose:** keep the audit trail of every agent decision forever, cheaply.

| Column | What it holds | Why it exists |
| --- | --- | --- |
| `key` | `traces/2026/05/01/traces_1714572045.db`. | Path layout means listing all traces from a given day is one prefix scan. The timestamp avoids overwrites if multiple jobs finish in the same second. |
| `bucket` | `hyperpersona-traces`. | The S3 bucket. One bucket for the whole project. |
| `payload` | A SQLite database file (binary). | The whole trace from one job in one file. ~10–50 KB per job. Cheap to store. |
| `uploaded_at` | When the worker uploaded it. | Lets you find recent uploads without parsing the key. |

---

# SQLite (per-job — inside AgentCore)

## `sqlite_traces`

**Purpose:** while a job runs, the supervisor agent inside the AgentCore microVM logs every step it takes to a local SQLite file. When the job completes, that file is uploaded to S3 (above) and the microVM dies.

| Column | What it holds | Why it exists |
| --- | --- | --- |
| `id` | Auto-increment integer. | Local row counter — preserves ordering within the file. |
| `job_id` | The job this trace belongs to. | Lets the server later say "give me the trace for job X" — find the right `.db` file in S3, query rows where `job_id = X`. |
| `agent_name` | `supervisor`, `privacy`, `analyzer`, `recommender`, `verifier`. | Which sub-agent took this step. |
| `step` | Free-form: `start`, `privacy_check`, `embed`, `retrieve_facts`, `generate_offer`, `verify`. | Human-readable name for the step. |
| `input` | JSON of what the step received. | For debugging: "what did the recommender see when it produced offer X?" |
| `output` | JSON of what the step returned. | Pair with `input` to reconstruct the entire reasoning chain. |
| `duration_ms` | Float milliseconds. | Profiling. Surfaces "the privacy check is taking 4 seconds — Comprehend is slow." |
| `timestamp` | When the step ran. | Ordering, latency analysis. |
| `status` | `ok`, `error`, `skipped`. | Per-step success. The agent might call privacy → ok, analyzer → ok, recommender → error. The job's overall status reflects the worst of these. |

---

# How data flows together

## `POST /events` (Phase 2 — works today)

`1. Server validates request body                                      → IngestEventRequest
2. Server creates a CustomerEvent (status=pending)                    → DynamoDB customer_events
3. Server creates a Job (status=queued)                               → DynamoDB jobs
4. Server LPUSHes the Job JSON                                        → Redis jobs:pending
5. Server returns 202 with event_id and job_id`

## Worker pickup (Phase 3 — next)

`6. Worker BRPOPs from jobs:pending                                    ← Redis jobs:pending
7. Worker marks job running                                           → DynamoDB jobs.status
8. Worker dispatches to handler based on job_type
9. Handler reads event from DynamoDB                                  ← DynamoDB customer_events
10. Handler marks event processing                                    → DynamoDB customer_events.status
11. Handler does its work (Phase 3: stub. Phase 5+: agent pipeline.)
12. Handler marks event processed and job completed                   → DynamoDB`

## Inside the agent pipeline (Phase 5–7)

`13. supervisor.privacy_check
    - reads customer_consent                                          ← DynamoDB customer_consent
    - calls Comprehend for PII redaction
14. supervisor.analyze_behavior
    - embeds the (redacted) event text                                ← Bedrock Titan
    - extracts atomic facts via Claude                                ← Bedrock Claude
    - upserts each fact (with vector + polarity)                      → OpenSearch customer_facts
    - upserts the event embedding                                     → OpenSearch behavior_embeddings
15. supervisor.generate_recommendation (only on /recommend)
    - embeds the query context                                         ← Bedrock Titan
    - searches all 3 OpenSearch collections in parallel
    - reads Redis session                                              ← Redis session:{id}
    - applies ACE ranking (recency × similarity, conflict detection)
    - generates offer text                                             ← Bedrock Claude
16. supervisor.verify_recommendation
    - chain-of-verification: fact-checks the draft offer              ← Bedrock Claude
    - returns either VALID or a corrected version
17. Throughout: every step is logged                                  → SQLite sqlite_traces (in microVM)
18. On job completion: SQLite file uploaded                           → S3 s3_traces`

## `GET /recommend` (Phase 8)

`19. Server checks the cache                                           ← Redis offer:{id}:{hash}
20. Cache hit → return immediately
21. Cache miss → enqueue generate_recommendation job, wait for result
22. Cache the result for 5 minutes                                    → Redis offer:{id}:{hash}
23. Return to caller`

Going table-by-table, column-by-column. The non-obvious bits get more space; the obvious ones (every `customer_id` is a customer ID) get one line.

---

# DynamoDB tables

These are durable, structured records — the books of record.

## `customer_events`

**Purpose:** every behavior signal we receive about a customer. One row per event.

| Column | What it holds | Why it exists |
| --- | --- | --- |
| `PK` | A string like `CUSTOMER#cust_42`. The partition key in DynamoDB. | DynamoDB shards data by partition key. Putting all of one customer's events in the same partition means "fetch all events for cust_42" is a single fast query. |
| `SK` | A string like `EVENT#2026-05-01T12:30:45Z#a3b1...`. The sort key. | Sort key is `EVENT#{timestamp}#{event_id}`. This means events for one customer are automatically stored in chronological order, and we can query "events between time X and Y" cheaply. |
| `customer_id` | `"cust_42"` — bare ID without the `CUSTOMER#` prefix. | Stored as its own column too because GSIs and filters work on attributes, not on parsed PKs. |
| `event_id` | A UUID like `"a3b1-..."`. | Globally unique handle for one event. Used by the worker to update *just this event*, by the recommender as a `source_event` reference, etc. |
| `event_type` | One of `page_view`, `add_to_cart`, `purchase`, `return`, `search`. | Categorical classifier. The agent uses it to decide what kind of facts to extract (a `purchase` is a stronger preference signal than a `page_view`). |
| `payload` | A JSON blob. e.g. `{"product":"Salomon X Ultra","price":159}` or `{"page":"/shoes"}`. | Free-form details specific to this `event_type`. Schema-less because each event type has different fields. |
| `status` | One of `pending`, `processing`, `processed`, `failed`. | Lifecycle: server writes `pending` → worker flips to `processing` while running → `processed` (success) or `failed` (error). Lets us know which events still need attention. |
| `consent_scope` | A set of strings like `{"personalization", "analytics"}`. May be empty. | Snapshot of consent at ingestion time. Even if the customer later revokes, this row remembers what was permitted *when we took it in*. Important for audits. |
| `created_at` | ISO-8601 timestamp string, UTC. | Used in the SK and as the GSI sort key. Strings (not numbers) because ISO-8601 sorts lexicographically the same as chronologically. |

**GSI `status-index`** (status, created_at): a secondary view over the same data. Lets you ask "give me everything still `pending`, oldest first" without scanning the whole table.

---

## `customer_consent`

**Purpose:** what the customer has agreed to. One row per customer. Tiny but central — every other action checks this first.

| Column | What it holds | Why it exists |
| --- | --- | --- |
| `PK` | `CUSTOMER#cust_42`. | Same partition layout as events so a customer's consent and events live together. Future-proof: if you ever switch to single-table design, the keys already line up. |
| `SK` | The literal string `CONSENT`. | DynamoDB requires a sort key on this table. We use a fixed value because there's exactly one consent record per customer. |
| `customer_id` | `"cust_42"`. |  |
| `scopes` | A set: `{"personalization"}` or `{"personalization","analytics","marketing"}`. | Each scope unlocks a category of behavior. `personalization` is required to run the agent. `marketing` is required to use the customer's data in outbound campaigns. |
| `data_retention_days` | Integer, default 90. | How long we're allowed to keep this customer's events. Powers DynamoDB TTL — events older than this are auto-expired by AWS. |
| `last_updated` | ISO timestamp. | When consent last changed. Useful if you have to prove "we got fresh consent on 2026-04-15". |

---

## `jobs`

**Purpose:** bookkeeping for every async unit of work. Whenever the server enqueues something, a job row gets written. This is how we know whether async work succeeded.

| Column | What it holds | Why it exists |
| --- | --- | --- |
| `PK` | `JOB#a7f2-...`. | Each job has a unique partition. (Jobs aren't grouped by customer because lookups are always by `job_id`.) |
| `SK` | The literal string `META`. | Same reason as consent — fixed because one row per `job_id`. |
| `job_id` | UUID. | The handle returned by `POST /events`. The caller can use it later to query status. |
| `job_type` | `process_event`, `generate_recommendation`, or `batch_import`. | Tells the worker which handler to dispatch to. Acts like a tagged union. |
| `payload` | JSON. For `process_event`: `{"event_id":"...","customer_id":"...","created_at":"..."}`. | Whatever the handler needs to do its job. Stays small — we don't put the whole event payload here, just enough to look it up. |
| `status` | `queued`, `running`, `completed`, `failed`. | Lifecycle parallel to event status but for the job itself. A single event can spawn multiple jobs (process, then later recommend). |
| `created_at` | ISO timestamp. | When the server enqueued it. |
| `completed_at` | ISO timestamp, nullable. | Set when the worker finishes. `completed_at - created_at` gives end-to-end latency, useful for dashboards. |
| `error` | Free-form text, nullable. | If a job fails, the worker writes the error message here. Lets you debug without needing logs. |

**GSI `status-index`**: same idea — find all `failed` jobs in the last hour, all `queued` jobs that have been waiting too long, etc.

---

# OpenSearch collections (Phase 7)

Three vector indexes. All three have the same shape (id + customer_id + text + 1024-dim vector + timestamp), but they play different roles on the time axis.

## `customer_facts` (long-term memory)

**Purpose:** distilled, atomic statements about a customer that survive across sessions.

| Column | What it holds | Why it exists |
| --- | --- | --- |
| `id` | UUID per fact. | Primary key in OpenSearch. |
| `customer_id` | The owner of the fact. | Used as a filter at query time so we only retrieve this customer's facts. |
| `text` | A short declarative sentence: `"prefers trail running"`, `"sensitive to >₹16,600"`. | Human-readable. Also fed into the recommender prompt. |
| `vector` | 1024 floats — the Titan embedding of the text. | Enables semantic search: "give me facts similar to *outdoor adventure preferences*" without keyword matching. |
| `source_event` | The `event_id` this fact was extracted from. | Audit trail. If a recommendation cites a fact, we can trace it back to the originating event. |
| `timestamp` | When the fact was extracted (not when the event happened — those can differ). | Used by ACE ranking: a fact from yesterday weighs more than one from a year ago. |
| `polarity` | `+1` (positive), `0` (neutral), `-1` (negative). | Signed sentiment about the topic. Critical for conflict detection: if there's a `+1 "loves Nike"` from 2024 and a `-1 "doesn't like Nike anymore"` from 2026, ACE flags the conflict and prefers the recent one. |

## `behavior_embeddings` (mid-term memory)

**Purpose:** the events themselves, embedded. Lower abstraction than facts.

| Column | What it holds | Why it exists |
| --- | --- | --- |
| `id` | The same UUID as the `event_id` in DynamoDB. | Lets us cross-reference: given a fact's `source_event`, look up the actual event in DynamoDB *and* the embedding here. |
| `customer_id` | Owner. |  |
| `text` | A redacted, human-readable description of the event. | E.g. `"viewed page /boots/salomon"`. PII is stripped (no names, emails) so embeddings can't leak personal data. |
| `vector` | 1024 floats. | Enables: "find sessions similar to this one" or "find events related to this query." |
| `timestamp` | When the event happened. | Recency weighting at retrieval. |

## `session_summaries` (short-term memory)

**Purpose:** rolled-up summaries of recent activity. Bridges Redis hot state and the long-term tier.

| Column | What it holds | Why it exists |
| --- | --- | --- |
| `id` | UUID per summary. |  |
| `customer_id` | Owner. |  |
| `text` | `"Browsed hiking boots, added Salomon to cart, searched for socks"`. | Compressed view of a session. |
| `vector` | 1024 floats. | Same retrieval mechanism as the other two collections. |
| `timestamp` | End-of-session time. | Recency. |

---

# Redis (ephemeral hot state)

Redis isn't a real "table" — it's a key-value store. The DBML representation is symbolic. Each row in the diagram represents one *category* of key.

## `redis_jobs_pending`

**Purpose:** the actual mailbox between server and worker.

| Column | What it holds | Why it exists |
| --- | --- | --- |
| `key` | The literal string `jobs:pending`. | Just one key, holds a Redis **list**. |
| `value` | List of JSON-serialized Jobs. | Server `LPUSH`es onto the head, worker `BRPOP`s from the tail. FIFO. `BRPOP` blocks until something appears. |

## `redis_session`

**Purpose:** what the customer is doing **right now**.

| Column | What it holds | Why it exists |
| --- | --- | --- |
| `key` | `session:cust_42`. | One key per active customer. |
| `value` | JSON: recent pages, last search, items in cart... | Updated on every event. Available to the recommender for "what's the customer doing this minute" context. |
| `ttl_seconds` | Around 30 minutes, refreshed on each update. | If the customer goes idle, the session gets auto-deleted. Periodically the session is summarized into `session_summaries` first. |

## `redis_offer_cache`

**Purpose:** don't re-run the agent for identical recommendation requests.

| Column | What it holds | Why it exists |
| --- | --- | --- |
| `key` | `offer:cust_42:{hash("looking for outdoor gear")}`. | Keyed on customer + a hash of the context string so cache lookups are stable. |
| `value` | The full recommendation JSON returned to the caller last time. | Same request → return cached result. |
| `ttl_seconds` | 300 (5 min). | Recommendations get stale fast — too long and you serve outdated offers; too short and you waste Bedrock $$. |

## `redis_profile_hot`

**Purpose:** keep the most-read fields of the customer profile in memory.

| Column | What it holds | Why it exists |
| --- | --- | --- |
| `key` | `profile:cust_42:hot`. | Per-customer. |
| `value` | A small JSON: tier, segment, top categories, last event time. | Without this, every event ingest hits DynamoDB to read the same fields. Redis cuts that to a sub-millisecond memory read. |

---

# S3 (cold trace archive — Phase 9)

## `s3_traces`

**Purpose:** keep the audit trail of every agent decision forever, cheaply.

| Column | What it holds | Why it exists |
| --- | --- | --- |
| `key` | `traces/2026/05/01/traces_1714572045.db`. | Path layout means listing all traces from a given day is one prefix scan. The timestamp avoids overwrites if multiple jobs finish in the same second. |
| `bucket` | `hyperpersona-traces`. | The S3 bucket. One bucket for the whole project. |
| `payload` | A SQLite database file (binary). | The whole trace from one job in one file. ~10–50 KB per job. Cheap to store. |
| `uploaded_at` | When the worker uploaded it. | Lets you find recent uploads without parsing the key. |

---

# SQLite (per-job — inside AgentCore)

## `sqlite_traces`

**Purpose:** while a job runs, the supervisor agent inside the AgentCore microVM logs every step it takes to a local SQLite file. When the job completes, that file is uploaded to S3 (above) and the microVM dies.

| Column | What it holds | Why it exists |
| --- | --- | --- |
| `id` | Auto-increment integer. | Local row counter — preserves ordering within the file. |
| `job_id` | The job this trace belongs to. | Lets the server later say "give me the trace for job X" — find the right `.db` file in S3, query rows where `job_id = X`. |
| `agent_name` | `supervisor`, `privacy`, `analyzer`, `recommender`, `verifier`. | Which sub-agent took this step. |
| `step` | Free-form: `start`, `privacy_check`, `embed`, `retrieve_facts`, `generate_offer`, `verify`. | Human-readable name for the step. |
| `input` | JSON of what the step received. | For debugging: "what did the recommender see when it produced offer X?" |
| `output` | JSON of what the step returned. | Pair with `input` to reconstruct the entire reasoning chain. |
| `duration_ms` | Float milliseconds. | Profiling. Surfaces "the privacy check is taking 4 seconds — Comprehend is slow." |
| `timestamp` | When the step ran. | Ordering, latency analysis. |
| `status` | `ok`, `error`, `skipped`. | Per-step success. The agent might call privacy → ok, analyzer → ok, recommender → error. The job's overall status reflects the worst of these. |

---

# How data flows together

## `POST /events` (Phase 2 — works today)

`1. Server validates request body                                      → IngestEventRequest
2. Server creates a CustomerEvent (status=pending)                    → DynamoDB customer_events
3. Server creates a Job (status=queued)                               → DynamoDB jobs
4. Server LPUSHes the Job JSON                                        → Redis jobs:pending
5. Server returns 202 with event_id and job_id`

## Worker pickup (Phase 3 — next)

`6. Worker BRPOPs from jobs:pending                                    ← Redis jobs:pending
7. Worker marks job running                                           → DynamoDB jobs.status
8. Worker dispatches to handler based on job_type
9. Handler reads event from DynamoDB                                  ← DynamoDB customer_events
10. Handler marks event processing                                    → DynamoDB customer_events.status
11. Handler does its work (Phase 3: stub. Phase 5+: agent pipeline.)
12. Handler marks event processed and job completed                   → DynamoDB`

## Inside the agent pipeline (Phase 5–7)

`13. supervisor.privacy_check
    - reads customer_consent                                          ← DynamoDB customer_consent
    - calls Comprehend for PII redaction
14. supervisor.analyze_behavior
    - embeds the (redacted) event text                                ← Bedrock Titan
    - extracts atomic facts via Claude                                ← Bedrock Claude
    - upserts each fact (with vector + polarity)                      → OpenSearch customer_facts
    - upserts the event embedding                                     → OpenSearch behavior_embeddings
15. supervisor.generate_recommendation (only on /recommend)
    - embeds the query context                                         ← Bedrock Titan
    - searches all 3 OpenSearch collections in parallel
    - reads Redis session                                              ← Redis session:{id}
    - applies ACE ranking (recency × similarity, conflict detection)
    - generates offer text                                             ← Bedrock Claude
16. supervisor.verify_recommendation
    - chain-of-verification: fact-checks the draft offer              ← Bedrock Claude
    - returns either VALID or a corrected version
17. Throughout: every step is logged                                  → SQLite sqlite_traces (in microVM)
18. On job completion: SQLite file uploaded                           → S3 s3_traces`

## `GET /recommend` (Phase 8)

`19. Server checks the cache                                           ← Redis offer:{id}:{hash}
20. Cache hit → return immediately
21. Cache miss → enqueue generate_recommendation job, wait for result
22. Cache the result for 5 minutes                                    → Redis offer:{id}:{hash}
23. Return to caller`