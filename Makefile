.PHONY: up down logs build server worker restart-worker setup-db setup-opensearch seed-consent scan-events scan-jobs scan-consent scan-vectors peek-queue test-bedrock test-tools test-recommend test-privacy test-e2e demo-conflict demo-tiered demo-backpressure demo-scale demo-async-recommend scale worker-count show-trace clean ps

up:
	docker compose up -d --build

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

server:
	docker compose logs -f server

worker:
	docker compose logs -f worker

# Worker has no auto-reload — restart it after worker code changes.
restart-worker:
	docker compose restart worker

# Phase 2 — DynamoDB tables and queue inspection
setup-db:
	docker compose exec server python /app/scripts/setup_dynamodb.py

# Phase 7 — OpenSearch indexes and vector inspection
setup-opensearch:
	docker compose exec worker python /app/scripts/setup_opensearch.py

# usage: make scan-vectors COLL=customer-facts CUST=cust_1
# CUST is optional; omit it to scan everything in the collection
scan-vectors:
	docker compose exec worker python /app/scripts/scan_vectors.py $(COLL) $(CUST)

scan-events:
	docker compose exec server python /app/scripts/scan.py customer_events

scan-jobs:
	docker compose exec server python /app/scripts/scan.py jobs

scan-consent:
	docker compose exec server python /app/scripts/scan.py customer_consent

peek-queue:
	docker exec hyperpersona-redis-1 redis-cli LRANGE jobs:pending 0 -1

# Phase 4 — Bedrock wrapper sanity test (mock or real, depending on BEDROCK_MODE)
test-bedrock:
	docker compose exec worker python /app/scripts/test_bedrock.py

# Phase 5 — Seed test consent records and run all four agent tools
seed-consent:
	docker compose exec worker python /app/scripts/seed_consent.py

test-tools:
	docker compose exec worker python /app/scripts/test_tools.py

# Phase 6 — Show the agent trace for one job: make show-trace JOB=<job_id>
show-trace:
	docker compose exec worker python /app/scripts/show_trace.py $(JOB)

# Phase 8 — Hit GET /recommend: make test-recommend CUST=cust_1 CTX="outdoor gear"
test-recommend:
	curl -s -H "X-API-Key: test-key" \
	  --data-urlencode "customer_id=$(CUST)" \
	  --data-urlencode "context=$(CTX)" \
	  -G "http://localhost:8000/recommend"

# Phase 11 — End-to-end privacy + GDPR delete verification
test-privacy:
	docker compose exec server python /app/scripts/test_privacy.py

# Phase 12 — Full happy-path demo + ACE conflict-detection demo
test-e2e:
	docker compose exec server python /app/scripts/test_e2e.py

demo-conflict:
	docker compose exec server python /app/scripts/conflict_demo.py

# Step 2 — tiered processing: high-signal events run the supervisor,
# low-signal events get cheap-stored and rolled into session summaries.
demo-tiered:
	docker compose exec server python /app/scripts/demo_tiered.py

# Step 4 — backpressure + per-customer rate limit
demo-backpressure:
	docker compose exec server python /app/scripts/demo_backpressure.py

# Step 5 — horizontal worker scaling
# Usage: make scale N=4   (defaults to 4)
N ?= 4
scale:
	docker compose up -d --scale worker=$(N) worker

worker-count:
	docker compose ps worker --format "table {{.Name}}\t{{.Status}}"

# Stress test: send 40 high-signal events, time how long until they all complete.
# Run before/after `make scale N=4` to see the throughput speedup.
demo-scale:
	docker compose exec server python /app/scripts/demo_scale.py

# Step 6 — async /recommend handler. Fires N concurrent /recommend, shows
# they run in parallel on the server's event loop instead of serialising.
demo-async-recommend:
	docker compose exec server python /app/scripts/demo_async_recommend.py

ps:
	docker compose ps

clean:
	docker compose down -v
