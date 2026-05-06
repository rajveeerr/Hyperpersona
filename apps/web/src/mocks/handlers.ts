import { delay, http, HttpResponse } from "msw";

import { homeRails, productRails } from "@/mocks/data/recommendations";
import { seedReviewsBySlug } from "@/mocks/data/productReviews";
import { initialConsent, initialProfile, explanationRecord } from "@/mocks/data/profile";
import { categories, products } from "@/mocks/data/products";
import type {
  CatalogFacetGroup,
  CheckoutInput,
  ConsentRecord,
  CreateProductReviewBody,
  DeliveryAddress,
  DeliveryAddressListResponse,
  IngestBatchResponse,
  IngestEventRequest,
  IngestEventResult,
  OrderListResponse,
  OrderSummary,
  Product,
  ProductListResponse,
  ProductReview,
  ProductVertical,
  ProfileSummary,
  ReviewHelpfulVote,
  SetReviewHelpfulBody,
  TrackedEvent,
  ViewerProductReview,
} from "@/shared/api/contracts";

let profileState: ProfileSummary = initialProfile;
let trackedEvents: TrackedEvent[] = [];

/**
 * Per-customer consent records keyed by `customer_id` — mirrors how the real
 * backend stores them in DynamoDB. New customers (post-register) intentionally
 * have **no** entry here so `GET /api/consent` returns 404 like the real API.
 *
 * The legacy demo customer (`demo-customer-1`) is preseeded so unauthenticated
 * MSW flows that fall back to that id keep working.
 */
const consentByCustomer = new Map<string, ConsentRecord>([
  [initialConsent.customer_id, { ...initialConsent }],
]);

/**
 * In-memory auth table for the dev MSW worker. Mirrors the response shape of
 * `POST /register` / `POST /login` in `server/src/routes/auth.py` so the FE
 * can be developed offline. The "JWT" is a random opaque string — fine for
 * the mock since the mock endpoints do not validate it; when pointing at the
 * real backend, MSW is bypassed and the real JWT is issued instead.
 */
type MockAuthRecord = { customer_id: string; email: string; password: string };
const mockAuthRecords: MockAuthRecord[] = [];
/** Bearer-token → customer_id index. Populated on register/login, used by
 * authenticated handlers to resolve identity from the `Authorization` header
 * the same way the real `JWTAuthMiddleware` does. */
const tokenToCustomer = new Map<string, string>();
const MOCK_TOKEN_EXPIRES_IN = 60 * 60 * 24; // seconds — 24h, matches default JWT TTL

function findAuthRecord(email: string): MockAuthRecord | undefined {
  const normalized = email.toLowerCase();
  return mockAuthRecords.find((record) => record.email === normalized);
}

function mintMockToken(customerId: string): string {
  // Opaque marker; the mock handlers don't verify the signature, but we DO
  // index it back to the customer so per-identity state (consent, etc.)
  // works correctly across handlers.
  const token = `mock.${crypto.randomUUID()}.${Date.now()}`;
  tokenToCustomer.set(token, customerId);
  return token;
}

/** Resolve customer_id from the `Authorization: Bearer <token>` header. */
function customerIdFromAuth(request: Request): string | null {
  const header = request.headers.get("authorization") ?? "";
  if (!header.toLowerCase().startsWith("bearer ")) return null;
  const token = header.slice(7).trim();
  return tokenToCustomer.get(token) ?? null;
}

/**
 * Returns the consent record relevant to the request — either the auth'd
 * customer's record, or the legacy demo record for unauthenticated mock
 * flows. Callers that need to enforce auth should branch on
 * `customerIdFromAuth` directly instead.
 */
function effectiveConsent(request: Request): ConsentRecord | null {
  const customerId = customerIdFromAuth(request) ?? initialConsent.customer_id;
  return consentByCustomer.get(customerId) ?? null;
}

/**
 * 401 envelope mirrors the FastAPI JWT middleware response shape
 * (`{ error: "..." }`) so the FE error mapper can read both server reality
 * and mock identically.
 */
function unauthorized() {
  return HttpResponse.json({ error: "missing or invalid bearer token" }, { status: 401 });
}

function cloneReviewSeeds(): Record<string, ProductReview[]> {
  const out: Record<string, ProductReview[]> = {};
  for (const [slug, list] of Object.entries(seedReviewsBySlug)) {
    out[slug] = list.map((row) => ({ ...row }));
  }
  return out;
}

/** Mutable PDP review threads + current shopper’s submitted review per slug (demo session). */
const reviewsBySlug: Record<string, ProductReview[]> = cloneReviewSeeds();
const viewerReviewBySlug: Record<string, ViewerProductReview | null> = {};

function mergeViewerReview(slug: string, product: (typeof products)[number]) {
  return { ...product, viewerReview: viewerReviewBySlug[slug] ?? null };
}

function applyHelpfulVote(review: ProductReview, vote: ReviewHelpfulVote) {
  let helpfulCount = review.helpfulCount;
  let notHelpfulCount = review.notHelpfulCount;
  const prev = review.viewerHelpfulVote ?? null;
  if (prev === "helpful") helpfulCount -= 1;
  if (prev === "not_helpful") notHelpfulCount -= 1;
  if (vote === "helpful") helpfulCount += 1;
  if (vote === "not_helpful") notHelpfulCount += 1;
  return { ...review, helpfulCount, notHelpfulCount, viewerHelpfulVote: vote };
}

function matchesQuery(text: string, search: string) {
  return text.toLowerCase().includes(search.toLowerCase());
}

function productVertical(p: Product): ProductVertical {
  return p.vertical ?? "general";
}

type FilterSkip = {
  /** When true, ignore the `vertical` URL filter while computing the slice (used for the vertical facet group). */
  vertical?: boolean;
  /** When true, ignore the `freeDelivery` URL filter while computing the slice (used for the delivery facet). */
  freeDelivery?: boolean;
};

/**
 * Product slice used for list + facet aggregation (no sort / pagination).
 *
 * `skip` lets callers exclude a facet's own selection so that group's counts reflect
 * "what would happen if you switched within this facet" — standard multi/boolean facet
 * semantics (OR within a facet group, AND across groups).
 */
function applyProductFilters(url: URL, skip: FilterSkip = {}): Product[] {
  const category = url.searchParams.get("category");
  const search = url.searchParams.get("q");
  const brand = url.searchParams.get("brand");
  const vertical = url.searchParams.get("vertical");
  const freeDelivery = url.searchParams.get("freeDelivery");
  const tagsParam = url.searchParams.get("tags");
  const minPrice = url.searchParams.get("minPrice");
  const maxPrice = url.searchParams.get("maxPrice");

  let filtered: Product[] = [...products];

  if (category) {
    filtered = filtered.filter((product) => product.category === category);
  }

  if (search) {
    filtered = filtered.filter((product) =>
      [product.name, product.brand, product.description, ...(product.tags ?? []), ...product.features].some((field) =>
        matchesQuery(field, search),
      ),
    );
  }

  if (brand) {
    filtered = filtered.filter((p) => p.brand.toLowerCase() === brand.toLowerCase());
  }

  if (vertical && !skip.vertical) {
    const wanted = vertical.split(",").map((v) => v.trim()) as ProductVertical[];
    filtered = filtered.filter((p) => wanted.includes(productVertical(p)));
  }

  if (freeDelivery === "true" && !skip.freeDelivery) {
    filtered = filtered.filter((p) => p.freeDelivery === true);
  }

  if (minPrice) {
    const n = Number(minPrice);
    if (!Number.isNaN(n)) filtered = filtered.filter((p) => p.price >= n);
  }
  if (maxPrice) {
    const n = Number(maxPrice);
    if (!Number.isNaN(n)) filtered = filtered.filter((p) => p.price <= n);
  }

  if (tagsParam) {
    const wanted = tagsParam.split(",").map((t) => t.trim().toLowerCase()).filter(Boolean);
    if (wanted.length) {
      filtered = filtered.filter((p) => {
        const hay = [...(p.tags ?? []), ...p.personalizationTags].map((x) => x.toLowerCase());
        return wanted.some((t) => hay.some((h) => h.includes(t)));
      });
    }
  }

  return filtered;
}

/**
 * Builds facet groups using **per-group** filter slices: counts within a group ignore that
 * group's own selection so non-active values don't drop to zero when one is selected.
 */
function buildFacets(url: URL): CatalogFacetGroup[] {
  const verticalSlice = applyProductFilters(url, { vertical: true });
  const deliverySlice = applyProductFilters(url, { freeDelivery: true });
  const fullSlice = applyProductFilters(url);
  const count = (slice: Product[], pred: (p: Product) => boolean) => slice.filter(pred).length;

  return [
    {
      id: "vertical",
      label: "Department",
      facetType: "multi",
      values: [
        { value: "apparel", label: "Apparel & accessories", count: count(verticalSlice, (p) => productVertical(p) === "apparel") },
        { value: "furniture", label: "Furniture & lighting", count: count(verticalSlice, (p) => productVertical(p) === "furniture") },
        { value: "electronics", label: "Electronics", count: count(verticalSlice, (p) => productVertical(p) === "electronics") },
        { value: "general", label: "Everyday & other", count: count(verticalSlice, (p) => productVertical(p) === "general") },
      ],
    },
    {
      id: "freeDelivery",
      label: "Delivery",
      facetType: "boolean",
      values: [{ value: "true", label: "Free delivery", count: count(deliverySlice, (p) => p.freeDelivery === true) }],
    },
    {
      id: "price",
      label: "Price",
      facetType: "range",
      min: fullSlice.length ? Math.min(...fullSlice.map((p) => p.price)) : 0,
      max: fullSlice.length ? Math.max(...fullSlice.map((p) => p.price)) : 0,
    },
  ];
}

function filterProducts(url: URL, personalized: boolean): ProductListResponse {
  const sort = url.searchParams.get("sort") ?? "featured";
  const page = Math.max(1, Number(url.searchParams.get("page") ?? "1"));
  const pageSize = Math.min(48, Math.max(1, Number(url.searchParams.get("pageSize") ?? "12")));

  const filtered = applyProductFilters(url);

  if (sort === "price-asc") {
    filtered.sort((a, b) => a.price - b.price);
  } else if (sort === "price-desc") {
    filtered.sort((a, b) => b.price - a.price);
  } else if (sort === "rating") {
    filtered.sort((a, b) => b.rating - a.rating);
  }

  const total = filtered.length;
  const start = (page - 1) * pageSize;
  const items = filtered.slice(start, start + pageSize);

  return {
    items,
    total,
    page,
    pageSize,
    personalized,
  };
}

function isPersonalized(request: Request): boolean {
  const consent = effectiveConsent(request);
  return Boolean(consent?.scopes.includes("personalization"));
}

const seedAddresses: DeliveryAddress[] = [
  {
    id: "addr-home",
    label: "Home",
    line1: "12 Rue Editoriale",
    city: "Montreal",
    region: "QC",
    postalCode: "H2X 1A1",
    country: "CA",
    isDefault: true,
  },
  {
    id: "addr-office",
    label: "Office",
    line1: "400 King St W",
    line2: "Suite 900",
    city: "Toronto",
    region: "ON",
    postalCode: "M5V 1K1",
    country: "CA",
  },
];

const addressBook: DeliveryAddress[] = seedAddresses.map((a) => ({ ...a }));

const ordersState: OrderSummary[] = [
  {
    id: "ord-demo-1001",
    status: "shipped",
    placedAt: new Date(Date.now() - 86400000 * 5).toISOString(),
    total: 308,
    currency: "CAD",
    destinationLabel: "Home · Montreal",
    lineCount: 2,
    trackingUrl: "https://example.com/track/ord-demo-1001",
    deliveryAddressId: "addr-home",
    lines: [
      { productId: "prod-1", slug: "altitude-shell-jacket", name: "Altitude Shell Jacket", quantity: 1, unitPrice: 220 },
      { productId: "prod-7", slug: "ridge-merino-sock", name: "Ridge Merino Sock", quantity: 2, unitPrice: 24 },
    ],
  },
  {
    id: "ord-demo-1002",
    status: "delivered",
    placedAt: new Date(Date.now() - 86400000 * 40).toISOString(),
    total: 128,
    currency: "CAD",
    destinationLabel: "Office · Toronto",
    lineCount: 1,
    deliveryAddressId: "addr-office",
    lines: [{ productId: "prod-11", slug: "arc-desk-lamp", name: "Arc Desk Lamp", quantity: 1, unitPrice: 128 }],
  },
];

export const handlers = [
  // --- Auth (mirrors server/src/routes/auth.py) ---
  http.post("/api/register", async ({ request }) => {
    await delay(180);
    const body = (await request.json()) as { email?: string; password?: string };
    const email = (body.email ?? "").trim().toLowerCase();
    const password = body.password ?? "";
    if (!email.includes("@") || password.length < 8) {
      return HttpResponse.json({ detail: "validation_error" }, { status: 422 });
    }
    if (findAuthRecord(email)) {
      return HttpResponse.json({ detail: "email already registered" }, { status: 409 });
    }
    const customer_id = crypto.randomUUID();
    mockAuthRecords.push({ customer_id, email, password });
    return HttpResponse.json({
      customer_id,
      email,
      token: mintMockToken(customer_id),
      token_type: "bearer",
      expires_in: MOCK_TOKEN_EXPIRES_IN,
    });
  }),
  http.post("/api/login", async ({ request }) => {
    await delay(220);
    const body = (await request.json()) as { email?: string; password?: string };
    const email = (body.email ?? "").trim().toLowerCase();
    const password = body.password ?? "";
    const record = findAuthRecord(email);
    if (!record || record.password !== password) {
      return HttpResponse.json({ detail: "invalid email or password" }, { status: 401 });
    }
    return HttpResponse.json({
      customer_id: record.customer_id,
      email: record.email,
      token: mintMockToken(record.customer_id),
      token_type: "bearer",
      expires_in: MOCK_TOKEN_EXPIRES_IN,
    });
  }),

  http.get("/api/catalog/categories", async () => {
    await delay(150);
    return HttpResponse.json(categories);
  }),
  http.get("/api/catalog/facets", async ({ request }) => {
    await delay(200);
    return HttpResponse.json(buildFacets(new URL(request.url)));
  }),
  http.get("/api/catalog/products", async ({ request }) => {
    await delay(240);
    return HttpResponse.json(filterProducts(new URL(request.url), isPersonalized(request)));
  }),
  http.get("/api/catalog/popular", async () => {
    await delay(130);
    const sorted = [...products].sort((a, b) => b.reviewCount - a.reviewCount).slice(0, 6);
    return HttpResponse.json(sorted);
  }),
  http.get("/api/catalog/products/:slug", async ({ params }) => {
    await delay(180);
    const slug = String(params.slug);
    const product = products.find((item) => item.slug === slug);

    if (!product) {
      return new HttpResponse(null, { status: 404 });
    }

    return HttpResponse.json(mergeViewerReview(slug, product));
  }),
  http.get("/api/catalog/products/:slug/reviews", async ({ params, request }) => {
    await delay(160);
    const slug = String(params.slug);
    const url = new URL(request.url);
    const page = Math.max(1, Number(url.searchParams.get("page") ?? "1"));
    const pageSize = Math.min(50, Math.max(1, Number(url.searchParams.get("pageSize") ?? "10")));
    const all = reviewsBySlug[slug] ?? [];
    const total = all.length;
    const start = (page - 1) * pageSize;
    const items = all.slice(start, start + pageSize);
    return HttpResponse.json({ items, page, pageSize, total });
  }),
  http.post("/api/catalog/products/:slug/reviews", async ({ params, request }) => {
    await delay(200);
    const slug = String(params.slug);
    const product = products.find((item) => item.slug === slug);
    if (!product) {
      return new HttpResponse(null, { status: 404 });
    }
    if (viewerReviewBySlug[slug]) {
      return HttpResponse.json({ error: "already_reviewed", message: "Update flow not implemented in demo." }, { status: 409 });
    }
    const body = (await request.json()) as CreateProductReviewBody;
    if (body.rating < 1 || body.rating > 5 || typeof body.body !== "string" || body.body.trim().length < 4) {
      return HttpResponse.json({ error: "validation_error" }, { status: 400 });
    }
    const review: ProductReview = {
      id: `rev-${slug}-${Date.now()}`,
      productId: product.id,
      authorDisplayName: "You",
      rating: body.rating,
      title: body.title,
      body: body.body.trim(),
      createdAt: new Date().toISOString(),
      verifiedPurchase: false,
      helpfulCount: 0,
      notHelpfulCount: 0,
      viewerHelpfulVote: null,
    };
    if (!reviewsBySlug[slug]) reviewsBySlug[slug] = [];
    reviewsBySlug[slug] = [review, ...reviewsBySlug[slug]];
    const viewerReview: ViewerProductReview = {
      id: review.id,
      rating: review.rating,
      title: review.title,
      body: review.body,
      createdAt: review.createdAt,
    };
    viewerReviewBySlug[slug] = viewerReview;
    return HttpResponse.json({ review, viewerReview });
  }),
  http.put("/api/catalog/products/:slug/reviews/:reviewId/helpful", async ({ params, request }) => {
    await delay(120);
    const slug = String(params.slug);
    const reviewId = String(params.reviewId);
    const body = (await request.json()) as SetReviewHelpfulBody;
    const list = reviewsBySlug[slug];
    if (!list) {
      return new HttpResponse(null, { status: 404 });
    }
    const idx = list.findIndex((r) => r.id === reviewId);
    if (idx === -1) {
      return new HttpResponse(null, { status: 404 });
    }
    const updated = applyHelpfulVote(list[idx], body.vote);
    list[idx] = updated;
    return HttpResponse.json({
      reviewId: updated.id,
      helpfulCount: updated.helpfulCount,
      notHelpfulCount: updated.notHelpfulCount,
      viewerHelpfulVote: body.vote,
    });
  }),
  http.get("/api/search", async ({ request }) => {
    await delay(220);
    return HttpResponse.json(filterProducts(new URL(request.url), isPersonalized(request)));
  }),
  http.get("/api/recommendations/home", async ({ request }) => {
    await delay(160);
    return HttpResponse.json(
      isPersonalized(request)
        ? homeRails
        : homeRails.map((rail) => ({
            ...rail,
            fallback: true,
            confidence: 0.52,
            reason: "Personalization is off, so these are generic best-performing products.",
          })),
    );
  }),
  http.get("/api/recommendations/pdp", async () => {
    await delay(140);
    return HttpResponse.json(productRails);
  }),
  http.get("/api/recommendations/cart", async () => {
    await delay(140);
    return HttpResponse.json(productRails);
  }),
  http.get("/api/recommendations/profile", async () => {
    await delay(160);
    return HttpResponse.json(homeRails);
  }),
  http.get("/api/consent", async ({ request }) => {
    // Mirrors `GET /consent` in server/src/routes/consent.py. JWT-derived,
    // 404 when the customer has no record yet.
    await delay(90);
    const customerId = customerIdFromAuth(request);
    if (!customerId) return unauthorized();
    const record = consentByCustomer.get(customerId);
    if (!record) {
      return HttpResponse.json({ detail: "consent record not found" }, { status: 404 });
    }
    return HttpResponse.json(record);
  }),
  http.post("/api/consent", async ({ request }) => {
    // Mirrors `POST /consent` (`ConsentUpsertRequest`) in server/src/routes/consent.py.
    await delay(120);
    const customerId = customerIdFromAuth(request);
    if (!customerId) return unauthorized();
    const body = (await request.json()) as { scopes: string[]; data_retention_days?: number };
    if (!Array.isArray(body.scopes)) {
      return HttpResponse.json({ detail: "validation_error" }, { status: 422 });
    }
    const next: ConsentRecord = {
      customer_id: customerId,
      scopes: [...new Set(body.scopes)].sort(),
      data_retention_days: body.data_retention_days ?? 90,
      last_updated: new Date().toISOString(),
    };
    consentByCustomer.set(customerId, next);
    return HttpResponse.json(next);
  }),
  http.get("/api/me/profile", async () => {
    await delay(120);
    return HttpResponse.json(profileState);
  }),
  http.patch("/api/me/preferences", async ({ request }) => {
    const body = (await request.json()) as {
      explicitPreferences: ProfileSummary["explicitPreferences"];
    };
    profileState = {
      ...profileState,
      explicitPreferences: body.explicitPreferences,
      lastUpdated: new Date().toISOString(),
    };
    return HttpResponse.json(profileState);
  }),
  http.get("/api/me/explanations", async () => {
    await delay(100);
    return HttpResponse.json(explanationRecord);
  }),
  /**
   * Bulk event ingest. Mirrors `POST /events/batch` in
   * `server/src/routes/events.py`:
   *   - Requires JWT (we resolve `customer_id` from `Authorization`).
   *   - Treats `client_event_id` as the idempotency key — repeated entries in
   *     the same batch produce a single result.
   *   - Drops the entire batch with `status: "rejected"` per row when the
   *     authenticated user has not granted `personalization` scope, matching
   *     the server's consent gate.
   *   - Returns `IngestBatchResponse` with per-event status so the FE
   *     tracker can ack durable rows and stop retrying rejected ones.
   */
  http.post("/api/events/batch", async ({ request }) => {
    const customerId = customerIdFromAuth(request);
    if (!customerId) return unauthorized();

    const body = (await request.json().catch(() => null)) as
      | { events?: IngestEventRequest[] }
      | null;
    const events = Array.isArray(body?.events) ? body!.events : [];
    if (events.length === 0) {
      return HttpResponse.json({ accepted: 0, rejected: 0, results: [] } satisfies IngestBatchResponse);
    }

    const consent = consentByCustomer.get(customerId);
    const personalizationGranted = (consent?.scopes ?? []).includes("personalization");

    const seen = new Set<string>();
    const results: IngestEventResult[] = [];
    let accepted = 0;
    let rejected = 0;

    for (const event of events) {
      if (!event?.client_event_id) {
        // Reject malformed rows individually instead of failing the whole batch.
        rejected += 1;
        results.push({
          client_event_id: event?.client_event_id ?? `unknown-${crypto.randomUUID()}`,
          status: "rejected",
          reason: "missing_client_event_id",
        });
        continue;
      }
      if (seen.has(event.client_event_id)) {
        // Idempotency dedupe within a single batch — same as server.
        continue;
      }
      seen.add(event.client_event_id);

      if (!personalizationGranted) {
        rejected += 1;
        results.push({
          client_event_id: event.client_event_id,
          status: "rejected",
          reason: "missing_personalization_scope",
        });
        continue;
      }

      const eventId = `evt_${event.client_event_id}`;
      const jobId = `evt_${event.client_event_id}`;
      results.push({
        client_event_id: event.client_event_id,
        status: "queued",
        event_id: eventId,
        job_id: jobId,
      });
      accepted += 1;

      // Mirror to the debug-events surface so the existing dev panel still
      // shows what's being uploaded under the auth'd identity.
      const traceRow: TrackedEvent = {
        event_id: eventId,
        event_type: event.event_type,
        payload: event.payload,
        status: "sent",
        created_at: new Date().toISOString(),
      };
      trackedEvents = [traceRow, ...trackedEvents].slice(0, 30);
    }

    return HttpResponse.json({ accepted, rejected, results } satisfies IngestBatchResponse);
  }),
  http.get("/api/debug/events", async () => {
    await delay(60);
    return HttpResponse.json(trackedEvents);
  }),
  http.post("/api/checkout", async ({ request }) => {
    const body = (await request.json()) as CheckoutInput;
    return HttpResponse.json({
      orderId: `demo-${body.items.length}-${Date.now()}`,
      status: "confirmed",
      placedAt: new Date().toISOString(),
    });
  }),
  http.get("/api/me/orders", async ({ request }) => {
    await delay(120);
    const url = new URL(request.url);
    const page = Math.max(1, Number(url.searchParams.get("page") ?? "1"));
    const pageSize = Math.min(50, Math.max(1, Number(url.searchParams.get("pageSize") ?? "10")));
    const start = (page - 1) * pageSize;
    const items = ordersState.slice(start, start + pageSize);
    const res: OrderListResponse = { items, page, pageSize, total: ordersState.length };
    return HttpResponse.json(res);
  }),
  http.patch("/api/me/orders/:orderId/delivery-address", async ({ params, request }) => {
    await delay(140);
    const orderId = String(params.orderId);
    const body = (await request.json()) as { deliveryAddressId: string };
    const exists = addressBook.some((a) => a.id === body.deliveryAddressId);
    if (!exists) {
      return HttpResponse.json({ error: "address_not_found" }, { status: 404 });
    }
    const idx = ordersState.findIndex((o) => o.id === orderId);
    if (idx === -1) {
      return new HttpResponse(null, { status: 404 });
    }
    const addr = addressBook.find((a) => a.id === body.deliveryAddressId)!;
    ordersState[idx] = {
      ...ordersState[idx],
      deliveryAddressId: body.deliveryAddressId,
      destinationLabel: `${addr.label} · ${addr.city}`,
    };
    return HttpResponse.json(ordersState[idx]);
  }),
  http.get("/api/me/addresses", async () => {
    await delay(90);
    const res: DeliveryAddressListResponse = { items: addressBook };
    return HttpResponse.json(res);
  }),
  http.patch("/api/me/addresses/:id", async ({ params, request }) => {
    await delay(100);
    const id = String(params.id);
    const body = (await request.json()) as Partial<DeliveryAddress>;
    const idx = addressBook.findIndex((a) => a.id === id);
    if (idx === -1) {
      return new HttpResponse(null, { status: 404 });
    }
    addressBook[idx] = { ...addressBook[idx], ...body, id: addressBook[idx].id };
    return HttpResponse.json(addressBook[idx]);
  }),
];
