export type Category = {
  id: string;
  slug: string;
  name: string;
  description: string;
  hero: string;
};

/** Merchandising vertical — drives which PDP facts and catalog facets apply. */
export type ProductVertical = "apparel" | "furniture" | "electronics" | "general";

export type ProductVariantOption = {
  id: string;
  label: string;
};

/** Structured logistics / size facts (clothes, phones, flat-pack, etc.). */
export type ProductDimensions = {
  /** Human-readable, e.g. `27.3 × 24.8 × 4.9 cm; 180 g` */
  display?: string;
  lengthCm?: number;
  widthCm?: number;
  heightCm?: number;
  weightG?: number;
};

export type CatalogFacetValue = {
  value: string;
  label: string;
  count: number;
};

export type CatalogFacetGroup = {
  id: string;
  label: string;
  facetType: "boolean" | "single" | "multi" | "range";
  values?: CatalogFacetValue[];
  min?: number;
  max?: number;
};

/** Logged-in or demo session: the shopper’s own published review for this SKU, if any. */
export type ViewerProductReview = {
  id: string;
  rating: number;
  title?: string;
  body: string;
  createdAt: string;
  updatedAt?: string;
};

export type Product = {
  id: string;
  slug: string;
  name: string;
  brand: string;
  category: string;
  price: number;
  compareAt?: number;
  rating: number;
  reviewCount: number;
  image: string;
  description: string;
  features: string[];
  badges: string[];
  inventoryStatus: "in-stock" | "low-stock" | "backorder";
  personalizationTags: string[];
  /** Present when the API knows the current customer has already reviewed this product. */
  viewerReview?: ViewerProductReview | null;
  /** Apparel vs furniture vs electronics — filters + PDP modules. */
  vertical?: ProductVertical;
  /** When true, listing/PDP should show a free-delivery affordance; track clicks in context of this flag. */
  freeDelivery?: boolean;
  /** Gallery after hero `image` (same SKU). */
  images?: string[];
  /** Long-form PDP body (tabs: Description). */
  longDescription?: string;
  dimensions?: ProductDimensions;
  department?: string;
  /** Bullet “Specification” row on PDP (reference: comma-separated feature list). */
  specification?: string[];
  dateFirstAvailable?: string;
  /** Merchandising chips (material, fit, room, connectivity…). */
  tags?: string[];
  colorOptions?: ProductVariantOption[];
  sizeOptions?: ProductVariantOption[];
  /** Phones / laptops / drives — mutually exclusive with size for some verticals. */
  storageOptions?: ProductVariantOption[];
};

/** Single UGC review row on a PDP (aggregated helpful / not-helpful counts are server-owned). */
export type ProductReview = {
  id: string;
  productId: string;
  authorDisplayName: string;
  rating: number;
  title?: string;
  body: string;
  createdAt: string;
  verifiedPurchase?: boolean;
  helpfulCount: number;
  notHelpfulCount: number;
  /** Caller’s current vote on this review, when identity is known. */
  viewerHelpfulVote?: ReviewHelpfulVote | null;
};

export type ReviewHelpfulVote = "helpful" | "not_helpful";

export type ProductReviewsResponse = {
  items: ProductReview[];
  page: number;
  pageSize: number;
  total: number;
};

export type CreateProductReviewBody = {
  rating: number;
  title?: string;
  body: string;
};

export type CreateProductReviewResponse = {
  review: ProductReview;
  viewerReview: ViewerProductReview;
};

export type SetReviewHelpfulBody = {
  vote: ReviewHelpfulVote;
};

export type SetReviewHelpfulResponse = {
  reviewId: string;
  helpfulCount: number;
  notHelpfulCount: number;
  viewerHelpfulVote: ReviewHelpfulVote;
};

/**
 * Canonical `event_type` strings for review-related `POST /events` payloads (see API_REQUIREMENTS.md).
 * Payload shapes are intentionally loose on `IngestEventRequest` but typed here for callers.
 */
export type ReviewTelemetryEventType =
  | "product_reviews_viewed"
  | "product_reviews_page_loaded"
  | "product_review_submitted"
  | "product_review_engagement";

export type ReviewTelemetryPayload = {
  product_reviews_viewed: { productId: string; slug: string; reviewCountShown: number };
  product_reviews_page_loaded: { productId: string; slug: string; page: number; pageSize: number };
  product_review_submitted: { productId: string; slug: string; reviewId: string; rating: number };
  /** Helpful / not helpful on another shopper’s review (UGC engagement). */
  product_review_engagement: { productId: string; slug: string; reviewId: string; vote: ReviewHelpfulVote };
};

/**
 * Catalog / PDP instrumentation for `POST /events` (see `API_REQUIREMENTS.md`).
 * Workers use these for ranking, rails, and “free delivery affinity” segments.
 */
export type CommerceTelemetryEventType =
  | "product_tile_clicked"
  | "product_pdp_viewed"
  | "pdp_tab_selected"
  | "pdp_variant_selected"
  | "pdp_quantity_changed"
  | "pdp_free_delivery_badge_viewed"
  | "pdp_report_product_clicked";

export type CommerceTelemetryPayload = {
  product_tile_clicked: {
    productId: string;
    slug: string;
    freeDelivery: boolean;
    vertical?: ProductVertical;
    source: "grid" | "rail" | "search" | "other";
  };
  product_pdp_viewed: { productId: string; slug: string; vertical?: ProductVertical; freeDelivery?: boolean };
  pdp_tab_selected: { productId: string; slug: string; tab: string };
  pdp_variant_selected: {
    productId: string;
    slug: string;
    optionKind: "color" | "size" | "storage" | "other";
    optionId: string;
    optionLabel: string;
  };
  pdp_quantity_changed: { productId: string; slug: string; quantity: number };
  pdp_free_delivery_badge_viewed: { productId: string; slug: string };
  pdp_report_product_clicked: { productId: string; slug: string };
};

export type ProductListResponse = {
  items: Product[];
  total: number;
  page: number;
  pageSize: number;
  personalized: boolean;
  /** @deprecated Prefer `GET /catalog/facets` — kept optional for older mocks/backends. */
  facets?: CatalogFacetGroup[];
};

export type DeliveryAddress = {
  id: string;
  label: string;
  line1: string;
  line2?: string;
  city: string;
  region?: string;
  postalCode: string;
  country: string;
  isDefault?: boolean;
};

export type DeliveryAddressListResponse = {
  items: DeliveryAddress[];
};

export type OrderLine = {
  productId: string;
  slug: string;
  name: string;
  quantity: number;
  unitPrice: number;
  /** Selected variant keys, e.g. `{ color: "slate", size: "M" }` — tracked for recommendations. */
  selectedOptions?: Record<string, string>;
};

export type OrderSummary = {
  id: string;
  status: "placed" | "processing" | "shipped" | "delivered" | "cancelled";
  placedAt: string;
  total: number;
  currency: string;
  destinationLabel: string;
  lineCount: number;
  trackingUrl?: string;
  lines?: OrderLine[];
  deliveryAddressId?: string;
};

export type OrderListResponse = {
  items: OrderSummary[];
  page: number;
  pageSize: number;
  total: number;
};

export type RecommendationRail = {
  id: string;
  title: string;
  subtitle: string;
  reason: string;
  confidence: number;
  fallback: boolean;
  products: Product[];
};

/**
 * Mirrors `ConsentRecord` returned by `GET /consent` / `POST /consent` in
 * `server/src/routes/consent.py`. Field names follow the backend wire shape
 * (snake_case) so the FE doesn't need a transform layer for this resource.
 *
 * `last_updated` is only present on the GET response (read from DDB); the
 * POST response omits it. Treat it as optional for that reason.
 */
export type ConsentRecord = {
  customer_id: string;
  scopes: string[];
  data_retention_days: number;
  last_updated?: string;
};

/** Allowed consent scopes — keep aligned with `ConsentUpsertRequest.scopes`. */
export const CONSENT_SCOPES = ["analytics", "personalization", "marketing"] as const;
export type ConsentScope = (typeof CONSENT_SCOPES)[number];

/** Reasonable retention windows for the demo lab UI. */
export const CONSENT_RETENTION_OPTIONS = [30, 90, 180, 365] as const;

export type ExplicitPreference = {
  key: string;
  label: string;
  value: string;
};

export type InferredInterest = {
  id: string;
  label: string;
  confidence: number;
  source: string;
};

export type ProfileSummary = {
  customerId: string;
  name: string;
  segment: string;
  topCategories: string[];
  explicitPreferences: ExplicitPreference[];
  inferredInterests: InferredInterest[];
  recentSignals: string[];
  lastUpdated: string;
};

export type ExplanationRecord = {
  search: string[];
  recommendations: string[];
  profileSignals: string[];
};

export type TrackedEvent = {
  event_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  status: "queued" | "sent" | "rejected";
  created_at: string;
  /** Server reason when status === "rejected" (e.g. `missing_personalization_scope`). */
  reason?: string;
};

/**
 * Wire shape sent to `POST /events` and `POST /events/batch` — mirrors
 * `IngestEventRequest` in `shared/schemas.py`. The tracker hook still accepts
 * a legacy `customer_id` field on input for backwards compat with existing
 * call sites; that field is dropped before the request goes on the wire
 * (server resolves identity from the JWT instead).
 */
export type IngestEventRequest = {
  client_event_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  consent_scope?: string[];
};

/**
 * Per-event result inside an `IngestBatchResponse`. The server uses
 * `client_event_id` as the dedupe + idempotency key, and emits
 * `status === "rejected"` (with a `reason`) when consent gates the batch.
 */
export type IngestEventResult = {
  client_event_id: string;
  status: "queued" | "rejected";
  event_id?: string;
  job_id?: string;
  reason?: string;
};

export type IngestBatchResponse = {
  accepted: number;
  rejected: number;
  results: IngestEventResult[];
};

/**
 * Bearer-token auth contract — mirrors `AuthResponse` in `shared/schemas.py`.
 * Returned from `POST /register` and `POST /login`. The token is a JWT; place
 * it in `Authorization: Bearer <token>` for every protected request.
 */
export type AuthResponse = {
  customer_id: string;
  email: string;
  token: string;
  token_type: "bearer";
  expires_in: number;
};

export type RegisterRequest = {
  email: string;
  password: string;
};

export type LoginRequest = {
  email: string;
  password: string;
};

/**
 * Persisted client-side session. `expires_at_ms` is computed at issue time
 * (`Date.now() + expires_in * 1000`) so the FE can detect expiry without a server round trip.
 */
export type AuthSession = {
  token: string;
  customerId: string;
  email: string;
  expiresAtMs: number;
};

/**
 * Normalized error envelope thrown by the API client. Handles FastAPI's
 * `{ detail }` (route-level 4xx), the JWT middleware's `{ error }` (401/500),
 * and bare network errors uniformly.
 */
export class ApiError extends Error {
  status: number;
  code?: string;
  retryable: boolean;
  constructor(args: { status: number; message: string; code?: string; retryable?: boolean }) {
    super(args.message);
    this.name = "ApiError";
    this.status = args.status;
    this.code = args.code;
    this.retryable = args.retryable ?? (args.status >= 500 || args.status === 0);
  }
}

export type CheckoutInput = {
  email: string;
  fullName: string;
  address: string;
  city: string;
  country: string;
  paymentMethod: "card" | "wallet";
  subtotal: number;
  items: Array<{ productId: string; quantity: number }>;
};

export type CheckoutResponse = {
  orderId: string;
  status: "confirmed";
  placedAt: string;
};
