# HyperPersona

Three deployment units: **server** (FastAPI REST API), **worker** (Python job runner), and (later) **AgentCore Runtime** for the supervisor agent. See [plan.md](plan.md) for the full phase-by-phase build plan.

## Phase 1 status

Scaffold only — both Docker images build, both services boot, no business logic.

## Quick start

```bash
make up                              # build + start server, worker, redis, dynamodb-local
curl http://localhost:8000/health    # → {"status":"ok","service":"server"}
docker logs hyperpersona-worker-1    # → "worker started, waiting for jobs ..."
make down                            # stop everything
```

## Layout

```text
server/    FastAPI REST API (Docker image #1)
worker/    Python job runner (Docker image #2)
shared/    Pydantic models, queue/table/collection name constants
scripts/   DynamoDB / OpenSearch setup helpers (placeholders)
```

## Services and ports

| Service        | Host port | Purpose                                                                                     |
| -------------- | --------- | ------------------------------------------------------------------------------------------- |
| server         | 8000      | FastAPI REST API                                                                            |
| dynamodb-local | 8001      | DynamoDB-compatible KV                                                                      |
| redis          | —         | Job queue + cache (internal only — `docker exec hyperpersona-redis-1 redis-cli` to inspect) |
| worker         | —         | Background processor                                                                        |

## Hot reload

`server/src` and `shared/` are bind-mounted into the server container, and uvicorn runs with `--reload`. Edit a file → uvicorn restarts automatically.

The worker doesn't auto-reload. After changing worker code, run `make restart-worker`.

## Makefile targets

| Target                | What it does                                       |
| --------------------- | -------------------------------------------------- |
| `make up`             | Build + start the full stack                       |
| `make down`           | Stop the stack                                     |
| `make logs`           | Tail logs from all services                        |
| `make server`         | Tail server logs                                   |
| `make worker`         | Tail worker logs                                   |
| `make restart-worker` | Restart the worker (use after worker code edits)   |
| `make ps`             | Show service status                                |
| `make clean`          | Stop and remove volumes                            |

> Windows note: `make` is not built in. Either install it (Chocolatey: `choco install make`) or run the underlying `docker compose` commands directly.

## Environment variables

Copy `.env.example` → `.env` if you want to override defaults. The compose file already injects sensible defaults for local dev.
