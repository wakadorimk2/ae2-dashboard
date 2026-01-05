.PHONY: env dev dev-local deploy help

env: ## Validate .env loads successfully (does not persist vars)
	@bash -c 'source scripts/env.sh'

dev: ## Run local dev via Docker (Cloud Run equivalent)
	@bash scripts/docker-dev.sh

dev-local: ## Run local FastAPI dev server (no Docker, no Vite build)
	@bash -c 'source scripts/env.sh && cd collector && uvicorn app.main:app --reload --host 0.0.0.0 --port $${PORT:-8080}'

deploy: ## Deploy to Cloud Run
	@bash scripts/deploy.sh

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*##"; print "Usage: make <target>\n\nTargets:"} /^[a-zA-Z_-]+:.*##/ {printf "  %-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)