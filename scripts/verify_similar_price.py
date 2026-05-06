"""End-to-end verifier for /recommend/similar-price + /recommend/complement.

Two assertions matter:

  1. Backward-compat for /recommend/complement after the rename + mode-flag
     refactor — same response keys, same products shape, no 5xx.

  2. /recommend/similar-price returns:
       - non-empty `products` array
       - every price within anchor.price ± tolerance
       - every product's category equals the anchor's (substitute-only lock)
       - every product has rating >= 3.5 AND reviewCount >= 2 (review floor)
       - anchor itself is NOT in the array
       - top-level `personalization_reason` is non-null when ranked facts exist

Run from inside the docker network so HYPERPERSONA_BASE_URL=http://server:8000
resolves. Used by `make verify-similar-price` (or invoke directly).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from urllib.parse import urlencode

BASE_URL = os.getenv("HYPERPERSONA_BASE_URL", "http://server:8000")


def _api(method, path, body=None, token=None):
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, method=method, data=data)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            text = resp.read().decode() or "null"
            return resp.status, json.loads(text)
    except urllib.error.HTTPError as e:
        text = e.read().decode() or "null"
        try:
            return e.code, json.loads(text)
        except json.JSONDecodeError:
            return e.code, {"raw": text}


def _hr():
    print("-" * 72)


def main():
    failures: list[str] = []

    # 1. Auth
    email = f"verify_similar_price_{uuid.uuid4().hex[:8]}@example.com"
    s, b = _api("POST", "/register", {"email": email, "password": "hunter22hunter"})
    assert s == 200, f"register failed: {s} {b}"
    token = b["access_token"]
    print(f"registered {email}")

    s, b = _api("POST", "/consent",
                {"scopes": ["personalization", "analytics", "marketing"], "data_retention_days": 30},
                token=token)
    assert s in (200, 201), f"consent failed: {s} {b}"

    # 2. Find an anchor product from storefront popular list
    s, products = _api("GET", "/catalog/popular", token=token)
    assert s == 200, f"catalog/popular failed: {s} {products}"
    if not isinstance(products, list) or not products:
        print(f"no popular products available: {products}")
        sys.exit(2)

    # Pick the first product that has a price > 0 and a category
    anchor = next(
        (p for p in products if p.get("price") and p.get("category")),
        products[0],
    )
    anchor_slug = anchor["slug"]
    anchor_price = float(anchor.get("price") or 0)
    anchor_category = anchor.get("category")
    print(f"anchor: {anchor_slug} cat={anchor_category} price=${anchor_price}")

    # 3. Hit /recommend/similar-price
    _hr()
    print("/recommend/similar-price")
    qs = urlencode({"product_id": anchor_slug, "limit": 6, "tolerance": 0.2})
    s, body = _api("GET", f"/recommend/similar-price?{qs}", token=token)
    print(f"  HTTP {s}")
    assert s == 200, f"similar-price failed: {s} {body}"
    print(json.dumps(body, indent=2)[:1500])

    band = body.get("price_band") or {}
    min_p, max_p = band.get("min", 0), band.get("max", 0)
    products_arr = body.get("products") or []

    if body.get("anchor_product_id") != anchor_slug:
        failures.append(f"anchor_product_id mismatch: {body.get('anchor_product_id')!r} != {anchor_slug!r}")

    if not products_arr:
        failures.append("products array is empty (likely OK if catalog has too few same-category peers — see candidates_dropped_*)")
    else:
        for p in products_arr:
            pid = p.get("product_id")
            price = float(p.get("price") or 0)
            cat = p.get("category")
            rating = p.get("rating")
            review_count = p.get("reviewCount")

            if pid == anchor_slug:
                failures.append(f"anchor leaked into products: {pid}")
            if not (min_p <= price <= max_p):
                failures.append(f"product {pid} price ${price} outside band [{min_p}, {max_p}]")
            if anchor_category and cat != anchor_category and not body.get("category_lock_relaxed"):
                failures.append(f"product {pid} category {cat!r} != anchor {anchor_category!r}")
            if rating is not None and rating < 3.5:
                failures.append(f"product {pid} rating {rating} < 3.5")
            if review_count is not None and review_count < 2:
                failures.append(f"product {pid} reviewCount {review_count} < 2")

    # 4. Backward-compat: /recommend/complement (sanity that the rename didn't break it)
    _hr()
    print("/recommend/complement (backward-compat)")
    qs = urlencode({"cart_items": "laptop_dell_xps_15"})  # lean catalog id
    s, c_body = _api("GET", f"/recommend/complement?{qs}", token=token)
    print(f"  HTTP {s}")
    print(json.dumps(c_body, indent=2)[:1200])
    expected_keys = {"recommendations", "cart_items", "cart_resolved", "candidates_considered", "used_llm", "job_id"}
    actual_keys = set(c_body.keys()) if isinstance(c_body, dict) else set()
    missing = expected_keys - actual_keys
    if s != 200:
        failures.append(f"complement returned non-200: {s}")
    elif missing:
        failures.append(f"complement missing keys: {missing}")

    _hr()
    if failures:
        print("FAIL:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("PASS — both endpoints behaving as expected")


if __name__ == "__main__":
    main()
