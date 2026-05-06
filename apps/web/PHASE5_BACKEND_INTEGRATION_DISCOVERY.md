# Phase 5 Backend Integration Discovery

Last updated: 2026-05-05 (post auth + consent + bulk-events FE integration)

> **Status: Auth, consent, and event ingestion are shipped on the FE.**
> Phases 5.0 → 5.4 are complete. Remaining phases are gated on backend delivery for the catalog/search/PDP/profile resource families.
>
> Backend currently ships:
> - `POST /register`, `POST /login` returning a Bearer JWT
> - JWT auth middleware on every non-public route
> - `customer_id` resolved server-side from JWT (no longer in request bodies/querystrings)
> - normalized consent routes (`GET /consent`, `POST /consent`)
> - normalized right-to-delete (`DELETE /customer`) — **not consumed by FE** (operator-only)
> - bulk events endpoint: `POST /events/batch` (max 100 events per request)
> - jobs + traces endpoints (`GET /jobs/{id}`, `GET /traces/{id}`) — **not consumed by FE** (operator-only)
>
> FE-side surfaces shipped:
> - `tokenStore.ts` + `useAuth()` + protected routes + login/register pages.
> - Authenticated `apiClient` with `Authorization` injection, normalized error envelope, 401 → `auth:expired` event.
> - Consent hooks + page + banner, all auth-gated, with first-time-user setup flow on 404.
> - Reliable event tracker with IndexedDB persistence, 3s/50-event batch triggers, keepalive flushes on visibility/pagehide, online resume, identity-aware purge.

## Purpose

Before wiring the frontend to real backend APIs, this document captures:

1. frontend endpoint expectations (current app behavior),
2. backend endpoint reality (current `server` implementation),
3. required frontend changes for compatibility,
4. backend gaps required for full parity, and
5. phased integration order.

This is a pre-integration planning artifact. No blind API swapping.

## Sources reviewed

- `plan.md` (system architecture and backend rollout phases)
- `schema.md` (DynamoDB/Redis/OpenSearch contracts)
- `apps/web/event-types-description.md` (canonical FE event + recommendation context spec)
- `apps/web/src/shared/api/client.ts` (all frontend API usage)
- `apps/web/API_REQUIREMENTS.md` (target contract)
- `apps/web/API_HANDOVER_STATUS.md` (handover status baseline)
- `server/src/main.py`
- `server/src/auth.py` (JWT primitives)
- `server/src/middleware/auth.py` (JWT middleware + `current_customer_id` dependency)
- `server/src/routes/auth.py` (`POST /register`, `POST /login`)
- `server/src/routes/events.py` (`POST /events`, `POST /events/batch`)
- `server/src/routes/consent.py` (`GET /consent`, `POST /consent`)
- `server/src/routes/recommend.py` (`GET /recommend`)
- `server/src/routes/jobs.py` (`GET /jobs/{job_id}`)
- `server/src/routes/traces.py` (`GET /traces/{job_id}`)
- `server/src/routes/customer.py` (`DELETE /customer`)
- `shared/schemas.py` (auth + event + consent request/response shapes)

## Architecture context (from plan)

- Frontend (`apps/web`) talks to REST APIs.
- Server (`FastAPI`) handles REST, JWT auth, consent gate, queue handoff.
- JWT middleware on the server resolves `customer_id` from the Bearer token; routes never accept `customer_id` from clients.
- Worker processes jobs asynchronously and produces recommendation results.
- Redis is used for queue, recommendation cache, and (later) hot-profile state.
- DynamoDB stores events, consent, jobs, and the auth (email → `customer_id` + password hash) table.

Integration implication: every protected FE call must carry `Authorization: Bearer <token>`, and the FE must support async-oriented flows (event → job → status) plus non-uniform endpoint maturity while backend phases progress.

## Frontend expectation inventory (current)

From `apps/web/src/shared/api/client.ts`, frontend currently expects:

- auth (NEW — to be added):
  - `POST /register`
  - `POST /login`
  - (logout is client-side: clear token + invalidate caches)
- catalog/listing/search:
  - `GET /catalog/categories`
  - `GET /catalog/facets`
  - `GET /catalog/products`
  - `GET /catalog/popular`
  - `GET /catalog/products/{slug}`
  - `GET /search`
- reviews:
  - `GET /catalog/products/{slug}/reviews`
  - `POST /catalog/products/{slug}/reviews`
  - `PUT /catalog/products/{slug}/reviews/{reviewId}/helpful`
- recommendations surfaces:
  - `GET /recommendations/home`
  - `GET /recommendations/{surface}`
  - (will be folded onto the single `GET /recommend?context=...` adapter)
- consent / profile / debug:
  - `GET /consent`
  - `PUT /consent` → must change to `POST /consent`
  - `GET /me/profile`
  - `PATCH /me/preferences`
  - `GET /me/explanations`
  - `GET /debug/events`
- commerce:
  - `POST /checkout`
  - `GET /me/orders`
  - `PATCH /me/orders/{id}/delivery-address`
  - `GET /me/addresses`
  - `PATCH /me/addresses/{id}`
- tracking:
  - `POST /events` (per-event today; migrating to `POST /events/batch`)
- privacy / right-to-erase (NEW — to be added):
  - `DELETE /customer`

## Backend reality inventory (current server code)

### Public routes (no auth)

- `GET /health`
- `GET /` (service banner)
- `GET /docs`, `GET /openapi.json`, `GET /redoc`
- `POST /register` — body `{ email, password }`, returns `{ customer_id, email, token, token_type, expires_in }`
- `POST /login` — body `{ email, password }`, returns same `AuthResponse` shape

### JWT-protected routes (require `Authorization: Bearer <token>`)

- `POST /events` — singular, kept for backwards compat
- `POST /events/batch` — bulk, accepts 1..100 events
- `GET /recommend?context=...` — `customer_id` resolved from JWT
- `GET /consent` — JWT-derived
- `POST /consent` — JWT-derived, body `{ scopes, data_retention_days }`
- `DELETE /customer` — JWT-derived
- `GET /jobs/{job_id}`
- `GET /traces/{job_id}`

### Backend request/response shapes (canonical)

`AuthResponse`:

```ts
type AuthResponse = {
  customer_id: string;
  email: string;
  token: string;        // JWT, place in Authorization: Bearer <token>
  token_type: "bearer";
  expires_in: number;   // seconds
};
```

`IngestEventRequest` (per event in a batch):

```ts
type IngestEventRequest = {
  client_event_id: string;        // FE-generated UUID — server idempotency key
  event_type: string;
  payload: Record<string, unknown>;
  consent_scope?: string[];       // optional snapshot
  // NOTE: no customer_id — server resolves from JWT
};
```

`IngestBatchRequest`:

```ts
type IngestBatchRequest = {
  events: IngestEventRequest[];   // length 1..100
};
```

`IngestBatchResponse`:

```ts
type IngestEventResult = {
  client_event_id: string;
  status: "queued" | "rejected";
  event_id?: string;
  job_id?: string;                // deterministic: `evt_${client_event_id}`
  reason?: string;                // e.g. "no_consent_record" | "missing_personalization_scope"
};

type IngestBatchResponse = {
  accepted: number;
  rejected: number;
  results: IngestEventResult[];   // ordered to mirror request `events[]`
};
```

`ConsentUpsertRequest`:

```ts
type ConsentUpsertRequest = {
  scopes: string[];                  // e.g. ["personalization", "analytics"]
  data_retention_days?: number;      // default 90
};
```

### Still backend-side TODO (from frontend perspective)

- all catalog/search/reviews endpoints
- `/recommendations/*` surface rail endpoints
- profile/explanations/debug endpoints used by FE
- checkout/orders/addresses endpoints used by FE

## Expectation vs reality matrix

### Group A: ready to integrate now

#### Auth (NEW)

- FE has: nothing yet. There is no register/login flow in `apiClient`.
- BE has: `POST /register`, `POST /login` returning `AuthResponse`.

Required FE changes:

- add `apiClient.register({ email, password })` and `apiClient.login({ email, password })`.
- store the JWT token, `customer_id`, and `expires_in` (computed expiry timestamp) in a token store.
- inject `Authorization: Bearer <token>` on every protected request.
- handle 401 responses by clearing the token and routing to login.
- minimal login/register UI surfaces.
- token storage decision: see *Token storage strategy* below.

#### Consent

- FE currently calls `GET /consent` and `PUT /consent`.
- BE provides `GET /consent` and `POST /consent`.

Required FE changes:

- change `apiClient.updateConsent` from `PUT` to `POST`.
- align request body to `{ scopes, data_retention_days? }` (drop any FE-side `customer_id`).
- keep response shape compatible with current FE consumers (`{ customer_id, scopes, data_retention_days }`).

#### Jobs and traces

- FE currently has no client methods.
- BE provides `GET /jobs/{job_id}` and `GET /traces/{job_id}`.

Required FE changes:

- add typed `apiClient.getJob(jobId)` and `apiClient.getTraces(jobId)`.
- wire optional debug surfacing on the recommendation/audit drawer when needed.

#### Customer delete

- FE currently has no client method.
- BE provides `DELETE /customer` (JWT-derived, no path param).

Required FE changes:

- add `apiClient.deleteAccount()` for the privacy / right-to-erase action.
- post-delete: clear token store, clear all cached state, route to login or marketing landing.

#### Events (NEW shape — bulk endpoint shipped)

- FE currently calls `apiClient.trackEvent(IngestEventRequest)` per event.
- BE shipped `POST /events/batch` with full per-event idempotency support.

Required FE changes:

- adopt `POST /events/batch` as the primary transport.
- per-event `client_event_id` (FE UUID) is now mandatory.
- treat `IngestBatchResponse.results[i]` as authoritative — only delete locally persisted events whose `status === "queued"`.
- on `status === "rejected"` with `reason === "no_consent_record"` or `"missing_personalization_scope"`, do not retry — surface a consent-prompt path.
- batch size cap: 100 events per HTTP request.
- keep singular `POST /events` only as a transitional fallback if needed; primary path is batch.

#### Recommendation

- FE currently expects rail-style endpoints (`GET /recommendations/home`, etc.) via MSW.
- BE provides a single `GET /recommend?context=...` (JWT-derived `customer_id`).

Required FE changes:

- introduce a single `apiClient.getRecommendation(context)` that calls `GET /recommend?context=<encoded>`.
- compose page-level rails by calling this endpoint with different `context` values (`homepage`, `category:{slug}`, `product_page:{slug}`, `cart_active`, etc.) — see `event-types-description.md`.
- React Query key: `["recommend", customer_id, context]`, `staleTime: 5min`.
- keep MSW rail-style endpoints around for surfaces backend hasn't shipped yet (or wrap them under the same `getRecommendation` adapter so component code is unchanged).

### Group B: still blocked on backend delivery

- Catalog, facets, product detail, search
- Reviews and helpful votes
- Profile, explanations, debug events read endpoint
- Checkout, orders, addresses

For these, frontend stays on MSW until backend endpoints exist.

## Critical contract mismatches — current status

1. ~~**Consent path + method mismatch**~~ — RESOLVED
   - BE now exposes `GET /consent` and `POST /consent` (JWT-derived).
   - FE only needs to switch `PUT` → `POST` and drop client-supplied `customer_id`.

2. **Recommendation surface mismatch** — partially resolved
   - BE still exposes one `GET /recommend?context=...` instead of multiple rail endpoints.
   - FE composes rails by calling this endpoint with different `context` values.
   - This is acceptable for now per the canonical spec in `event-types-description.md`.

3. ~~**Identity model mismatch**~~ — RESOLVED
   - JWT middleware extracts `customer_id` from the Bearer token.
   - FE must remove all explicit `customer_id` from authenticated request bodies/querystrings.
   - Identity resolution centralizes into the token store, single source of truth.

4. **Error envelope mismatch** — still open
   - FE client throws `Error("Request failed: status")`.
   - BE returns FastAPI `{ detail: "..." }` on 4xx and `{ error: "..." }` on 401 (middleware) and 500 (handler).
   - FE must implement a normalized error mapper that handles both shapes.

5. **Event batch response handling** — new requirement
   - FE must consume `IngestBatchResponse` per-event status (not just batch HTTP status).
   - Partial-success semantics matter: some events queued, others rejected for consent reasons in the same response.

## Frontend modifications required before endpoint swapping

1. **Auth + token store** — new top-priority item.
   - module under `apps/web/src/features/auth/` owning `register`, `login`, `logout`, `getToken`, `getCustomerId`, `isAuthenticated`.
   - all other modules read identity from this store, never from URL/state directly.
2. **Authenticated `apiClient`** — every method automatically attaches `Authorization: Bearer <token>` for non-public routes.
   - 401 handler clears the token, dispatches a `auth:expired` event, and redirects to `/login`.
3. **Canonical error mapper** — handles both `{ detail: ... }` and `{ error: ... }` envelopes plus network errors. Returns `{ status, code, message, retryable }`.
4. **Swap-ready API adapter layer** — no path literals in feature hooks/components (already partially structured in `client.ts`).
5. **Central query key factory** — keys derived from `(customer_id, resource, params)`. Auth changes invalidate the entire identity-scoped namespace.
6. **Backend capability flags** — per resource family (`auth | events | recommend | consent | jobs | traces | catalog | search | reviews | profile | commerce`) toggleable between `real` and `mock` so we mix safely while migration is in progress.

## Backend build expectations before full FE parity

Minimum for browse/search parity:

- `GET /catalog/categories`
- `GET /catalog/facets`
- `GET /catalog/products`
- `GET /catalog/products/{slug}`
- `GET /search`

Minimum for PDP social proof:

- `GET /catalog/products/{slug}/reviews`
- `POST /catalog/products/{slug}/reviews`
- `PUT /catalog/products/{slug}/reviews/{reviewId}/helpful`

Minimum for profile/personalization surfaces:

- `GET /me/profile`
- `PATCH /me/preferences`
- `GET /me/explanations`
- `GET /debug/events` (or a replacement endpoint contract)

Minimum for checkout/account:

- `POST /checkout`
- `GET /me/orders`
- `PATCH /me/orders/{orderId}/delivery-address`
- `GET /me/addresses`
- `PATCH /me/addresses/{id}`

## Event tracking integration spec

The canonical FE-side event vocabulary lives in `apps/web/event-types-description.md`. That file is the single source of truth for:

- allowed `event_type` values and their `payload` shapes,
- aggregation rules (debounce, dedupe, dwell, no PII),
- recommendation `context` strings.

The backend bulk endpoint `POST /events/batch` is now live (see *Backend reality inventory*). FE must adopt this as the primary transport. The integration **must** be reliable across:

- network drops mid-flight,
- tab close / navigation away,
- full page reload,
- device sleep / app backgrounding,
- consent revocation mid-buffer.

### Goals

1. Drop zero events that the user actually performed under valid consent.
2. Never block the UI thread — tracking must always be fire-and-forget at the call site.
3. Be cost-efficient — never send one HTTP request per event in normal browsing.
4. Be idempotent — server can safely receive the same event twice and dedupe.
5. Survive reload — if the browser dies before flush, next session resumes the queue.
6. Respect consent — events emitted while consent is missing are dropped or anonymized at enqueue time.

### Architecture

A small dedicated module under `apps/web/src/features/events/tracker/` (proposed path) acts as the only producer of `POST /events/*`:

```
[any feature code]
    └─ trackEvent(type, payload)
            │
            ▼
[EventTracker]
    ├─ in-memory ring buffer (fast path)
    ├─ persistent IndexedDB queue (durable path)
    ├─ flush triggers
    │     ├─ size:    >= 50 events buffered
    │     ├─ time:    every 3000ms (idle debounce)
    │     ├─ visibility: document.visibilityState === "hidden"
    │     ├─ pagehide / freeze events
    │     └─ network: navigator.onLine -> true (after offline)
    └─ transport
          ├─ default:  fetch(`/events/batch`, { keepalive: true })
          └─ unload:   navigator.sendBeacon('/events/batch', blob)
```

No feature code may call `fetch('/events*')` directly. All event emission flows through `trackEvent`.

### Storage choice — IndexedDB (not localStorage)

**Decision:** persistent queue lives in IndexedDB.

Reasons:

- `localStorage` is synchronous and blocks the main thread on writes — unacceptable for high-frequency event emission.
- `localStorage` has a ~5MB total quota across the entire origin and is shared with other features.
- IndexedDB supports structured cloning (objects, dates), large quotas, async access, and cursor-based draining of pending records.
- Survives full page reload because writes are durable per record.

Recommended library: `idb` (small Promise wrapper around IndexedDB). Avoid building a custom transactional wrapper unless `idb` is rejected for bundle reasons.

Database layout:

- DB: `hyperpersona-events`
- Object store: `pending`
  - keyPath: `client_event_id` (UUID)
  - indexed by `client_emitted_at` for FIFO drain order
  - indexed by `next_attempt_at` for the backoff scheduler

### Per-event shape (FE-generated)

Each event the FE produces gets a client-generated UUID before it ever leaves memory. This is the basis of server-side idempotency. The wire shape is fixed by `IngestEventRequest` in `shared/schemas.py`:

```ts
// Wire shape sent to the server
type IngestEventRequest = {
  client_event_id: string;          // UUIDv4 generated on FE — server idempotency key
  event_type: string;               // from event-types-description.md
  payload: Record<string, unknown>;
  consent_scope?: string[];         // snapshot at enqueue time
  // NOTE: no customer_id — server derives it from the JWT
};

// Internal shape kept in IndexedDB. Adds metadata the server doesn't need.
type StoredEvent = IngestEventRequest & {
  client_emitted_at: string;        // ISO timestamp at enqueue
  client_session_id: string;        // session-scoped UUID
  schema_version: number;           // 1 today; bump if payload shape changes
  attempt_count: number;            // retry counter
  next_attempt_at: number;          // epoch ms — used by backoff scheduler
};
```

The server treats `client_event_id` as the dedupe key (deterministic `job_id = evt_${client_event_id}`). FE retries the same `client_event_id` on transient failures.

### Batch envelope (FE → BE)

The wire shape is fixed by `IngestBatchRequest` in `shared/schemas.py`:

```ts
type IngestBatchRequest = {
  events: IngestEventRequest[];     // FIFO order, length 1..100 (BE-enforced cap)
};
```

The FE keeps a logical `batch_id` (UUID) for its own logs/diagnostics, but it does **not** send it on the wire — the server does not require it.

Server-side response handling (per `IngestBatchResponse`):

- HTTP 200 with `results[]` is the expected success path.
- For each `result`:
  - `status === "queued"` → delete the matching `client_event_id` from IndexedDB.
  - `status === "rejected"` → do **not** retry. Reasons today:
    - `"no_consent_record"` → no consent doc for this customer; surface a consent prompt.
    - `"missing_personalization_scope"` → user opted out; drop and stop emitting until consent changes.
- HTTP 4xx other than per-event rejection (e.g. 422 schema error) → batch is malformed, drop it (do not loop forever on poison pills). Log to debug for repro.
- HTTP 5xx / network error → retain and retry the batch with exponential backoff.
- HTTP 401 → token expired. Pause flushes. Trigger auth re-login. Resume flushing once a new token lands.
- Hard cap `events.length <= 100` per request. The tracker chunks larger queues into multiple requests.

### Flush triggers

The tracker decides to flush when **any** of these fire:

1. **Size trigger** — buffer length >= `MAX_BATCH_SIZE` (default 50).
2. **Time trigger** — `FLUSH_INTERVAL_MS` since the oldest unsent event (default 3000ms).
3. **Visibility trigger** — `document.visibilitychange` -> `hidden`.
4. **Pagehide trigger** — `pagehide` and `freeze` events.
5. **Online trigger** — `online` event after a previous offline period.
6. **Manual trigger** — `tracker.flush()` for tests and explicit moments (e.g. checkout submit).

`beforeunload` is intentionally **not** used — it's unreliable across browsers and can interact badly with bfcache. Use `pagehide` instead.

### Transport rules

- **Normal flush**: `fetch('/events/batch', { method: 'POST', keepalive: true, body: JSON, headers: { 'Content-Type': 'application/json' } })`.
  - `keepalive: true` allows the request to survive a tab close that begins after dispatch.
  - Allows JSON content-type (which `sendBeacon` does not).
- **Unload flush** (`pagehide`): use `navigator.sendBeacon('/events/batch', blob)` as a guaranteed-attempt fallback.
  - Wrap payload as `new Blob([JSON.stringify(batch)], { type: 'application/json' })`.
  - If `sendBeacon` is unavailable, fall back to `fetch(..., { keepalive: true })`.
- **Payload size cap**: `keepalive` is limited to ~64KB per request across all keepalive fetches. The tracker must enforce a serialized-size cap and split into multiple batches if exceeded.

### Reliability rules

1. **Persist before send.** Every event is written to IndexedDB at `trackEvent()` time, not at flush time. This means a tab kill between enqueue and flush still leaves the event recoverable.
2. **Acknowledged delete.** On 2xx, delete only the `client_event_id`s whose result is `status === "queued"`. Leave the rest in IndexedDB to be retried (or marked dead on `rejected`).
3. **Retry policy.** Exponential backoff per batch attempt: 1s, 2s, 4s, 8s, capped at 30s. Reset on success.
4. **Max age.** Drop persisted events older than 7 days at boot (configurable). Avoid uploading stale signal weeks later.
5. **Cap on queue size.** Hard cap at `MAX_QUEUE_SIZE` (default 1000). When exceeded, drop the **oldest** events (FIFO eviction) and log a debug counter.
6. **Boot drain.** On app boot, run `drainPending()` before any new events are enqueued so events from a previous tab session are flushed first.
7. **Consent gate at enqueue.** Inspect the latest known consent snapshot before persisting. If `personalization` is not granted, either drop or persist with `consent_scope: []` per policy decision.
8. **Consent revocation.** When consent is revoked, the tracker must purge events that were enqueued under personalization scope but not yet sent.
9. **Schema migrations.** If `schema_version` of stored events is older than the current code's expectation, run a migration step at boot (for now: drop them).
10. **Single instance per tab.** Tracker is a module-level singleton; do not instantiate in components.
11. **Multi-tab safety.** IndexedDB writes are scoped to origin and shared across tabs. Use a `BroadcastChannel('hyperpersona-events')` so only one tab is the active flusher at a time, preventing duplicate sends. The chosen tab pings every few seconds; if it goes silent, another tab takes over.
12. **Clock skew tolerance.** All timestamps are FE-provided ISO strings — server may correct using its own clock if needed.

### Aggregation rules (mirror `event-types-description.md`)

Implemented inside the producer side (before enqueue), not on the server:

- `search` — fired on submit only, not on keystroke.
- `product_dwell` — at most once per PDP load, only after >=10s.
- Generic dedupe — drop the same `event_type` + `payload` hash within a 2s window.

These rules belong inside `trackEvent()` so callers can stay simple.

### Auth integration (RESOLVED — auth shipped)

The tracker no longer carries `customer_id` on the wire — `IngestEventRequest` does not include it. Identity resolution lives entirely in the JWT middleware:

- the tracker pulls the current Bearer token from the auth/token store at flush time and sets the `Authorization` header.
- if the token store reports no session, the tracker pauses flushes (events still persist to IndexedDB) and waits for an auth event.
- on `auth:login` (new token), drain pending events.
- on `auth:logout` or `auth:expired`, freeze the flusher, do **not** purge stored events automatically (a deliberate logout flow can call `purge()`).
- on `auth:user_changed` (different `customer_id` after login as another user), purge any pending events that were enqueued under the previous identity. Events are tied to the JWT they will be sent under, so cross-identity carryover is unsafe.

### Recommendation API integration

Recommendations follow the rules in `apps/web/event-types-description.md` (sections 2 and 3). Reinforced here so they don't drift:

1. FE must call `/recommend` only on:
   - mount of a surface that has a recommendation slot,
   - a major surface transition (e.g. cart becomes empty/active),
   - email/notification generation flows.
2. FE must **not** call `/recommend` on:
   - every event,
   - per-render renders inside scroll/hover handlers.
3. All `context` strings come from a single `Context.*` helper module — no string concatenation at call sites.
4. Context format is strictly `lowercase + underscores`, no PII, no SKUs, no timestamps.
5. React Query caching:
   - cache key: `["recommend", customer_id, context]` where `customer_id` comes from the auth/token store.
   - `staleTime`: 5 minutes (mirrors Redis offer cache TTL on the server).
   - background refetch disabled by default; explicit invalidation only on consent change, persona switch, or auth identity change.
6. Backend exposes a single `GET /recommend?context=...`. Customer identity is resolved server-side from the JWT — FE does **not** pass `customer_id` in the query. Until backend ships rail-style endpoints, FE rail components consume the same single endpoint with different `context` values and FE composes the page-level layout.
7. On 401 from `/recommend`, fall back to the generic/cold-start visual state in `HomePersonalizedSection` and similar components, and trigger the auth-store re-login flow.

## Token storage strategy

The Bearer token returned from `/login` and `/register` must be persisted in a way that survives reload but does not leak to other origins or unrelated scripts:

- **Choice:** `localStorage` under a single namespaced key, e.g. `hyperpersona.auth.v1`, holding `{ token, customer_id, email, expires_at_ms }`.
- **Rationale:**
  - We do not need cross-tab cookie behavior or server-side session mirroring at this stage.
  - The backend issues a JWT — there is no refresh token rotation yet, so HttpOnly cookie is not yet justified.
  - `localStorage` lets us read the token synchronously on app boot without an extra round trip.
- **XSS risk note:** localStorage is reachable from any script on the origin. Mitigations:
  - strict CSP once the static deploy is finalized,
  - never `dangerouslySetInnerHTML` user-supplied content,
  - keep token TTL short (`expires_in` from the server) and route to login on expiry.
- **Migration path:** if/when the backend adds refresh tokens or HttpOnly session cookies, this module is the only place that needs to change.
- **Multi-tab consistency:** subscribe to `storage` events so a logout in one tab logs out other tabs.

Module location: `apps/web/src/features/auth/tokenStore.ts`. Shape:

```ts
type AuthSession = {
  token: string;
  customer_id: string;
  email: string;
  expires_at_ms: number;        // Date.now() + expires_in * 1000 at issue time
};

export function getSession(): AuthSession | null;
export function setSession(s: AuthSession): void;
export function clearSession(): void;
export function isExpired(s: AuthSession | null, skewMs?: number): boolean;
export function onSessionChange(cb: (s: AuthSession | null) => void): () => void;
```

## Phased integration plan

### Phase 5.0 — Discovery lock (current)

- freeze this document as single source of truth for integration sequencing.
- circulate to FE + BE owners and resolve any disagreement on contract shapes before code lands.

### Phase 5.1 — Integration scaffolding (no endpoint swaps yet)

- implement FE adapter boundary so feature code never imports raw paths.
- add canonical error envelope mapper (`{ status, code, message, retryable }`).
- add capability flags (`real | mock`) per resource family.
- add central query key factory keyed on `(customer_id, resource, params)`.

### Phase 5.2 — Auth integration (FIRST real cutover)

This is the unblocking phase for everything else. No other real-backend cutover happens before this lands.

- ship `tokenStore.ts` per *Token storage strategy* above.
- ship `apiClient.register({ email, password })` and `apiClient.login({ email, password })`.
- ship a minimal login + register page set + protected-route wrapper. UX can be functional, not polished.
- ship `Authorization: Bearer <token>` injection in `apiClient` for non-public routes.
- ship 401 handling: clear session → emit `auth:expired` → redirect to login → preserve return URL.
- ship `apiClient.logout()` (client-side; clears session, invalidates query cache scoped by `customer_id`).
- ship a `useAuth()` hook reading from the token store via `onSessionChange`, exposed to the rest of the app.
- update React Query: keys derive `customer_id` from `useAuth()`; on auth identity change, invalidate the entire `["recommend", ...]`, `["consent", ...]`, etc. namespace.
- demo persona switcher on the demo lab page is decoupled from real auth — it controls a separate "demo persona" overlay, not the real customer identity.

### Phase 5.3 — Consent (SHIPPED)

Scoped down: `customer-delete`, `jobs`, and `traces` are intentionally **not** integrated on the FE — they're operator/observability surfaces, not user-facing flows. Removing them from the FE shrinks the attack surface and cuts dev-time complexity. The backend keeps shipping them; we just don't consume them here.

- `apiClient.getConsent()` → `GET /consent` (no `customer_id` arg). ✅ shipped
- `apiClient.updateConsent({ scopes, data_retention_days })` → `POST /consent`. ✅ shipped
- 404 from `GET /consent` is handled as "missing record" (first-time user prompt). ✅ shipped
- `useConsentQuery` / `useConsentMutation` hooks gate on `useAuth().isAuthenticated`; the floating consent banner and `/consent` page route through these. ✅ shipped

### Phase 5.4 — Event tracker + bulk ingestion (SHIPPED)

The tracker module under `apps/web/src/features/events/tracker/` implements the full architecture from *Event tracking integration spec*. Status:

1. ✅ Module split: `types.ts`, `storage.ts` (IndexedDB), `aggregation.ts` (2s dedupe window), `tracker.ts` (singleton orchestrator), `init.ts` (DOM listeners), `index.ts` (public API), `TrackerConsentBridge.tsx` (React → tracker consent snapshot).
2. ✅ All `useTrackEvent` callsites enqueue through the tracker (legacy `customer_id` arg dropped on the wire).
3. ✅ Transport calls `POST /events/batch` exclusively. Singular `POST /events` is no longer wired into the FE.
4. ✅ Acks: only `client_event_id`s with `status` of `queued` or `rejected` are deleted from IDB; transient failures stay queued for retry.
5. ✅ Per-event `rejected` outcomes surface in the dev event panel with `reason` and a `rejected` status row.
6. ☐ Capability flag (`tracking.enabled`) — deferred until the wider FE adapter/flag scaffolding lands in Phase 5.1's residual cleanup. Currently the tracker auto-pauses when there's no JWT and when `personalization` consent is missing, which covers the staging cases in practice.
7. ✅ Reliability covered: tab close + reload (`visibilitychange`/`pagehide` keepalive flush + IDB boot drain), offline → online (`online` listener flush), consent revoke mid-buffer (TrackerConsentBridge updates the snapshot — subsequent enqueues drop), auth user-switch (boot drain calls `purgeOtherIdentity`), 7-day age cap, 1000-row queue cap.

### Phase 5.5 — Recommendation `/recommend` cutover

- `apiClient.getRecommendation(context)` → `GET /recommend?context=<encoded>`.
- compose all rail surfaces (`HomePersonalizedSection`, PDP rails, cart rails, etc.) on top of this single endpoint using `Context.*` helpers from `event-types-description.md`.
- React Query: `["recommend", customer_id, context]`, `staleTime: 5 minutes`, no background refetch.
- 401 path: fall back to generic/cold-start UI, trigger auth re-login.
- 504 path (worker timeout from `/recommend`): show generic fallback rail + retry-once button — do not auto-retry on a hot path.
- keep MSW rail-style endpoints (`/recommendations/*`) registered for any surfaces backend hasn't shipped, but route them through the same `getRecommendation(context)` adapter so component code is uniform.

### Phase 5.6 — Catalog + search migration (gated on BE delivery)

- when backend ships catalog endpoints, swap as a single slice (not piecemeal across categories vs. products vs. facets).
- verify facet-count semantics, pagination, sort, and free-delivery filter parity before enabling.

### Phase 5.7 — PDP reviews migration (gated on BE delivery)

- swap reviews and helpful-votes endpoints.
- verify optimistic updates, duplicate-review behavior, helpful-vote idempotency.

### Phase 5.8 — Profile + account migration (gated on BE delivery)

- swap profile/explanations/debug reads + checkout/orders/addresses.
- enforce real backend error and empty-state UX.

## Exit criteria for "ready to start real integration"

- this document approved by FE + BE owners.
- token store + authenticated `apiClient` merged behind capability flags before any other cutover.
- normalized error mapper covers `{ detail }`, `{ error }`, network, and 401-expiry paths.
- event tracker passes reliability checklist (tab close, reload, offline, consent revoke, auth switch) against the real `POST /events/batch` in dev.
- no component imports raw API paths; all access goes through `apiClient`.
- `API_REQUIREMENTS.md` and `API_HANDOVER_STATUS.md` updated post-auth so handover docs and integration docs agree.
