#!/usr/bin/env bash
# End-to-end smoke for the 17 ecommerce endpoints (M1+M2+M3).
#
# Idempotent: safe to run repeatedly against the same seeded stack.
# - Reviews: POST is treated as success on either 200 (created) or 409
#   (already reviewed by this customer in a prior run).
# - Cart / wishlist: cleared by-id before tests so prior state doesn't
#   skew counts.
# - Orders: asserts >= 2 demo seeds plus N more from prior checkouts.
#
# Usage:
#   make smoke-ecom
#   # or
#   ./scripts/smoke_ecom.sh
#
# Prereqs:
#   make up && make seed-all
#
# Demo creds match scripts/seed_demo_customer.py.

set -uo pipefail

BASE="${SMOKE_BASE_URL:-http://localhost:8000}"
EMAIL="${SMOKE_EMAIL:-demo@hyperpersona.dev}"
PASSWORD="${SMOKE_PASSWORD:-demo-password-123}"

PASS=0
FAIL=0

fail() { echo "  FAIL: $1"; FAIL=$((FAIL+1)); }
pass() { echo "  PASS: $1"; PASS=$((PASS+1)); }

# Numeric float equality: bash `=` is string compare, which trips on
# "158" vs "158.0". Use python with a small tolerance instead.
nearly_equal() {
    python3 -c "import sys; sys.exit(0 if abs(float('$1') - float('$2')) < 0.01 else 1)"
}

T=$(curl -s -X POST "$BASE/login" -H 'Content-Type: application/json' \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])" 2>/dev/null)

if [ -z "${T:-}" ]; then
    echo "LOGIN FAILED — is the stack up and seeded?"
    echo "  try: make up && make seed-all"
    exit 1
fi
echo "logged in (token len=${#T})"

H="Authorization: Bearer $T"
JSON='Content-Type: application/json'

# run <label> <method> <path> <body|""> <python-assert>
# python-assert reads the response body on stdin; raise to fail.
run() {
    local label="$1" method="$2" path="$3" data="${4:-}" check="$5"
    local resp body http
    if [ -n "$data" ]; then
        resp=$(curl -s -w '\n%{http_code}' -X "$method" -H "$H" -H "$JSON" -d "$data" "$BASE$path")
    else
        resp=$(curl -s -w '\n%{http_code}' -X "$method" -H "$H" "$BASE$path")
    fi
    http=$(echo "$resp" | tail -1)
    body=$(echo "$resp" | sed '$d')
    echo "[$method $path] http=$http"
    result=$(echo "$body" | python3 -c "$check" 2>&1) || { fail "$label: $result"; return; }
    echo "  $result"
    pass "$label"
}

# ===== M1 CATALOG (5) =====
echo
echo "===== M1 CATALOG ====="
run "GET /catalog/categories" GET /catalog/categories "" \
"import sys,json; d=json.load(sys.stdin); assert isinstance(d,list) and len(d)==5; print(f'5 categories: {[c[\"slug\"] for c in d]}')"

run "GET /catalog/popular" GET /catalog/popular "" \
"import sys,json; d=json.load(sys.stdin); assert len(d)==6; print(f'6 products top={d[0][\"slug\"]} reviewCount={d[0][\"reviewCount\"]}')"

run "GET /catalog/products filtered" GET '/catalog/products?vertical=apparel,electronics&freeDelivery=true' "" \
"import sys,json; d=json.load(sys.stdin); assert d['total']>=4; assert all(i.get('freeDelivery')==True for i in d['items']); print(f'total={d[\"total\"]} all freeDelivery=True')"

run "GET /catalog/facets per-group skip" GET '/catalog/facets?vertical=apparel' "" \
"import sys,json; d=json.load(sys.stdin); v=next(g for g in d if g['id']=='vertical'); furn=next(x for x in v['values'] if x['value']=='furniture'); assert furn['count']>0; print(f'vertical=apparel selected, furniture count={furn[\"count\"]} (per-group skip OK)')"

run "GET /catalog/products/{slug} PDP" GET /catalog/products/altitude-shell-jacket "" \
"import sys,json; d=json.load(sys.stdin); assert d['slug']=='altitude-shell-jacket'; assert len(d.get('colorOptions',[]))==3; print(f'name={d[\"name\"]} price={d[\"price\"]} viewerReview present={d.get(\"viewerReview\") is not None}')"

# ===== M1 SEARCH (1) =====
echo
echo "===== M1 SEARCH ====="
run "GET /search?q=jacket (hybrid)" GET '/search?q=jacket' "" \
"import sys,json; d=json.load(sys.stdin); slugs=[i['slug'] for i in d['items']]; assert 'altitude-shell-jacket' in slugs; print(f'total={d[\"total\"]} jacket in results: True')"

run "GET /search no q (delegates)" GET '/search?vertical=furniture' "" \
"import sys,json; d=json.load(sys.stdin); assert d['total']==2; print(f'furniture total={d[\"total\"]}')"

# ===== M2 REVIEWS (3) =====
echo
echo "===== M2 REVIEWS ====="
run "GET reviews (seeded slug)" GET /catalog/products/commuter-sling-pack/reviews "" \
"import sys,json; d=json.load(sys.stdin); assert d['total']==2; print(f'total={d[\"total\"]} ids={[r[\"id\"] for r in d[\"items\"]]}')"

# Idempotent: 200 (first run) or 409 (already reviewed in a prior run) both pass.
REVIEW_BODY='{"rating":5,"title":"Smoke test","body":"Smoke test review body."}'
RESP=$(curl -s -w '\n%{http_code}' -X POST -H "$H" -H "$JSON" -d "$REVIEW_BODY" "$BASE/catalog/products/recovery-knit-hoodie/reviews")
HTTP=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | sed '$d')
echo "[POST /catalog/products/recovery-knit-hoodie/reviews] http=$HTTP"
case "$HTTP" in
    200)
        ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['review']['id'])")
        echo "  created review id=$ID"
        pass "POST review (recovery-knit-hoodie)"
        ;;
    409)
        echo "  already reviewed by this customer in a prior smoke run — endpoint reachable"
        pass "POST review (recovery-knit-hoodie) — 409 dup path"
        ;;
    *)
        fail "POST review unexpected http=$HTTP body=$BODY"
        ;;
esac

run "PUT helpful (rev-csp-2)" PUT /catalog/products/commuter-sling-pack/reviews/rev-csp-2/helpful \
  '{"vote":"helpful"}' \
"import sys,json; d=json.load(sys.stdin); assert d['viewerHelpfulVote']=='helpful'; print(f'helpful={d[\"helpfulCount\"]}/{d[\"notHelpfulCount\"]} viewerVote={d[\"viewerHelpfulVote\"]}')"

# ===== M2 PROFILE (3) =====
echo
echo "===== M2 PROFILE ====="
run "GET /me/profile" GET /me/profile "" \
"import sys,json; d=json.load(sys.stdin); assert d['customerId']=='demo-customer-1'; assert len(d['addresses'])==2; print(f'name={d[\"name\"]} addresses={[a[\"id\"] for a in d[\"addresses\"]]}')"

run "PATCH /me/preferences" PATCH /me/preferences \
  '{"explicitPreferences":[{"key":"budget","label":"Budget band","value":"$100-$300"}]}' \
"import sys,json; d=json.load(sys.stdin); prefs={p['key']:p['value'] for p in d['explicitPreferences']}; assert prefs.get('budget')=='\$100-\$300'; print(f'updated; budget={prefs[\"budget\"]} lastUpdated={d[\"lastUpdated\"][:19]}')"

run "GET /me/explanations" GET /me/explanations "" \
"import sys,json; d=json.load(sys.stdin); assert len(d['search'])>0 and len(d['recommendations'])>0; print(f'search={len(d[\"search\"])} recs={len(d[\"recommendations\"])} signals={len(d[\"profileSignals\"])}')"

# ===== M2 ORDERS (1) =====
echo
echo "===== M2 ORDERS ====="
# Demo seeds give us at least 2; prior smoke checkouts may have added more.
run "GET /me/orders (>= demo seeds)" GET /me/orders "" \
"import sys,json; d=json.load(sys.stdin); ids=[o['id'] for o in d['items']]; assert d['total']>=2; assert 'ord-demo-1001' in ids and 'ord-demo-1002' in ids; print(f'total={d[\"total\"]} demo seeds present')"

# ===== M3 CART (4) =====
echo
echo "===== M3 CART ====="
# Wipe any leftover cart state (404 ignored) so counts are deterministic.
for pid in prod-1 prod-3 prod-7; do
    curl -s -o /dev/null -X DELETE -H "$H" "$BASE/me/cart/items/$pid"
done

run "GET /me/cart (empty)" GET /me/cart "" \
"import sys,json; d=json.load(sys.stdin); assert d['itemCount']==0 and d['subtotal']==0; print('cart empty')"

run "POST add prod-1 qty 1" POST /me/cart/items \
  '{"productId":"prod-1","quantity":1,"selectedOptions":{"color":"slate","size":"M"}}' \
"import sys,json; d=json.load(sys.stdin); assert d['itemCount']==1 and d['subtotal']==220.0; print(f'1 item, subtotal={d[\"subtotal\"]}')"

run "POST add prod-1 again (bumps qty)" POST /me/cart/items '{"productId":"prod-1","quantity":1}' \
"import sys,json; d=json.load(sys.stdin); assert d['itemCount']==2 and d['subtotal']==440.0; print(f'qty bumped, subtotal={d[\"subtotal\"]}')"

run "PATCH prod-1 qty=3" PATCH /me/cart/items/prod-1 '{"quantity":3}' \
"import sys,json; d=json.load(sys.stdin); assert d['itemCount']==3 and d['subtotal']==660.0; print(f'patched qty=3 subtotal={d[\"subtotal\"]}')"

run "DELETE prod-1" DELETE /me/cart/items/prod-1 "" \
"import sys,json; d=json.load(sys.stdin); assert d['itemCount']==0; print('cart empty after delete')"

# ===== M3 WISHLIST (3) =====
echo
echo "===== M3 WISHLIST ====="
for pid in prod-10 prod-12; do
    curl -s -o /dev/null -X DELETE -H "$H" "$BASE/me/wishlist/items/$pid"
done

run "GET /me/wishlist (empty)" GET /me/wishlist "" \
"import sys,json; d=json.load(sys.stdin); assert d['items']==[]; print('wishlist empty')"

run "POST add prod-12" POST /me/wishlist/items '{"productId":"prod-12"}' \
"import sys,json; d=json.load(sys.stdin); assert len(d['items'])==1 and d['items'][0]['slug']=='orbit-noise-headphones'; print(f'added: {d[\"items\"][0][\"name\"]}')"

run "DELETE prod-12" DELETE /me/wishlist/items/prod-12 "" \
"import sys,json; d=json.load(sys.stdin); assert d['items']==[]; print('wishlist empty after delete')"

# ===== M3 CHECKOUT (1) =====
echo
echo "===== M3 CHECKOUT ====="
# Stage a known cart, then run checkout and verify the side effects:
#   - cart cleared
#   - orders count bumped by exactly 1
#   - newest order total recomputed server-side from the catalog
#     (client-supplied subtotal=9999 is ignored — anti-tamper)
curl -s -o /dev/null -X POST -H "$H" -H "$JSON" -d '{"productId":"prod-7","quantity":2}' "$BASE/me/cart/items"
curl -s -o /dev/null -X POST -H "$H" -H "$JSON" -d '{"productId":"prod-3","quantity":1}' "$BASE/me/cart/items"

ORDERS_BEFORE=$(curl -s -H "$H" "$BASE/me/orders" | python3 -c "import sys,json; print(json.load(sys.stdin)['total'])")
echo "  staged cart with 2 SKUs; orders before checkout: $ORDERS_BEFORE"

run "POST /checkout" POST /checkout \
  '{"email":"demo@hyperpersona.dev","fullName":"Ava Chen","address":"12 Rue Editoriale","city":"Montreal","country":"CA","paymentMethod":"card","subtotal":9999,"items":[{"productId":"prod-7","quantity":2},{"productId":"prod-3","quantity":1}]}' \
"import sys,json; d=json.load(sys.stdin); assert d['status']=='confirmed' and d['orderId'].startswith('ord-'); print(f'orderId={d[\"orderId\"]} placedAt={d[\"placedAt\"][:19]}')"

# Verify side effects.
EXPECTED_TOTAL=$(python3 -c "print(2*24 + 1*110)")  # prod-7 = $24, prod-3 = $110 -> $158
ORDERS_AFTER_JSON=$(curl -s -H "$H" "$BASE/me/orders")
NEW_TOTAL=$(echo "$ORDERS_AFTER_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['items'][0]['total'])")
NEW_COUNT=$(echo "$ORDERS_AFTER_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['total'])")
CART_COUNT=$(curl -s -H "$H" "$BASE/me/cart" | python3 -c "import sys,json; print(json.load(sys.stdin)['itemCount'])")
EXPECTED_COUNT=$((ORDERS_BEFORE + 1))

if [ "$CART_COUNT" = "0" ] && [ "$NEW_COUNT" = "$EXPECTED_COUNT" ] && nearly_equal "$NEW_TOTAL" "$EXPECTED_TOTAL"; then
    echo "  cart cleared (0 items) + new order (${ORDERS_BEFORE} -> ${NEW_COUNT}) + server total=$NEW_TOTAL (expected $EXPECTED_TOTAL, client claimed 9999)"
    pass "checkout side-effects: cart cleared, order persisted with server-recomputed total"
else
    fail "checkout side-effects (cart=$CART_COUNT orders=$NEW_COUNT/$EXPECTED_COUNT total=$NEW_TOTAL/$EXPECTED_TOTAL)"
fi

echo
echo "============================="
echo "PASSED: $PASS    FAILED: $FAIL"
echo "============================="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
