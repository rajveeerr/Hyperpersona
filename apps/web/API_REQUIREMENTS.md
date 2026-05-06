# API Requirements For Backend Handoff

## Purpose

This document defines the frontend-facing API contract expected by the demo commerce app. It is intentionally broader than the current backend implementation because the frontend is being built first.

## Design Principles

- Keep product catalog as the canonical source for browseable product data.
- Keep customer events, consent, and async job flow aligned with the existing DynamoDB-centered schema.
- Return explanation-friendly payloads so the UI can prove personalization is working.
- Support generic fallback behavior when consent is absent.

## Core Resources

- `Product` (extended optional PDP / listing merchandising fields)
- `ProductReview`
- `Category`
- `OrderSummary` / `OrderListResponse`
- `DeliveryAddress` / `DeliveryAddressListResponse`
- `CatalogFacetGroup` (listing/search facets)
- `SearchResult`
- `RecommendationRail`
- `ConsentRecord`
- `ProfileSummary`
- `ExplanationRecord`
- `TrackedEvent`
- `CheckoutOrder`

## Endpoints

### Catalog

#### `GET /catalog/categories`

Returns all visible categories used in navigation and home modules.

#### `GET /catalog/popular`

Returns a fixed-size list of **best-selling or highest-signal** products (`Product[]`) using **catalog-wide** rules—**not** personalized per customer. Intended for home “most popular” rails.

#### `GET /catalog/products`

Query params:

- `category` — category `slug`
- `brand` — exact brand match (case-insensitive)
- `minPrice`, `maxPrice` — numeric inclusive range on `Product.price`
- `tags` — comma-separated; matches if any token appears in `tags` or `personalizationTags` (substring, case-insensitive)
- `vertical` — comma-separated enum: `apparel` | `furniture` | `electronics` | `general` (products without `vertical` default to `general` in filters)
- `freeDelivery` — when `true`, only products with `freeDelivery: true`
- `sort` — `featured` | `price-asc` | `price-desc` | `rating`
- `page` — 1-based (default `1`)
- `pageSize` — default `12`, cap e.g. `48`
- `q` — same semantics as search (optional; when present, catalog behaves like a scoped search)

Response:

- `items` — page slice of `Product`
- `page`, `pageSize`, `total`
- `personalized` — boolean echo (consent-driven ranking may adjust order in a real backend; demo may keep deterministic sort)
- _(Legacy)_ `facets` on this response is optional/deprecated — prefer **`GET /catalog/facets`** so facet aggregates are not coupled to sort/page refetches (see below).

#### `GET /catalog/facets`

Separate facet aggregation for listing/search UIs. Use the **same filter params** as `GET /catalog/products` / search **except** `sort`, `page`, and `pageSize` do not affect facet membership counts.

Returns `CatalogFacetGroup[]` — counts for the current filter context (computed **before** pagination), with **per-group** semantics: counts within `vertical` ignore the active `vertical` selection when tallying other departments (standard facet UX); same idea for `freeDelivery`.

#### Product fields required for current listing filters

On each **`Product`**, the backend must expose at minimum:

| Filter / facet | `Product` fields |
|----------------|------------------|
| Category browse (`category` query param) | `category` — slug aligned with `GET /catalog/categories` |
| Department / vertical pills | `vertical` — `apparel` \| `furniture` \| `electronics` \| omit → treated as `general` in filters |
| Free delivery toggle | `freeDelivery` — boolean |
| Price range (when wired) | `price` — number |
| Tag chips (when wired) | `tags[]`, `personalizationTags[]` |
| Text search | `name`, `brand`, `description`, `features[]`, `tags[]` (substring match per search contract) |

Everything above is already described on the **`Product`** shape in this document; there is no separate “filter schema” beyond these columns.

#### `GET /catalog/products/{slug}`

Returns:

- core product card data (see **Product** shape — includes optional PDP fields)
- `description` (short hero) and optional `longDescription` (tabs / “Product details”)
- optional `specification[]` — structured bullet list (clothes: materials, care, fit; electronics: chipset, radios, ports; furniture: materials, assembly)
- optional `dimensions` — structured + `display` string (package dimensions, device size, flat-pack box, etc.)
- optional `department` (e.g. Mens, Electronics, Furniture)
- optional `dateFirstAvailable`
- optional `tags[]` — merchandising / filter chips
- optional `images[]` — gallery after primary `image`
- optional `colorOptions`, `sizeOptions`, `storageOptions` — variant axes (which axes exist depends on `vertical`; **sizing matrices** may arrive in a later phase — see `FE_PLAN.md`)
- merchandising `badges`, `inventoryStatus`
- review summary (`rating`, `reviewCount`)
- optional `viewerReview` when the authenticated (or demo-session) customer has already submitted a review for this SKU (`id`, `rating`, `title`, `body`, `createdAt`) so the PDP can show “your review” without a second round-trip
- optional `freeDelivery` — listing/PDP badge; **must be tracked** when shoppers view or click SKUs in contexts where this flag is shown (see **Events**)

#### `GET /catalog/products/{slug}/reviews`

Paginated UGC list for the PDP.

Query params:

- `page` (default `1`)
- `pageSize` (default `10`, cap e.g. `50`)

Response:

- `items`: array of `ProductReview`
- `page`, `pageSize`, `total`

Each `ProductReview` includes server-owned `helpfulCount` and `notHelpfulCount`, plus optional `viewerHelpfulVote` (`helpful` | `not_helpful`) when the caller has registered a vote on that row.

#### `POST /catalog/products/{slug}/reviews`

Creates a new review for the product (authenticated or demo identity).

Request body:

- `rating` (required, 1–5)
- `title` (optional)
- `body` (required, min length enforced server-side)

Response:

- `review` (full `ProductReview` as stored)
- `viewerReview` (compact shape mirrored on `GET /catalog/products/{slug}`)

Errors:

- `409` if the customer already has a review for this SKU (until `PATCH` for edit is added)

#### `PUT /catalog/products/{slug}/reviews/{reviewId}/helpful`

Registers or replaces the caller’s helpfulness vote on someone else’s review (not on their own).

Request body:

- `vote`: `helpful` | `not_helpful`

Response:

- `reviewId`
- updated `helpfulCount`, `notHelpfulCount`
- `viewerHelpfulVote` echo

Replacing an existing vote must adjust counts idempotently (swap helpful ↔ not helpful without double-counting).

#### `GET /catalog/products/{slug}/related`

Returns a recommendation rail for PDP use.

### Search

#### `GET /search`

Query params:

- `q`
- `category`
- `brand`
- `minPrice`, `maxPrice`
- `tags`
- `vertical`, `freeDelivery` (same semantics as catalog listing)
- `sort`
- `page`, `pageSize`

Response:

- `items`
- `query`
- `total`
- `page`
- `pageSize`
- `facets` (same shape as catalog)
- `personalized`
- `explanations`

#### `GET /search/suggestions`

Query params:

- `q`

Response:

- `suggestions`

### Recommendations

#### `GET /recommendations/home`

Returns multiple rails for the home page.

#### `GET /recommendations/pdp`

Query params:

- `productId`

Returns related or complementary rails.

#### `GET /recommendations/cart`

Returns add-on products for the current cart.

#### `GET /recommendations/profile`

Returns profile-driven recommendations and insights.

**Recommendation inputs (backend):** rails and ranking should consume **variant selections**, **quantity changes**, **free-delivery affinity** (from `product_tile_clicked` / PDP events), **vertical**, **filter history**, and **saved addresses** (geo hints only if policy allows) in addition to consent-gated clickstream. Typed payload keys live in `CommerceTelemetryPayload` in `contracts.ts`.

### Orders and fulfillment (tracking + delivery location)

#### `GET /me/orders`

Paginated order history for the current customer.

Query params:

- `page`, `pageSize`

Response:

- `items`: `OrderSummary[]` — each with `id`, `status`, `placedAt`, `total`, `currency`, `destinationLabel`, `lineCount`, optional `trackingUrl`, optional `lines` (SKU lines with `selectedOptions` when variants were chosen), `deliveryAddressId`

#### `PATCH /me/orders/{orderId}/delivery-address`

Change the ship-to address for an order while still eligible (policy: processing vs shipped — backend enforces).

Request body:

- `deliveryAddressId` — must reference an address row the customer owns

Response:

- updated `OrderSummary`

### Saved addresses

#### `GET /me/addresses`

Returns `items: DeliveryAddress[]` — `id`, `label`, `line1`, optional `line2`, `city`, `region`, `postalCode`, `country`, `isDefault`

#### `PATCH /me/addresses/{id}`

Partial update (label, lines, default flag). Changing default may emit `profile_updated` or a dedicated address event.

### Consent

#### `GET /consent`

Returns:

- `customerId`
- `scopes`
- `lastUpdated`

#### `PUT /consent`

Request body:

- `scopes`

Response:

- updated `ConsentRecord`

### Auth

#### `POST /auth/session`

Used to establish a frontend session in the real integrated version.

#### `GET /auth/me`

Returns:

- `customerId`
- `email`
- `name`
- `roles`
- `consentSummary`

#### `POST /auth/logout`

Used by the frontend to end the current authenticated session.

### Profile

#### `GET /me/profile`

Returns:

- explicit preferences
- inferred interests
- recent signals
- top categories
- segment
- last updated

#### `PATCH /me/preferences`

Request body:

- explicit preference updates

Response:

- updated `ProfileSummary`

#### `GET /me/explanations`

Returns:

- current recommendation reasons
- search ranking factors
- profile signal groups

### Events

#### `POST /events`

Request body:

- `customer_id`
- `event_type`
- `payload`
- `consent_scope`
- optional `context` object (recommended normalized shape below)

Response:

- `event_id`
- `job_id`
- `status`

**Review and UGC engagement** (typed in `apps/web/src/shared/api/contracts.ts` as `ReviewTelemetryEventType` / `ReviewTelemetryPayload`):

- `product_reviews_viewed` — shopper opened or scrolled the reviews region; payload includes `productId`, `slug`, `reviewCountShown`.
- `product_reviews_page_loaded` — shopper requested another page of reviews (“load more”); payload includes `productId`, `slug`, `page`, `pageSize`.
- `product_review_submitted` — shopper published a review; payload includes `productId`, `slug`, `reviewId`, `rating` (star value they assigned).
- `product_review_engagement` — shopper marked another author’s review **helpful** or **not helpful**; payload includes `productId`, `slug`, `reviewId`, `vote`.

These events feed personalization, profile inference, and debug/explainability surfaces the same way as cart and search signals. Respect consent: omit or anonymize when scopes disallow behavioral storage.

**Catalog / PDP / variant telemetry** (typed in `apps/web/src/shared/api/contracts.ts` as `CommerceTelemetryEventType` / `CommerceTelemetryPayload`; ingest via same `POST /events`):

- `product_tile_clicked` — listing or grid; payload **must** include `freeDelivery` and `vertical` when known so workers can learn **free-delivery affinity** and **category intent** without inferring from SKU alone.
- `product_pdp_viewed` — PDP load; include `freeDelivery`, `vertical`.
- `pdp_tab_selected` — e.g. Description | Styling ideas | Reviews | Highlights (reference UI); feeds content affinity.
- `pdp_variant_selected` — color, size, storage, or other option; include `optionKind`, `optionId`, `optionLabel`.
- `pdp_quantity_changed` — quantity stepper; include `quantity`.
- `pdp_free_delivery_badge_viewed` — impression when free-delivery treatment is visible (for funnel analysis).
- `pdp_report_product_clicked` — trust & safety funnel (pairs with future `POST /catalog/products/{slug}/report` if added).

**Cart / checkout alignment:** when line items carry `selectedOptions` and `quantity`, `POST /checkout` (or cart patch endpoints) should echo them on order lines so **post-order recommendations** and **“buy again”** respect the same variant dimension.

**Context object recommendation (`payload` companion):**

- `device`: `type`, `os`, `browser`, `userAgent`
- `session`: `localTimestamp`, `timezone`, `hourOfDay`, `dayOfWeek`
- `acquisition`: `source`, `medium`, `campaign`, `referrer`
- `geo`: coarse IP-derived `country`, `region`, `city` (no precise lat/lng by default)
- `environment`: optional weather snapshot (`condition`, `temperatureBand`)
- `engagement`: optional `scrollDepth`, `viewport`, `pageType`

This context should be generated by a lightweight frontend tracking SDK layer and attached consistently to all event types where policy allows.

#### `POST /events/batch`

Optional later endpoint for batching low-priority frontend telemetry.

### Checkout

#### `POST /checkout`

Frontend demo expects a fake order confirmation shape now, even if the backend initially leaves it mocked.

Request body:

- `customer`
- `shippingAddress`
- `paymentMethod`
- `items`
- `totals`

Response:

- `orderId`
- `status`
- `placedAt`

### Debug And Audit

#### `GET /debug/events`

Returns recent tracked events for demo and diagnostics views.

#### `GET /jobs/{jobId}`

Returns async status aligned with the existing jobs table concept.

#### `GET /debug/recommendations/{decisionId}`

Returns recommendation audit details suitable for a future explanation drawer.

## Entity Shapes

### Product

- `id`
- `slug`
- `name`
- `brand`
- `category` (slug referencing `Category`)
- `price`
- `compareAt`
- `image` (primary hero)
- `description` (short)
- `features` (legacy bullet list; may overlap `specification`)
- `badges`
- `rating`
- `reviewCount`
- `inventoryStatus`
- `personalizationTags`
- optional `viewerReview` (see `GET /catalog/products/{slug}`)
- optional `vertical` — `apparel` | `furniture` | `electronics` | `general` (drives PDP modules + facets)
- optional `freeDelivery` — boolean; **tracked** whenever surfaced
- optional `images[]` — additional gallery URLs
- optional `longDescription` — long-form body for Description tab
- optional `specification[]` — structured spec lines
- optional `dimensions` — `{ display?, lengthCm?, widthCm?, heightCm?, weightG? }`
- optional `department`
- optional `dateFirstAvailable` (ISO date)
- optional `tags[]` — merchandising / filter chips
- optional `colorOptions`, `sizeOptions`, `storageOptions` — `{ id, label }[]` variant axes (**full sizing matrix / inseam ladders** deferred — see `FE_PLAN.md` upcoming phase)

### ProductReview

- `id`
- `productId`
- `authorDisplayName` (or anonymized handle per policy)
- `rating` (1–5)
- `title` (optional)
- `body`
- `createdAt`
- optional `verifiedPurchase`
- `helpfulCount`
- `notHelpfulCount`
- optional `viewerHelpfulVote` for the current caller

### RecommendationRail

- `id`
- `title`
- `subtitle`
- `reason`
- `confidence`
- `fallback`
- `products`

### ProfileSummary

- `customerId`
- `name`
- `segment`
- `topCategories`
- `explicitPreferences`
- `inferredInterests`
- `recentSignals`
- `lastUpdated`

## Open Questions For Backend

- How should **variant availability** (per color × size × warehouse) be represented without exploding payload size—matrix endpoint vs embedded on PDP?
- How much explanation detail can be safely exposed per product or search result?
- Should search and recommendation APIs respond synchronously or with a cached job result abstraction?
- Which endpoints need authenticated identity versus explicit `customerId` in the demo phase?
- How should cold-start behavior be encoded so the frontend can message it clearly?
- Review moderation: pre-publish screening, reporting flow, and whether shoppers can edit/delete their own reviews after submission.
- One review per customer per SKU versus versioned edits, and how aggregate `rating` / `reviewCount` on `Product` are recomputed (sync vs async job).
