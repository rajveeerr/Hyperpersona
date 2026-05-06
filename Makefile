.PHONY: up down logs build server worker restart-worker clean ps

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

ps:
	docker compose ps

clean:
	docker compose down -v
