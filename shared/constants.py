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
