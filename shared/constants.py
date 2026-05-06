"""Queue names, table names, and collection names shared between services."""

# Redis queues
QUEUE_PENDING = "jobs:pending"

# DynamoDB tables
TABLE_CUSTOMER_EVENTS = "customer_events"
TABLE_CUSTOMER_CONSENT = "customer_consent"
TABLE_JOBS = "jobs"

# OpenSearch collections
COLLECTION_FACTS = "customer-facts"
COLLECTION_BEHAVIOR = "behavior-embeddings"
COLLECTION_SESSIONS = "session-summaries"

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
