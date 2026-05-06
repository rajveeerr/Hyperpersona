"""Queue names, table names, and collection names shared between services."""

# Redis queues
QUEUE_PENDING = "jobs:pending"

# DynamoDB tables
TABLE_CUSTOMER_EVENTS = "customer_events"
TABLE_CUSTOMER_CONSENT = "customer_consent"
TABLE_CUSTOMER_AUTH = "customer_auth"
TABLE_JOBS = "jobs"
# Ecommerce tables (catalog + reviews + profile + cart/wishlist + orders)
TABLE_PRODUCTS = "products"
TABLE_CATEGORIES = "categories"
TABLE_PRODUCT_REVIEWS = "product_reviews"
TABLE_REVIEW_VOTES = "review_votes"
TABLE_CUSTOMER_PROFILE = "customer_profile"
TABLE_CART_ITEMS = "cart_items"
TABLE_WISHLIST_ITEMS = "wishlist_items"
TABLE_ORDERS = "orders"
# Recommender catalog (separate from the storefront `products` table —
# used by the complement-products recommender for prompt-time lookups).
TABLE_PRODUCT_CATALOG = "product_catalog"

# OpenSearch collections
COLLECTION_FACTS = "customer-facts"
COLLECTION_BEHAVIOR = "behavior-embeddings"
COLLECTION_SESSIONS = "session-summaries"
COLLECTION_PRODUCTS = "product-catalog"

# Tiered processing — only these event types trigger the full supervisor
# pipeline (Bedrock embed + generate + per-fact embed). Everything else is
# cheap-stored and rolled up into a single session summary periodically.
HIGH_SIGNAL_EVENT_TYPES = frozenset({
    "purchase", "add_to_cart", "return", "search",
})

# Event-status values used by the worker's tiered routing
EVENT_STATUS_PROCESSED = "processed"             # full supervisor ran
EVENT_STATUS_CHEAP = "processed_cheap"           # cheap-stored, awaiting summary
EVENT_STATUS_AGGREGATED = "aggregated"           # rolled up into a session summary

# Complement recommender — KNN candidate-generation tuning. Over-fetch K from
# OpenSearch, then post-filter (cart slugs + out-of-stock + optional vertical
# distinction) down to TOP_CANDIDATES before the LLM sees them.
COMPLEMENT_KNN_K = 80
COMPLEMENT_TOP_CANDIDATES = 30
# Blend weight for the user-preference vector: query_vec = (1-α)·cart + α·pref.
# Cart stays dominant — pair-up is cart-driven first, preference-flavored
# second. Bumping above ~0.5 risks recommending things the customer likes that
# don't actually pair with the cart contents.
COMPLEMENT_PREF_WEIGHT = 0.3

# General recommender — products picker tuning. Over-fetch K from OpenSearch
# product-catalog (KNN over blended context+preference vector), then drop
# out-of-stock and cap at PRODUCTS_LIMIT for the frontend rail. Blend weight
# reuses COMPLEMENT_PREF_WEIGHT — same intent, same range of acceptable values.
RECOMMEND_KNN_K = 60
RECOMMEND_PRODUCTS_LIMIT = 6
