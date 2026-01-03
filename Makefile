.PHONY: env dev deploy help

env: ## Validate .env loads successfully (does not persist vars)
	@bash -c 'source scripts/env.sh'

dev: ## Run local dev server (FastAPI/uvicorn)
	@bash -c 'source scripts/env.sh && cd collector && uvicorn app.main:app --reload --host 0.0.0.0 --port $${PORT:-8080}'

deploy: ## Deploy to Cloud Run
	@bash scripts/deploy.sh

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*##"; print "Usage: make <target>\n\nTargets:"} /^[a-zA-Z_-]+:.*##/ {printf "  %-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
