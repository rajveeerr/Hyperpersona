# HyperPersona Web App — Frontend Execution Plan

## Summary

This document is the standing implementation plan for the frontend-first HyperPersona demo commerce app. It captures:

- product scope
- demo-specific showcase surfaces
- architecture and coding conventions
- React and UI best-practice expectations
- phase-by-phase implementation details
- backend handoff expectations

The goal is not just to build a nice ecommerce UI. The frontend must make the invisible parts of `plan.md` visible:

- tracked behavior
- consent-aware personalization
- recommendation reasoning
- search explainability
- session memory
- profile inference
- generic vs personalized fallbacks

This document should be sufficient to continue frontend work without re-quoting skills every time.

Companion references:

- `UI_REFERENCE.md` for visual interpretation of current design inspiration
- `API_REQUIREMENTS.md` for backend contract expectations
- `BACKEND_TASKS.md` for deferred backend work

## Goals

### Primary product goal

Build a standalone React storefront that behaves like a real ecommerce experience while proving the recommendation, consent, tracking, profile, and explainability systems planned in the root architecture.

### Demo goal

Help stakeholders understand how the overall platform works by turning hidden system behavior into visible product surfaces.

### Non-goals for this phase

- real payment processing
- real authentication integration
- live backend integration
- production-ready admin catalog workflows
- final visual system extraction from reference material before public design inputs are shared

## Working Principles

This app should follow the intent of:

- `vercel-react-best-practices`
- `web-design-guidelines`
- `software-architecture`

### Architecture principles

- Keep the app modular by business capability, not by technical dumping grounds.
- Keep business logic out of page components.
- Prefer domain-specific names and file ownership.
- Avoid oversized files and split modules before they become hard to reason about.
- Keep UI composition, state orchestration, API contracts, and interaction tracking separate.

### React implementation principles

- Use TanStack Query for server-shaped state from the start, even when responses are mocked.
- Use Zustand only for local interaction state that does not belong in remote cache.
- Use React Hook Form with Zod for forms.
- Use `useDeferredValue` and `startTransition` where input responsiveness or non-urgent updates benefit.
- Avoid waterfall fetching by loading independent resources in parallel.
- Avoid barrel-heavy import structure that widens bundles.
- Keep controlled inputs cheap and avoid excessive rerender chains.

### UI and accessibility principles

- Every flow must be keyboard-complete.
- Focus states must be visible and intentional.
- Empty, error, fallback, and sparse states are required, not optional.
- Inputs must retain value and focus safely.
- Labels must exist for all form fields.
- Buttons must show loading state without losing meaning.
- Mobile targets should remain finger-safe.
- The app should be truthful about when personalization is active versus generic.
- **Motion / animation:** use **Framer Motion** (`import { motion, AnimatePresence, … } from "framer-motion"`) for UI **animations**—hover feedback, springs, enter/exit, layout shifts—not ad hoc CSS keyframes or Tailwind `transition-*` alone for interactive motion. Honor **`prefers-reduced-motion`** (shorter easing or disable transforms; keep essential state changes). Existing example: **`ConsentBanner`** scroll-dismiss; **`ProductGrid`** catalog cell hover (Motion).

## Product Scope

### Shopper flows

1. Discover products on the home page.
2. Browse category and listing pages with sort and filters.
3. Search with personalized ranking cues.
4. Open product detail pages with related products.
5. Read product reviews on the PDP, load more pages of reviews when offered, and engage with UGC by marking reviews **helpful** or **not helpful** (tracked for personalization and explainability).
6. Submit their own product review (star rating plus text), which the platform stores and surfaces back as **their** rating for that SKU; submission and engagement emit typed **`POST /events`** payloads (see `API_REQUIREMENTS.md` and `ReviewTelemetryPayload` in contracts).
7. Add to cart.
8. Add to wishlist.
9. Complete fake checkout.
10. Return to see how those actions could influence future recommendations.

**Catalog richness (contract + demo data in progress):** the API and mocks now support **vertical** (`apparel` | `furniture` | `electronics` | `general`), **free delivery** flag, **multi-image** galleries, **long description**, **dimensions**, **department**, **date first available**, **structured specification lines**, **tags**, and **variant option lists** (`colorOptions`, `sizeOptions`, `storageOptions`). **Listing** supports **pagination**, **department/vertical facets**, **free-delivery filter**, **price range**, and **tag** filters (see `API_REQUIREMENTS.md`). PDP UI should eventually mirror reference **tabbed** layouts (Description, styling ideas, reviews, highlights) plus **Report product**; tab and variant interactions emit **`CommerceTelemetryEventType`** events documented in contracts.

**Upcoming phase — sizing & variant matrix (not yet in UI):** full **apparel sizing** (numeric + letter + inseam ladders, regional sizing, fit models), **furniture configuration** (finish + configuration SKUs), and **electronics** (storage + color bundles) as first-class **availability matrices** with server-side validation; cart line items already conceptually carry `selectedOptions` + `quantity` for recommendations. Until then, **simple option lists** on PDP are placeholders; profile **fit / sizing** fields remain as described in personalization flows below.

### Personalization and trust flows

1. View and update consent.
2. View explicit and inferred profile traits.
3. See why products or results were recommended.
4. Compare personalized versus generic states.
5. Inspect live tracked events and system-facing behavior.

**Future:** from **`/profile`**, optionally maintain a **fit and sizing profile**: fields such as **gender**, **height**, **weight**, **shoe size**, **waist**, **chest**, **hips**, **inseam**, and other **category-aware** measurements or labels the shopper chooses to provide. All saves are **tracked** (`profile_updated` and finer-grained fit events once wired). **Copy requirement:** when personalization consent is on, the UI must **plainly state** that **search ranking, recommendations, and size or variant defaults** may use these attributes **in addition to** browsing and purchase history—so shoppers understand **why** a size or variant might be pre-selected or boosted. If consent is off, do not imply that body or sizing inputs drive the model.

### Demo and storytelling flows

1. Switch personas rapidly for stakeholder demos.
2. Show current session understanding.
3. Show a recommendation audit drawer or panel.
4. Show cold-start and low-signal fallback behavior.
5. Show how a fake order can strengthen future personalization.

## Information Architecture

### Routes

- `/` home
- `/catalog` product listing
- `/search` search results
- `/products/:slug` product detail
- `/wishlist` wishlist
- `/cart` cart
- `/checkout` fake checkout
- `/consent` consent management
- `/profile` profile lab and explainability
- future `/demo` or `/lab` route for comparison tools, personas, and system storytelling surfaces
- future `/admin/catalog-preview` route for catalog freshness storytelling

### Feature ownership

- `catalog`: **`/catalog`** sits on the **default body canvas** (no separate full-bleed story band) so colour matches the rest of chrome; **dashed-pill** category/sort controls (serif labels); **department** pills use a **filled ink chip** when selected so state is obvious; **`ProductGrid`** is the **only** product grid — **hairline lattice** (1px `#e5e5e5` borders: shell `border-l`/`border-t` + cell `border-r`/`border-b`—no fill; same weight as New collection mat) + **`ProductCard`** (single tile implementation site-wide: centered sans title/price, soft product shadow, optional **`accent`** eyebrow for rails/search); **`/wishlist`**, **PDP suggestions**, **home rails**, **`HomePopularSection`**, and **`/search`** all use this grid + card; **editorial New collection** (`EditorialNewCollectionSection`) stays bespoke lookbook tiles, not `ProductCard`; **`CatalogToolbarSkeleton` / `CatalogProductGridSkeleton`** while categories or results load; **PDP** uses **`ProductDetailSkeleton`** until `getProduct` resolves and **`PdpSuggestionsRailsSkeleton`** for suggestion rails; **`ScrollToTop`** in `AppLayout` scrolls **`window` to 0** on **`pathname` or `search`** change (pagination, filters, slug); **facets** (vertical, free delivery, price range, tags), **pagination**, **reviews** (list + pagination, helpful / not helpful, compose + submit, client telemetry aligned with `ReviewTelemetryEventType`); **rich PDP fields** per `Product` in contracts (images, dimensions, specs, variant option lists); **future:** full variant **matrix** + **sizing** UI, default size prefill from profile when consented, tabbed PDP (“Product details” reference), **Report product** flow
- `search`: query state, result ranking surface, explainability surface; **`/search`** shares **catalog grid + skeleton** treatment when a query is active (`UI_REFERENCE`)
- `recommendations`: rails, reason chips, fallback states, audit drawer
- `cart`: cart state, quantity changes, pricing summary, intent events
- `wishlist`: save-for-later state and durable preference behavior; **`/wishlist`** uses the same **`ProductGrid` + `ProductCard`** as **`/catalog`**
- `checkout`: fake order flow and completion loop
- **future `orders` / `fulfillment`:** order list, **tracking** links, **change delivery address** while eligible (`PATCH /me/orders/{id}/delivery-address`), saved **addresses** book (`GET` / `PATCH /me/addresses`) — contracts and MSW stubs exist; dedicated UI pages are optional for demo
- `consent`: controls, mode switching, trust copy; **floating consent toast** (`ConsentBanner`) uses **Framer Motion** — **visible at scroll top**; past a few pixels of scroll it **slides off to the right** and fades; **scrolling back to the top** brings it **back in** with the same motion (short transition when `prefers-reduced-motion: reduce`)
- `profile`: explicit preferences, inferred interests, current segment, recent intent; **future:** fit / sizing / body-measurement fields (optional, user-editable), surfaced next to explainability so “why this size” stays auditable
- `events`: tracking client, event feed, diagnostics
- `personas`: quick context switching for demo scenarios
- `session-memory`: current session understanding card and summary

## Application Architecture

### Workspace shape

- root `package.json` owns the JS workspace because the repository now contains a standalone web app
- `apps/web` is the frontend application boundary
- root remains shared only for workspace-level concerns, not feature code

### App structure

Recommended structure to preserve:

- `src/app`
  - router
  - providers
  - application shell
- `src/pages`
  - route entrypoints only
- `src/features`
  - bounded contexts like catalog, cart, profile, consent, recommendations
- `src/shared`
  - frontend-wide contracts, config, low-level UI primitives, theme tokens
- `src/mocks`
  - mock handlers, datasets, scenario configuration
- `src/test`
  - setup and focused tests

### State ownership rules

#### Remote or server-shaped state

Use TanStack Query:

- categories
- product listing data
- product detail data
- paginated product reviews (`GET /catalog/products/{slug}/reviews`) and review mutations
- search responses
- recommendation rails
- consent record
- profile data
- explanation data
- future diagnostics data
- orders list and address book (**when wired**)
- **future:** product variant **matrix** and per-warehouse availability per SKU; persisted fit / sizing slice on `ProfileSummary` (or dedicated endpoint) once backend extends `API_REQUIREMENTS.md`

#### Local interaction state

Use Zustand:

- cart items
- wishlist items
- current persona
- debug stream cache
- audit drawer open state
- comparison-mode toggles

#### URL state

Keep in URL when it affects navigation or shareability:

- search query
- category
- sort
- filters
- comparison mode

#### Form state

Use React Hook Form + Zod:

- checkout
- consent forms
- explicit preference editing
- **future:** profile fit & sizing editor (Zod schemas per field group: footwear vs apparel vs generic)
- future account or auth entry forms

## Design-System Strategy

### Baseline

The current baseline is a warm editorial commerce direction. It is intentionally a placeholder design system, not the final design language.

### Token rules

- All brand values come from theme tokens, never ad hoc feature CSS.
- Use semantic tokens instead of raw values inside components.
- Typography, spacing, radius, elevation, and motion all need tokenized ownership.
- Introduce explicit state tokens for success, warning, error, info, and personalization-highlight states.

### Styling implementation (this repo)

- The storefront uses **Tailwind CSS v4** with semantic tokens declared in **`@theme`** inside `apps/web/src/shared/styles/app.css` (loaded from `apps/web/src/main.tsx`).
- Prefer Tailwind utilities backed by those tokens; reuse composed class strings from `apps/web/src/shared/ui/tw.ts` where it keeps feature code readable. See `UI_REFERENCE.md` for how reference assets map into this layer.

### Typography system (editorial commerce reference)

- **Display / serif:** **Playfair Display** (`--font-display`) — high-contrast headlines, product names, wordmarks, newsletter titles. Prefer **`tw.displayH1`**, **`tw.displayH2`**, **`tw.displayProductTitle`**, **`tw.displayWordmarkNav`**, **`tw.displayWordmarkFooter`**, **`tw.displayNewsletterHeading`**, **`tw.editorialStoryHeadline`**, **`tw.storyTitle`** instead of raw `font-display` + manual `tracking-*` in feature components.
- **UI / body:** **Inter** (`--font-body`) — navigation, forms, cards, explanatory copy. Root `body` uses **`tracking-body`** for the slight negative tracking used in reference body blocks.
- **Tracking tokens:** `--tracking-display`, `--tracking-display-tight`, `--tracking-body`, `--tracking-ui-wide` in `app.css`; map to utilities `tracking-display`, `tracking-display-tight`, `tracking-body`, `tracking-ui-wide`.
- **Rationale:** Matches luxury PDP references (tight serif kerning, soft black `text-ink`, warm grounds). When reference screens update, adjust tokens and `tw.*` once rather than per-page.

### Design inspiration workflow

Create and maintain `apps/web/design-inspo/` as the drop zone for:

- screenshots
- product videos
- moodboards
- references

Use it for manual inspiration immediately.

Maintain `apps/web/UI_REFERENCE.md` as the design translation layer between raw reference assets and the real token/component system.

Use `extract-design-system` later only when a public website URL is provided and we explicitly want starter token extraction. That skill is not appropriate for local images or videos alone.

Current reference direction from local assets:

- editorial and premium rather than marketplace-heavy
- oversized serif typography
- quiet utility navigation
- warm ivory surfaces and restrained earthy accents
- product photography with generous negative space
- pill controls with hairline borders

### Future extraction workflow

When a public design reference is available:

1. extract design primitives into generated artifacts
2. review normalized tokens
3. selectively map them into the existing semantic theme
4. never overwrite the app’s styling blindly

## Demo-Specific Showcase Modules

These are the most important additions for showcasing the actual system in `plan.md`.

### High-priority showcase modules

- **Live personalization timeline**
  - Show “viewed X, searched Y, added Z, checked out A”
  - Visibly connect timeline activity to recommendation/search changes
- **Why this was recommended panel**
  - Show the main signal groups behind each rail or product
- **Consent impact demo**
  - Toggle personalized versus generic experience instantly
- **Before vs after comparison mode**
  - Side-by-side generic versus personalized ranking/recommendations
- **Profile lab**
  - Show explicit preferences, inferred interests, category affinity, recent intent, and editable values
- **Recommendation audit drawer**
  - Show reason, confidence, fallback status, and source signal groups
- **Live event/debug stream**
  - Show every emitted frontend event in demo/dev mode
- **Session memory showcase**
  - Summarize what the system currently believes the customer is doing
- **Search explainability**
  - Explain why a result ranked high, not only why a product was recommended
- **Empty/fallback states**
  - Cold start
  - no consent
  - low signal
  - no results
- **Fake order outcome loop**
  - Show how fake purchase completion would sharpen future suggestions
- **Demo personas switcher**
  - Preloaded personas like budget shopper, outdoor enthusiast, premium buyer, gift shopper
- **Catalog freshness story**
  - Placeholder admin/demo surface showing item ingestion to searchable/recommendable lifecycle
- **Trust and safety messaging**
  - Make data usage and revocation behavior understandable
- **Fit, sizing, and variant explainability (future)**
  - Tie PDP size/variant suggestions to profile inputs when personalization is on, and show **which signals** influenced the suggestion in audit or profile lab copy

### Top 6 for pure demo impact

1. Side-by-side generic vs personalized view
2. Consent toggle with instant UX change
3. Profile lab
4. Why-this-was-recommended / why-this-ranked UI
5. Live event stream
6. Demo persona switcher

## API Contract Expectations

The frontend is being shaped around a realistic API surface from the start. Detailed API handoff lives in `API_REQUIREMENTS.md`, but the implementation should assume:

- auth-aware user context
- customer events with async processing
- searchable catalog resources
- recommendation surfaces with explanations
- profile and consent endpoints
- debug and audit views

## Tracking Coverage

The frontend must emit event-shaped payloads for:

- page view
- collection view
- category view
- product impression
- product click
- recommendation impression
- recommendation click
- search submit
- filter change
- sort change
- add to cart
- remove from cart
- wishlist add
- wishlist remove
- checkout started
- checkout step completed
- checkout completed
- consent updated
- profile updated
- persona switched
- **`product_tile_clicked`** (with `freeDelivery`, `vertical`, `source`) alongside legacy `product_click` where needed
- **`pdp_*`** events from `CommerceTelemetryEventType` (tabs, variants, quantity, free-delivery badge impression, report click)
- **future:** combined `sku_option_changed` for high-frequency variant streams, `profile_fit_updated` / `profile_sizing_saved`

### Frontend tracking SDK module (add/maintain)

Maintain a lightweight frontend event SDK layer instead of ad hoc `trackEvent` calls in feature code.

Minimum module expectations:
- single `track(eventType, payload, options)` API
- shared context enrichment (below) before dispatch
- consent-aware gating and redaction hooks
- retry + offline queue + batch flush strategy for non-critical events
- typed event contracts (reuse `contracts.ts` event payload types)
- transport adapters (`/events` now, future `/events/batch`)

### Contextual data enrichment requirements

In addition to feature payloads, include contextual metadata for every trackable interaction where policy allows:

- device and client: device type (mobile/tablet/desktop), OS, browser, user agent
- session timing: local timestamp, hour-of-day, day-of-week, timezone
- acquisition context: traffic source / medium / campaign (`utm_*`, referrer domain, "google", "tiktok", etc.)
- location context: coarse geo from IP lookup (country/region/city), no precise GPS by default
- environmental context (optional): local weather snapshot
- commerce behavior: scroll depth on listing/search/PDP, product impressions, final purchase, returns, search query terms

Privacy constraints:
- capture only coarse, necessary context for personalization/analytics
- gate storage/processing by consent scope
- avoid storing raw sensitive PII in event payloads

## Detailed Phase Plan

### Phase 1 — foundation and believable shopper experience

#### Goal

Stand up a credible ecommerce shell with real interaction flows and a frontend architecture that can survive backend integration.

#### Deliverables

- React + TypeScript app scaffold
- routing and provider setup
- design tokens and base theme
- mock API layer with MSW (**catalog pagination + facets + richer `Product` demo rows**; stub **orders** and **addresses**)
- home, catalog, PDP, cart, wishlist, checkout, consent, profile routes
- initial tracking hooks and debug event panel
- frontend plan and backend handoff docs
- standalone frontend Docker setup
- `design-inspo/` directory

#### Implementation notes

- Start simple, but keep contracts realistic.
- Ensure core actions already emit events.
- Preserve route-level ownership and avoid fat page components.
- Use images with dimensions/aspect handling to avoid layout shift.

### Phase 2 — personalization storytelling surfaces

#### Goal

Make the intelligence and system behavior visible.

#### Deliverables

- live personalization timeline
- search explanation module
- recommendation audit drawer
- session memory card
- cold-start and no-consent fallback UI
- recommendation reason chips and confidence cues
- stronger event instrumentation coverage
- **future stretch:** profile section for **fit / sizing** with consent-aligned disclosure that these fields may personalize **search, recommendations, and default variant or size**; first-pass “why this default size” hint on PDP when data exists

#### Implementation notes

- Comparison views should share one contract but render two modes.
- Fallback state language must be explicit and reassuring.
- Audit and explanation surfaces should not feel like developer-only junk; they should be polished demo artifacts.

### Phase 3 — demo acceleration surfaces

#### Goal

Make the app easier to demo repeatedly with different narratives.

#### Deliverables

- demo persona switcher
- side-by-side generic vs personalized comparison mode
- fake order outcome loop visualization
- placeholder catalog freshness story screen
- scenario presets for stakeholder walkthroughs

#### Implementation notes

- Personas should drive profile, consent, and behavioral context together.
- Comparisons must be obvious enough for non-technical stakeholders.

### Phase 4 — visual refinement from references

#### Goal

Elevate the visual system once inspiration assets or a public reference URL are available.

#### Deliverables

- curated design inspiration library under `design-inspo/`
- token refinement
- updated layout, typography, illustration direction, and motion language
- visual QA pass against `web-design-guidelines`

#### Implementation notes

- If reference is local media, use it manually as inspiration.
- If reference is a public site, use `extract-design-system` carefully to seed token refinement.

### Phase 5 — backend integration readiness

#### Goal

Make the app integration-ready without rewrites.

#### Deliverables

- swap-ready service layer
- stable query keys
- normalized request/response contracts
- error envelopes and empty states for real backend conditions
- auth-aware route preparation

#### Implementation notes

- Keep MSW handlers shaped like the real API from day 1.
- Do not let component code know whether data is mocked or real.

## Best Practices To Preserve In Implementation

### Performance

- Keep search inputs responsive with deferred rendering.
- Load independent homepage data in parallel.
- Avoid unnecessary subscriptions to cart or wishlist slices.
- Use lazy loading for below-the-fold media.
- Keep bundle expansion in check as showcase modules grow.

### Maintainability

- Files over roughly 200 lines should be reviewed for splitting.
- Keep feature-specific domain logic within that feature boundary.
- Avoid generic dumping-ground files.
- Prefer reusable, composable UI primitives rather than duplicated patterns.

### Trust and UX quality

- The app must clearly say when it is using personalized behavior.
- When shoppers save **fit, sizing, or body-related profile fields**, paired **consent** and **profile** copy must state that **personalization** (with the personalization scope enabled) may use that data for **ranking, recommendations, and size or variant defaults**—not only clickstream history.
- Every error or blocked state must explain what the user can do next.
- Recommendation confidence or explanation should never imply certainty when data is weak.
- Revoking consent must immediately affect visible personalization state.

## Acceptance Criteria

- App runs as a standalone React SPA from `apps/web`.
- Users can browse, wishlist, cart, and fake-checkout products.
- Core actions emit visible tracked events.
- Consent state visibly changes recommendation and search behavior.
- Profile changes visibly change how the app describes the user.
- The plan covers implementation detail deeply enough to continue without re-stating the referenced skills.
- The demo surfaces make the underlying system in `plan.md` understandable to non-engineers.
