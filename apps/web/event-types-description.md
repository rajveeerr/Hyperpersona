# HyperPersona — Frontend Event & Context Spec (v1)

## 1. Events to track (`POST /events`)

Fire these whenever the user does the corresponding action. Body shape:

```json
{ "customer_id": "<string>", "event_type": "<from table below>", "payload": { ... } }
```

| `event_type` | When to fire | `payload` shape |
|---|---|---|
| `search` | User submits a search (debounce — fire on submit, not every keystroke) | `{ "query": string, "results_count": number }` |
| `product_view` | User opens a product detail page (fire on PDP mount, also fire `product_dwell` if you want depth) | `{ "product_id": string, "product_name": string, "category": string, "price": number }` |
| `product_dwell` | User stayed ≥10s on a PDP (debounced, send once per page load) | `{ "product_id": string, "category": string, "duration_seconds": number }` |
| `category_view` | User lands on a category/listing page | `{ "category": string }` |
| `filter_applied` | User applies a filter on a listing page | `{ "category": string, "filter_type": string, "filter_value": string }` |
| `add_to_cart` | User adds item to cart | `{ "product_id": string, "product_name": string, "category": string, "price": number, "quantity": number }` |
| `remove_from_cart` | User removes item from cart | `{ "product_id": string, "category": string }` |
| `wishlist_add` | User adds to wishlist / saves for later | `{ "product_id": string, "product_name": string, "category": string }` |
| `wishlist_remove` | User removes from wishlist | `{ "product_id": string, "category": string }` |
| `purchase` | Order completed (one event per line item is fine; or one summary event) | `{ "product_id": string, "product_name": string, "category": string, "price": number, "quantity": number }` |
| `return_initiated` | User starts a return (negative signal — important!) | `{ "product_id": string, "category": string, "reason": string }` |
| `review_submitted` | User leaves a review | `{ "product_id": string, "rating": number, "summary": string }` |
| `email_clicked` | User clicks a link from a marketing email | `{ "campaign": string, "link_target": string }` |
| `recommendation_clicked` | User clicks a recommendation we showed them | `{ "product_id": string, "category": string, "source_context": string }` |

### Do NOT track these (noise / privacy / cost)

- Per-pixel `scroll` events
- Individual `keystroke` events
- Hover events
- Free-form text inputs that aren't searches (PII risk)
- More than 1 `page_view` for the same page in the same session

### Aggregation rules

- Debounce search to fire only on **submit**, not on each keystroke.
- `product_dwell` should fire **at most once per PDP load**, only if user stayed ≥10s.
- Don't fire the same event twice in <2s (deduplicate).

---

## 2. Context strings for `GET /recommend`

Call `/recommend` whenever a surface needs to render a recommendation slot. Use these context strings — exact format, lowercase, normalized.

| Surface / trigger | `context` string |
|---|---|
| Homepage rail | `homepage` |
| Category listing page | `category:{slug}` (e.g. `category:hiking_boots`) |
| Product detail page (similar items) | `product_page:{category_slug}` |
| Search results (sponsored slot) | `search:{category_slug}` if results have a clear category, else `search:general` |
| Cart page | `cart_active` |
| Empty cart page | `cart_empty` |
| Post-purchase / order confirmation | `post_purchase` |
| Wishlist page | `wishlist_active` |
| Email newsletter generation | `email:newsletter` |
| Abandoned cart email | `email:cart_recovery` |
| 404 / no-results page | `no_results` |

### Rules for context strings

1. **Lowercase + underscores.** No spaces, no caps, no special chars.
2. **Use category slug, not SKU.** The customer's stored facts in OpenSearch already know what they viewed. The context just tells the recommender which surface.
3. **No timestamps, no user IDs, no session IDs.** These break caching for zero benefit (`customer_id` is already part of the cache key).
4. **No cart contents, no exact prices.** Bucket if needed (`cart:small`, `cart:large`).

---

## 3. When to call `/recommend`

✅ **Call it:**
- When a page mounts and has a recommendation slot to fill
- After a major user action that changes the surface (e.g. user adds last item → switch to `cart_active` recommendation)
- When generating an email/notification

❌ **Don't call it:**
- After every single event (you'll burn cache + Bedrock budget for no UI benefit)
- More than once per surface per render
- Inside scroll/hover handlers

---

## 4. Frontend helper file (drop-in)

```typescript
// recommendations.ts
const API_BASE = process.env.API_BASE_URL;
const API_KEY = process.env.API_KEY;

// --- Allowed contexts (single source of truth) ----------------------
export const Context = {
  homepage:        () => "homepage",
  category:        (slug: string) => `category:${normalize(slug)}`,
  productPage:     (categorySlug: string) => `product_page:${normalize(categorySlug)}`,
  search:          (categorySlug?: string) =>
                     `search:${categorySlug ? normalize(categorySlug) : "general"}`,
  cartActive:      () => "cart_active",
  cartEmpty:       () => "cart_empty",
  postPurchase:    () => "post_purchase",
  wishlist:        () => "wishlist_active",
  emailNewsletter: () => "email:newsletter",
  emailCartRecovery: () => "email:cart_recovery",
  noResults:       () => "no_results",
} as const;

function normalize(s: string): string {
  return s.toLowerCase().trim().replace(/\s+/g, "_");
}

// --- API calls -------------------------------------------------------
export async function trackEvent(
  customerId: string,
  eventType: string,
  payload: Record<string, unknown>,
) {
  return fetch(`${API_BASE}/events`, {
    method: "POST",
    headers: { "X-API-Key": API_KEY!, "Content-Type": "application/json" },
    body: JSON.stringify({ customer_id: customerId, event_type: eventType, payload }),
  });
}

export async function getRecommendation(customerId: string, context: string) {
  const url = `${API_BASE}/recommend?customer_id=${encodeURIComponent(customerId)}` +
              `&context=${encodeURIComponent(context)}`;
  const res = await fetch(url, { headers: { "X-API-Key": API_KEY! } });
  return res.json();
}

// --- Example usage ---------------------------------------------------
// On homepage mount:
// const rec = await getRecommendation(customerId, Context.homepage());
//
// On product page mount:
// trackEvent(customerId, "product_view", { product_id, product_name, category, price });
// const rec = await getRecommendation(customerId, Context.productPage(category));
//
// On add to cart:
// trackEvent(customerId, "add_to_cart", { product_id, product_name, category, price, quantity });
// (don't need to call /recommend here unless you're refreshing the cart-page rail)
```

---

## 5. Quick sanity checklist for the frontend dev

- [ ] Events fire from a single helper function (`trackEvent`) — never inline `fetch("/events")`
- [ ] All `/recommend` calls go through the `Context.*` helpers — no string concatenation at call sites
- [ ] Context strings are validated against the table above (consider a TS literal-union type)
- [ ] Search input is debounced — only the submitted query becomes a `search` event
- [ ] PDP dwell uses a single timer per page load, not per scroll/interaction
- [ ] No PII in `payload` fields (no email, no phone, no full name, no address)
- [ ] `/recommend` is only called on slot render or major surface change, not on every event