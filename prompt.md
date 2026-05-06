# Server Architecture

This document describes the architecture, runtime behavior, and core design decisions of the `server/` package — the backend for the productivity SaaS application.

---

## 1. High-level Overview

The server is a **Node.js / TypeScript / Express** API that powers a journaling + AI-coaching product. Users submit free-form log entries, and the system builds a personal **Agentic Cognitive Architecture (ACE)** memory of the user — long-term facts, episodic logs, and a rolling daily summary — which is then used to answer the user's chat questions via Google Gemini.

The architecture is split into three planes:

| Plane               | Responsibility                                                               | Technology                       |
| ------------------- | ---------------------------------------------------------------------------- | -------------------------------- |
| **API plane**       | HTTP endpoints, auth, request validation                                     | Express + better-auth            |
| **Storage plane**   | Relational data (users/sessions/logs), vector memory, queue/cache backbone   | PostgreSQL, Qdrant, Redis        |
| **Processing plane**| Async log ingestion, embedding, fact extraction, summary updates             | BullMQ worker + Gemini AI        |

A user-submitted log triggers a **fast write path** (insert + enqueue, return 200 immediately) and a **slow processing path** (worker generates embeddings, extracts facts, updates daily summary). A user chat query triggers a **retrieval-augmented generation** path that pulls from all three Qdrant collections, applies recency / polarity / conflict heuristics, and runs a **Chain-of-Verification** pass before responding.

---

## 2. Tech Stack

### Runtime
- **Node.js + TypeScript** (`tsx watch` in dev, `tsc` build, `node dist/index.js` in prod)
- **Express 5** — HTTP server
- **Helmet** + **CORS** — security middleware

### Auth
- **better-auth** with the **drizzle adapter** — email/password, sessions, accounts, verification tables stored in Postgres

### Persistence
- **PostgreSQL 16** + **drizzle-orm** + **drizzle-kit** for migrations (`server/drizzle/*.sql`)
- **Qdrant** (vector DB, port 6333) — three collections of 3072-dim cosine vectors
- **Redis** (port 6379) — BullMQ queue backend (and intended cache layer)

### AI
- **Google Generative AI SDK** (`@google/generative-ai`)
  - Embedding model: `gemini-embedding-001` (3072 dims)
  - Chat model: `gemini-2.5-flash`
  - Fact-extraction model: `gemini-2.5-flash` configured with `responseMimeType: "application/json"`

### Background processing
- **BullMQ** queue `log-processing` with a single worker (`src/workers/log.worker.ts`)
- 3 attempts, exponential backoff starting at 1s, completed jobs removed

### Local infrastructure
- `docker-compose.yml` brings up Postgres, Redis, and Qdrant with named volumes

---

## 3. Directory Layout

```
server/
├── docker-compose.yml          # Postgres + Redis + Qdrant
├── drizzle.config.ts           # drizzle-kit config (reads DATABASE_URL)
├── drizzle/                    # Generated SQL migrations + meta snapshots
│   ├── 0000_lethal_red_ghost.sql
│   ├── 0001_square_black_crow.sql
│   └── meta/
├── package.json                # dev/build/start + db:generate / db:push
├── tsconfig.json
└── src/
    ├── index.ts                # Express app, routes, server bootstrap
    ├── config/index.ts         # Centralized env config + validateConfig()
    ├── db/
    │   ├── index.ts            # pg.Pool + drizzle(db) instance
    │   └── schema.ts           # user, session, account, verification, log_entry
    ├── lib/
    │   ├── auth.ts             # betterAuth() instance with drizzleAdapter
    │   ├── gemini.ts           # aiService: embed/chat/extract/summary/CoVe
    │   ├── qdrant.ts           # vectorService: init/search/upsert/getPoint
    │   ├── queue.ts            # BullMQ Queue + addLogJob()
    │   └── redis.ts            # IORedis connection (shared by queue + worker)
    ├── workers/
    │   └── log.worker.ts       # BullMQ Worker for "log-processing"
    ├── types/index.ts          # Domain types (LogEntry, Fact, ChatResponse, ...)
    └── utils/
        ├── errors.ts           # AppError + typed subclasses (Validation, Unauthorized, ...)
        ├── helpers.ts          # Stopwords, recency/polarity, normalizeKey, getTodayDateString
        └── logger.ts           # JSON structured logger
```

---

## 4. Data Model

### 4.1 PostgreSQL (Drizzle schema — `src/db/schema.ts`)

| Table          | Purpose                                                                  |
| -------------- | ------------------------------------------------------------------------ |
| `user`         | Identity record (id, name, email, emailVerified, image, timestamps)      |
| `session`      | Auth sessions issued by better-auth (token, expiresAt, ip, userAgent)    |
| `account`      | Linked auth providers + password (managed by better-auth)                |
| `verification` | Email/password verification tokens                                       |
| `log_entry`    | The user's submitted journal entries — the **system of record** for logs |

`log_entry.status` is a string enum tracked by the worker: `"pending" → "processed" | "failed"`.

### 4.2 Qdrant collections (`src/lib/qdrant.ts`)

All three collections use **3072-dim cosine** vectors and are filtered per `userId` on every search.

| Collection (constant)                     | Memory role        | What's stored                                                          | Point ID                                  |
| ----------------------------------------- | ------------------ | ---------------------------------------------------------------------- | ----------------------------------------- |
| `productivity_logs` (`LOGS_COLLECTION`)   | Episodic memory    | Each raw log entry, embedded                                           | `logId` (UUID v4, also Postgres PK)       |
| `user_facts` (`FACTS_COLLECTION`)         | Long-term memory   | Atomic facts extracted from a log (one point per fact)                 | UUID v4 per fact, payload links sourceLog |
| `daily_summaries` (`SUMMARIES_COLLECTION`)| Working memory     | One rolling narrative summary per user per UTC date                    | `uuidv5(userId_YYYY-MM-DD, NAMESPACE)`    |

The deterministic v5 UUID for summaries is what lets the chat endpoint fetch "today's summary" by ID without a search query.

---

## 5. Request Flow — `/api/logs` (Write Path)

```
Client ──POST /api/logs──▶ Express
                           │
                           ├─ helmet + cors + json
                           ├─ better-auth: getSession(headers)  ◀── 401 if missing
                           ├─ INSERT log_entry (status="pending") via drizzle
                           ├─ addLogJob({ logId, userId, text }) ──▶ Redis (BullMQ)
                           └─ 200 { success, id, status: "queued" }
                                                        │
                                                        ▼
                                          ┌─────────────────────────┐
                                          │ log.worker.ts (BullMQ)  │
                                          │  1. Embed(text) ──▶ Qdrant LOGS upsert
                                          │  2. extractFacts(text) ─▶ N facts
                                          │       ▶ for each: embed + upsert FACTS
                                          │  3. Get existing daily summary point
                                          │       ▶ updateDailySummary(curr, text)
                                          │       ▶ embed + upsert SUMMARIES
                                          │  4. UPDATE log_entry SET status="processed"
                                          └─────────────────────────┘
```

Key properties:
- **The HTTP request does no AI work.** Latency stays low; failures in the AI/vector path can't fail the write.
- **Failure isolation.** The worker `try/catch` flips the row to `status="failed"` then rethrows so BullMQ records it. Retry is 3× exponential.
- **Determinism for summaries.** Re-running the same `(userId, date)` always targets the same point ID, so multiple logs in one day *update* (not duplicate) the summary.

---

## 6. Request Flow — `/api/chat` (Read / RAG Path)

This is the heart of the cognitive architecture. The endpoint is implemented in `src/index.ts` and uses the helpers extracted into `src/utils/helpers.ts`.

### 6.1 Retrieval (parallel)

```
1. embed(message) ──▶ vector
2. Promise.all:
   a) qdrant.search(FACTS_COLLECTION,    vector, 5, userId)   ── long-term
   b) qdrant.search(LOGS_COLLECTION,     vector, 5, userId)   ── episodic
   c) qdrant.getPoint(SUMMARIES_COLLECTION, uuidv5(userId_today)) ── working
```

### 6.2 Ranking and de-duplication of facts ("ACE Layer")

For each retrieved fact, build a `FactEntry` with:
- `similarity` — Qdrant score
- `recency` — `0.5 ^ (ageDays / FACT_HALF_LIFE_DAYS)` (default half-life 45 days)
- `combinedScore = similarity * recency`
- `key` — `normalizeKey(text)` — first 4 non-stopword/non-negation tokens, lowercased
- `polarity` — `+1 / 0 / -1` from POSITIVE/NEGATION token presence

Then:
1. Drop facts below `FACT_SCORE_THRESHOLD` (default `0.12`).
2. Group by `key`; when two facts share a key:
   - If their polarities are **opposite**, record a conflict and prefer the **more recent** entry.
   - Otherwise prefer the higher `combinedScore`.
3. Sort surviving facts by `combinedScore` DESC, take top `FACT_LIMIT` (default 6).

The conflict list is surfaced into the prompt so the LLM doesn't gaslight the user with stale preferences.

### 6.3 Prompt assembly + Chain-of-Verification

Two prompts are constructed:
- `systemPrompt` — instructs Gemini as a Productivity Coach and includes the three context blocks (USER PROFILE, CURRENT STATUS, RELEVANT HISTORY) plus any conflicts.
- `combinedContextForVerifier` — the same context blocks formatted as the **only source of truth** for the editor pass.

`aiService.generateVerifiedResponse(systemPrompt, combinedContextForVerifier)`:
1. **Writer**: chat model produces a draft answer.
2. **Editor**: chat model is asked to fact-check the draft against the source data only. It must reply exactly `VALID` if accurate, otherwise rewrite.
3. If editor returns `VALID`, return the draft. Else return the rewritten answer.
4. On any error in this chain, fall back to a single-shot `generateResponse()`.

### 6.4 Response shape

```json
{
  "success": true,
  "answer": "...",
  "debug": {
    "factsUsed": 5,
    "logsUsed": 5,
    "hasSummary": true,
    "verification": "Enabled"
  }
}
```

---

## 7. Authentication

`src/lib/auth.ts` configures **better-auth** with the drizzle adapter and email/password enabled.

- The Express app mounts the better-auth Node handler with a wildcard splat:
  `app.all("/api/auth/*splat", toNodeHandler(auth))`
- For protected endpoints (`/api/logs`, `/api/chat`), the handler converts Express headers to a `HeadersInit` (via `toHeadersInit`) and calls `auth.api.getSession({ headers })`. Missing session → 401.
- Sessions, accounts, verifications are persisted in the matching Postgres tables defined in `db/schema.ts`.

---

## 8. Configuration & Environment

Centralized in `src/config/index.ts` and consumed by helpers and (incrementally) the rest of the app.

Required env vars (validated by `validateConfig()`):
- `DATABASE_URL`
- `BETTER_AUTH_SECRET`
- `GEMINI_API_KEY`

Optional env vars and their defaults:

| Variable                | Default                          | Used in                         |
| ----------------------- | -------------------------------- | ------------------------------- |
| `PORT`                  | `3000`                           | server bootstrap                |
| `NODE_ENV`              | `development`                    | config                          |
| `REDIS_URL`             | `redis://localhost:6379`         | `lib/redis.ts`                  |
| `BETTER_AUTH_URL`       | `http://localhost:3000`          | better-auth                     |
| `CORS_ORIGINS`          | `http://localhost:5173`          | CORS middleware                 |
| `FACT_HALF_LIFE_DAYS`   | `45`                             | recency weight in `/api/chat`   |
| `FACT_SCORE_THRESHOLD`  | `0.12`                           | filter weak facts in `/api/chat`|
| Rate limits             | chat 10/min, logs 30/min, gen 100/min | declared in `config` (not yet wired) |

---

## 9. Cross-cutting Utilities

### 9.1 `utils/errors.ts`
Typed exception hierarchy rooted at `AppError(statusCode, code, isOperational)`. Subclasses: `ValidationError`, `UnauthorizedError`, `ForbiddenError`, `NotFoundError`, `ConflictError`, `RateLimitError`, `ExternalServiceError`, and the AI/vector specializations `AIServiceError`, `VectorServiceError`. Currently *defined* but the routes still throw/return raw 4xx/5xx — wiring an error-handling middleware is a natural next step.

### 9.2 `utils/logger.ts`
JSON structured logger with `debug/info/warn/error/request/worker` methods. Outputs one JSON object per line (timestamp, level, message, context, error). Currently the live code paths in `src/index.ts` and `workers/log.worker.ts` still use `console.log` — the logger is in place to migrate to.

### 9.3 `utils/helpers.ts`
Pure helpers used by the chat endpoint: stopword/negation/positive sets, `parseTimestampMs`, `daysSince`, `recencyWeight`, `normalizeKey`, `polarityScore`, `formatDateLabel`, `recencyLabel`, `toHeadersInit`, `getTodayDateString`, and the shared `UUID_NAMESPACE` constant. `src/index.ts` currently inlines copies of these functions; consolidating onto `utils/helpers.ts` is a pending cleanup.

---

## 10. Operational Notes

### Local dev
1. `docker compose up -d` (Postgres, Redis, Qdrant)
2. `npm run db:push` (apply drizzle schema)
3. `npm run dev` (tsx watch — also imports the worker so a single process serves HTTP and consumes the queue)

### Health & test endpoints
- `GET /health` — liveness `{ status: "OK", timestamp }`
- `POST /api/test-queue` — enqueues a synthetic job, no auth (dev tool)
- `POST /api/test-ai` — embeds + summarizes input text, no auth (dev tool)

### Server bootstrap (`startServer`)
1. `vectorService.initCollection()` — creates any missing Qdrant collections at the right dim/distance
2. `app.listen(PORT)`

### Process model
- HTTP server and BullMQ worker run **in the same Node process** (the worker is imported as a side-effect of `src/index.ts`). For production scale, the worker can trivially be split out by importing it from a separate entrypoint.

---

## 11. The "ACE" Memory Model — Why Three Stores?

| Memory type    | Backed by                | What it answers                                                  |
| -------------- | ------------------------ | ---------------------------------------------------------------- |
| **Long-term**  | `user_facts` (Qdrant)    | Stable preferences, sensitivities, recurring patterns            |
| **Episodic**   | `productivity_logs`      | "What did the user actually say on day X about topic Y?"         |
| **Working**    | `daily_summaries`        | "What's the user's state *today* — mood, key activities so far?" |
| **Source of truth** | Postgres `log_entry` | Durable record of every submitted log + its processing status    |

Postgres holds the canonical text; Qdrant holds the semantic indexes built from it. If Qdrant data is lost, it can be rebuilt from `log_entry` by re-running the worker pipeline.

---

## 12. Known Gaps / Next Steps

These are visible in the current code and are good candidates for follow-up work:

- **Inline duplication in `src/index.ts`** — stopwords, helpers, and the chat handler should move to dedicated route + service files using `utils/helpers.ts`.
- **`utils/errors.ts` and `utils/logger.ts`** are not yet integrated; routes still hand-roll status codes and use `console.*`.
- **Rate limits in config are not enforced** — middleware is not yet wired.
- **Worker observability**: the `failed` listener has a TODO for Sentry integration.
- **`/api/test-queue` and `/api/test-ai`** are unauthenticated and should be gated behind `NODE_ENV !== "production"` or removed.
- **Embedding cache** (`config.ai.embeddingCacheTTL`) is configured but not used; the worker re-embeds on every retry.
