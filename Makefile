# Verity: the everyday commands. Run `make` to list them.
.DEFAULT_GOAL := help
.PHONY: help setup dev test eval fixtures build up smoke warm

IMAGE := verity:dev
# uv stops if --env-file points at a missing file, so pass it only when .env exists.
ENV_FILE := $(if $(wildcard .env),--env-file .env)

help: ## List the commands
	@grep -E '^[a-z]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  make %-9s %s\n", $$1, $$2}'

setup: ## Install backend and frontend dependencies, and create .env from the example
	uv sync
	cd frontend && pnpm install --frozen-lockfile
	@test -f .env || { cp .env.example .env; echo "Created .env. Add at least one API key to it."; }

dev: ## API with reload on :8000 and the UI on :5173 (open http://localhost:5173, Ctrl-C stops both)
	@trap 'kill 0' INT TERM EXIT; \
	uv run $(ENV_FILE) uvicorn app.main:app --app-dir backend --reload --port 8000 & \
	(cd frontend && pnpm dev --port 5173) & \
	wait

test: ## Backend tests, packaging checks and the frontend type check. No model is ever called.
	uv run pytest -q backend/tests .github/scripts
	cd frontend && pnpm typecheck

eval: ## Grade the app on the golden questions with the real model, e.g. make eval ARGS="--split dev"
	PYTHONPATH=backend:. uv run $(ENV_FILE) python -m eval.run_eval $(ARGS)

fixtures: ## Regenerate the UI's mock data after a change to contracts.py
	PYTHONPATH=backend:. uv run python backend/scripts/make_fixtures.py

build: ## Build the Docker image
	docker build -t $(IMAGE) .

up: ## Run the app in Docker at http://localhost:8000
	docker compose up --build

# PORT is set the way a host such as Render sets it, so this also proves the image obeys it.
# Up to 30 one-second tries: a cold CI runner needs a few seconds to import pandas and DuckDB.
smoke: build ## Start the image locked down like compose, on a host-chosen PORT; check health, the UI, non-root, no secrets inside
	@docker rm -f verity-smoke >/dev/null 2>&1 || true
	docker run -d --name verity-smoke -e PORT=8011 -p 8011:8011 --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges $(IMAGE)
	@ok=1; for i in $$(seq 1 30); do \
		sleep 1; curl -fs localhost:8011/healthz && ok=0 && break; \
	done; \
	curl -fs localhost:8011/ | grep -q 'id="root"' || { echo "The built UI is not served at /."; ok=1; }; \
	test "$$(docker exec verity-smoke id -u)" = "1000" || { echo "The container is not running as uid 1000."; ok=1; }; \
	stray=$$(docker exec verity-smoke find /app -path /app/.venv -prune -o \
		\( -name '.env*' -o -name '*.env' -o -name '*.pem' -o -name '*.key' -o -name .git -o -name node_modules -o -name .playwright-mcp \) -print); \
	test -z "$$stray" || { echo "These must never be in the image: $$stray"; ok=1; }; \
	test $$ok = 0 || docker logs verity-smoke; \
	docker rm -f verity-smoke >/dev/null; echo; exit $$ok

warm: ## Wake a deployed app and pre-answer the starter questions: make warm URL=https://...
	@test -n "$(URL)" || { echo "Usage: make warm URL=https://your-app.onrender.com"; exit 2; }
	@python3 .github/scripts/warm.py "$(URL)"
