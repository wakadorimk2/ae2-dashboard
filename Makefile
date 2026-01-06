.PHONY: env dev dev-local deploy test test-agg test-ci prune help

env: ## Validate .env loads successfully (does not persist in your shell)
	@bash -c 'source scripts/env.sh'

dev: ## Run local dev via Docker (Cloud Run equivalent)
	@bash scripts/docker-dev.sh

dev-local: ## Run local FastAPI dev server (no Docker, no Vite build)
	@bash -c 'source scripts/env.sh && cd collector && uvicorn app.main:app --reload --host 0.0.0.0 --port $${PORT:-8080}'

deploy: ## Deploy to Cloud Run
	@bash scripts/deploy.sh

test: ## Fast local tests (no external deps)
	@bash -c 'cd collector && pytest -q'

test-ci: ## Full test suite (may require env / external deps)
	@bash -c 'source scripts/env.sh && cd collector && pytest -q'

test-agg: ## Manual integration test (real Aggregate call)
	@bash -c 'source scripts/env.sh && python collector/scripts/aggregate_real.py'

prune: ## Prune deleted remote branches + delete local branches whose upstream is gone (safe)
	@bash -c 'git fetch --prune && git branch -vv | awk '"'"'/: gone]/{print $$1}'"'"' | xargs -r git branch -d'

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*##"; print "Usage: make <target>\n\nTargets:"} /^[a-zA-Z_-]+:.*##/ {printf "  %-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)