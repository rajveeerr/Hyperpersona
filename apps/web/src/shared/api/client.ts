import { clearSession, getSession, sessionFromAuthResponse, setSession } from "@/features/auth/tokenStore";
import { env } from "@/shared/config/env";
import { ApiError } from "@/shared/api/contracts";
import type {
  AddCartItemBody,
  AddWishlistItemBody,
  AuthResponse,
  AuthSession,
  CartResponse,
  CatalogFacetGroup,
  Category,
  CheckoutInput,
  CheckoutResponse,
  ComplementResponse,
  ConsentRecord,
  CreateProductReviewBody,
  CreateProductReviewResponse,
  DeleteCustomerResponse,
  ExplanationRecord,
  IngestBatchResponse,
  IngestEventRequest,
  LoginRequest,
  OrderListResponse,
  PatchCartItemBody,
  Product,
  ProductListResponse,
  ProductReviewsResponse,
  ProfileSummary,
  RecommendResponse,
  RegisterRequest,
  SetReviewHelpfulBody,
  SetReviewHelpfulResponse,
  WishlistResponse,
} from "@/shared/api/contracts";

/**
 * Routes the FE may call without a Bearer token. Anything outside this set
 * gets the `Authorization` header injected (when a session exists). Mirrors
 * `PUBLIC_PATHS` in `server/src/middleware/auth.py`.
 */
const PUBLIC_PATHS = new Set(["/health", "/", "/login", "/register"]);

function isPublicPath(path: string): boolean {
  const [bare] = path.split("?");
  return PUBLIC_PATHS.has(bare);
}

type AuthEventName = "auth:expired" | "auth:login" | "auth:logout";

function emitAuth(name: AuthEventName, detail?: unknown) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(name, { detail }));
}

async function readError(response: Response): Promise<{ message: string; code?: string }> {
  // FastAPI: `{ detail: "..." }` on routed 4xx; JWT middleware: `{ error: "..." }`
  // on 401/500. Fall back to status text + best-effort body decode for everything else.
  try {
    const text = await response.text();
    if (!text) return { message: response.statusText || "request failed" };
    try {
      const json = JSON.parse(text) as { detail?: unknown; error?: unknown; code?: unknown };
      if (typeof json.detail === "string") return { message: json.detail, code: typeof json.code === "string" ? json.code : undefined };
      if (typeof json.error === "string") return { message: json.error, code: typeof json.code === "string" ? json.code : undefined };
      if (Array.isArray(json.detail)) {
        // Pydantic validation errors come back as an array of issue objects.
        return { message: "validation_error", code: "validation_error" };
      }
      return { message: response.statusText || "request failed" };
    } catch {
      return { message: text.slice(0, 240) };
    }
  } catch {
    return { message: response.statusText || "request failed" };
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers ?? {});
  if (!headers.has("Content-Type") && init?.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  if (!isPublicPath(path)) {
    const session = getSession();
    if (session) headers.set("Authorization", `Bearer ${session.token}`);
  }

  let response: Response;
  try {
    response = await fetch(`${env.apiBaseUrl}${path}`, { ...init, headers });
  } catch (cause) {
    throw new ApiError({
      status: 0,
      message: cause instanceof Error ? cause.message : "network_error",
      code: "network_error",
      retryable: true,
    });
  }

  if (!response.ok) {
    const { message, code } = await readError(response);
    if (response.status === 401 && !isPublicPath(path)) {
      // Bearer rejected (expired, revoked, or never present). Wipe the session
      // and let the app shell route to login. Public-path 401s (login with bad
      // credentials) are surfaced to the caller as-is.
      clearSession();
      emitAuth("auth:expired");
    }
    throw new ApiError({ status: response.status, message, code });
  }

  // 204 / empty bodies — let callers type T as `void` and trust the absence of body.
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const apiClient = {
  // --- Auth (public) ---
  register: async (body: RegisterRequest): Promise<AuthSession> => {
    const res = await request<AuthResponse>("/register", {
      method: "POST",
      body: JSON.stringify(body),
    });
    const session = sessionFromAuthResponse(res);
    setSession(session);
    emitAuth("auth:login", session);
    return session;
  },
  login: async (body: LoginRequest): Promise<AuthSession> => {
    const res = await request<AuthResponse>("/login", {
      method: "POST",
      body: JSON.stringify(body),
    });
    const session = sessionFromAuthResponse(res);
    setSession(session);
    emitAuth("auth:login", session);
    return session;
  },
  /**
   * Client-side logout. There is no backend logout endpoint — JWTs are stateless
   * and expire on their own. Callers are responsible for invalidating their
   * React Query cache after this returns.
   */
  logout: (): void => {
    clearSession();
    emitAuth("auth:logout");
  },

  // --- Catalog / search ---
  getCategories: () => request<Category[]>("/catalog/categories"),
  /**
   * Aggregated facet counts for the current browse/search filter context (category/q + facet selections).
   * Not tied to sort/page — call separately from the product list.
   */
  getCatalogFacets: (params = "") => request<CatalogFacetGroup[]>(`/catalog/facets${params}`),
  getProducts: (params = "") => request<ProductListResponse>(`/catalog/products${params}`),
  /** Same catalog slice for every shopper — popularity / bestseller ordering from the server. */
  getPopularProducts: () => request<Product[]>(`/catalog/popular`),
  getProduct: (slug: string) => request<Product>(`/catalog/products/${slug}`),
  getProductReviews: (slug: string, params = "") =>
    request<ProductReviewsResponse>(`/catalog/products/${slug}/reviews${params}`),
  createProductReview: (slug: string, body: CreateProductReviewBody) =>
    request<CreateProductReviewResponse>(`/catalog/products/${slug}/reviews`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  setReviewHelpful: (slug: string, reviewId: string, body: SetReviewHelpfulBody) =>
    request<SetReviewHelpfulResponse>(
      `/catalog/products/${slug}/reviews/${encodeURIComponent(reviewId)}/helpful`,
      { method: "PUT", body: JSON.stringify(body) },
    ),
  searchProducts: (params = "") => request<ProductListResponse>(`/search${params}`),

  // --- Recommendations ---
  /**
   * Personalized rail. Pass a context string from `Context.*` helpers
   * ([apps/web/src/features/events/contexts.ts]) — never hand-build the
   * value, since the server caches per (customer_id, context_hash) for
   * 5 minutes and ad-hoc strings balloon the keyspace.
   *
   * Response includes a ranked `products[]`, a `personalization_reason`
   * subtitle (null when generic), and the AI `offer` text the FE can
   * surface as an editorial banner.
   */
  getRecommendation: (context: string) =>
    request<RecommendResponse>(`/recommend?context=${encodeURIComponent(context)}`),
  /**
   * Cart-driven "frequently bought together" rail. Pass the product ids
   * currently in the cart (comma-separated server-side), optional limit
   * up to 10. Response is a lighter shape — no images / brand / rating —
   * so render a text-forward "list" tile rather than the catalog grid.
   */
  getComplementRecommendation: (cartItems: string[], limit = 5) => {
    const params = new URLSearchParams({
      cart_items: cartItems.join(","),
      limit: String(limit),
    });
    return request<ComplementResponse>(`/recommend/complement?${params.toString()}`);
  },

  // --- Consent / profile ---
  getConsent: () => request<ConsentRecord>("/consent"),
  /**
   * Backend now exposes `POST /consent` (was `PUT` in earlier mock contract).
   * The body matches `ConsentUpsertRequest` in `shared/schemas.py`. `customer_id`
   * is JWT-derived server-side — do not pass it in the body.
   */
  updateConsent: (scopes: string[], dataRetentionDays?: number) =>
    request<ConsentRecord>("/consent", {
      method: "POST",
      body: JSON.stringify({
        scopes,
        ...(dataRetentionDays !== undefined ? { data_retention_days: dataRetentionDays } : {}),
      }),
    }),
  getProfile: () => request<ProfileSummary>("/me/profile"),
  updateProfile: (explicitPreferences: ProfileSummary["explicitPreferences"]) =>
    request<ProfileSummary>("/me/preferences", {
      method: "PATCH",
      body: JSON.stringify({ explicitPreferences }),
    }),
  getExplanations: () => request<ExplanationRecord>("/me/explanations"),
  /**
   * Right-to-erasure. Wipes the customer's behavioral data (events, consent,
   * Redis state, vectors) on the BE — see `server/src/routes/customer.py`.
   * The customer auth row is NOT removed by this endpoint; callers should
   * still call `apiClient.logout()` after this resolves so the FE treats it
   * as a clean session end.
   */
  deleteAccount: () =>
    request<DeleteCustomerResponse>("/customer", { method: "DELETE" }),

  // --- Tracking ---
  /**
   * Submit a batch of events. The server uses `client_event_id` for
   * idempotency, so retries of the same batch on a flaky network are safe.
   *
   * `keepalive` should be set when sending during `pagehide` / `visibilitychange`
   * so the browser commits the request even if the page is being torn down.
   * Note: keepalive bodies are capped at ~64 KB per origin, so the tracker
   * trims batch size to stay safely under that ceiling.
   */
  trackEventsBatch: (events: IngestEventRequest[], opts: { keepalive?: boolean } = {}) =>
    request<IngestBatchResponse>("/events/batch", {
      method: "POST",
      body: JSON.stringify({ events }),
      keepalive: opts.keepalive,
    }),

  // --- Commerce ---
  checkout: (body: CheckoutInput) =>
    request<CheckoutResponse>("/checkout", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getOrders: (params = "") => request<OrderListResponse>(`/me/orders${params}`),

  // --- Server-side cart (mirrors `server/src/routes/me_cart.py`) ---
  /** Returns the customer's cart with pre-computed `itemCount` + `subtotal`. */
  getCart: () => request<CartResponse>("/me/cart"),
  /** Add a product to the cart. Server bumps quantity if the line already exists. */
  addCartItem: (body: AddCartItemBody) =>
    request<CartResponse>("/me/cart/items", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  /** Update quantity (and/or selectedOptions) on an existing line. */
  patchCartItem: (productId: string, body: PatchCartItemBody) =>
    request<CartResponse>(`/me/cart/items/${encodeURIComponent(productId)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteCartItem: (productId: string) =>
    request<CartResponse>(`/me/cart/items/${encodeURIComponent(productId)}`, {
      method: "DELETE",
    }),

  // --- Server-side wishlist (mirrors `server/src/routes/me_wishlist.py`) ---
  getWishlist: () => request<WishlistResponse>("/me/wishlist"),
  addWishlistItem: (body: AddWishlistItemBody) =>
    request<WishlistResponse>("/me/wishlist/items", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  deleteWishlistItem: (productId: string) =>
    request<WishlistResponse>(`/me/wishlist/items/${encodeURIComponent(productId)}`, {
      method: "DELETE",
    }),
};
