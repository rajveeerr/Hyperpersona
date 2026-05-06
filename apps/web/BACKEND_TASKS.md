# Backend Tasks Deferred From Frontend Phase

## Purpose

This file tracks backend work needed to support the web frontend contract.

Reality check (2026-05-05): this is no longer "frontend-only". A real `server/` + `worker/` stack exists and some APIs are already live. See `API_HANDOVER_STATUS.md` for the implementation ledger.

## Completed on real backend (can be treated as done)

- `POST /events` ingestion with consent gating and worker job enqueue
- `GET /recommend` (job-backed recommendation response + cache)
- consent routes: `POST /consent`, `GET /consent/{customer_id}`
- `GET /jobs/{job_id}`
- `GET /traces/{job_id}`
- `DELETE /customer/{customer_id}` right-to-delete flow

## Already Represented In Current Plan Or Schema

- customer event ingestion via `POST /events`
- consent record model
- async jobs model
- worker-driven event processing
- recommendation generation concept
- profile and memory architecture in DynamoDB, Redis, and OpenSearch

## Remaining Backend Work Required By Frontend

### Catalog

- choose canonical catalog store and schema
- implement category and product read APIs
- support filters, sort, and **pagination** (`page`, `pageSize`, `total`)
- support **facet counts** for `vertical`, `freeDelivery`, and **price range** (and future histograms) on filtered sets
- support **vertical-specific** merchandising fields on `Product`: `images`, `longDescription`, `specification`, `dimensions`, `department`, `dateFirstAvailable`, `tags`, `colorOptions`, `sizeOptions`, `storageOptions`, `freeDelivery`
- index **tags** and **personalizationTags** for filter + search
- support related-product retrieval for PDP and cart surfaces; **re-rank** related items using **variant + free-delivery affinity** from events

### Product reviews (UGC)

- persist `ProductReview` rows per `productId` / `slug` with pagination (`GET /catalog/products/{slug}/reviews`)
- expose optional `viewerReview` on `GET /catalog/products/{slug}` when the customer already submitted a review
- implement `POST /catalog/products/{slug}/reviews` with validation, idempotency rules, and `409` when a second create is attempted for the same customer + SKU
- implement `PUT .../reviews/{reviewId}/helpful` with per-customer vote storage and correct aggregate `helpfulCount` / `notHelpfulCount` (including vote changes)
- ingest review telemetry via `POST /events` (`product_reviews_viewed`, `product_reviews_page_loaded`, `product_review_submitted`, `product_review_engagement`) for personalization workers
- define moderation / PII policy for `body` and `authorDisplayName`; optional verified-purchase linkage to orders
- recompute product-level `rating` and `reviewCount` (sync write-through or async job—document which)

### Search

- implement product search index
- support personalized reranking
- return explanation snippets for boosted results
- support query suggestions

### Recommendations

- implement home, PDP, cart, and profile recommendation surfaces
- include reason and confidence metadata
- support generic fallback when consent is missing

### Consent

- expose `GET /consent`
- expose `PUT /consent`
- ensure consent affects recommendation and search APIs consistently

### Auth

- define the frontend auth approach for the web app
- expose `POST /auth/session` or equivalent session bootstrap endpoint
- expose `GET /auth/me` or equivalent current-user endpoint
- decide guest versus authenticated demo behavior
- define how persona switching works in demo mode without conflicting with real auth
- align auth claims with consent, profile, and debug access rules

### Profile

- expose `GET /me/profile`
- expose `PATCH /me/preferences`
- expose `GET /me/explanations`
- define how explicit preferences are merged with inferred signals

### Checkout

- decide whether fake checkout remains purely frontend or returns a backend confirmation stub
- define analytics or event semantics for checkout milestones
- persist **order lines** with `selectedOptions` + `quantity` for downstream recommendations and repurchase flows

### Orders and addresses

- implement `GET /me/orders` with pagination and immutable `OrderSummary` rows
- implement `PATCH /me/orders/{orderId}/delivery-address` with business rules (cutoff when shipped)
- implement `GET /me/addresses` and `PATCH /me/addresses/{id}` (default address semantics)
- expose **tracking URLs** or carrier integration when available

### Event pipeline extensions

- ingest **`CommerceTelemetryEventType`** payloads (`product_tile_clicked`, `pdp_variant_selected`, `pdp_quantity_changed`, `pdp_tab_selected`, free-delivery impression, report click) into the same worker topology as `POST /events`
- build **segment features** for “free delivery preference” and “electronics vs apparel affinity” from these events for recommendations and search reranking

### Debug And Audit

- expose `GET /jobs/{jobId}`
- expose event and recommendation debug endpoints for demo use
- map worker traces or recommendation decisions into a frontend-friendly format

### Operational Follow-Ups

- align auth model for the web app
- publish OpenAPI for typed frontend generation
- add rate limits and error envelopes
- define deployment topology for web-to-api communication
