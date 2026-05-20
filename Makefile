# =============================================================================
# mt-ecommerce — comandos de desarrollo
# =============================================================================
# Uso:
#   make test            → corre backend + frontend
#   make test-backend    → pytest (unit + integration); levanta testcontainers
#   make test-frontend   → tsc typecheck + vitest
#   make lint            → ruff (backend) + eslint (frontend)
#   make lint-backend    → ruff check + format --check
#   make lint-frontend   → eslint
#   make typecheck       → mypy (backend) + tsc (frontend)
#
# Prerequisitos locales:
#   - Docker en ejecución (para testcontainers del backend)
#   - uv instalado (https://docs.astral.sh/uv/)
#   - pnpm instalado (https://pnpm.io/)
# =============================================================================

.PHONY: test test-backend test-frontend \
        lint lint-backend lint-frontend \
        typecheck typecheck-backend typecheck-frontend \
        help

# Directorios de subproyecto
BACKEND  := mt-pricing-backend
FRONTEND := mt-pricing-frontend

# ---------------------------------------------------------------------------
# test
# ---------------------------------------------------------------------------

test: test-backend test-frontend

test-backend:
	@echo "▶ Backend — pytest (unit + integration)"
	cd $(BACKEND) && uv run pytest \
		-m "unit or integration" \
		--tb=short \
		--cov=app \
		--cov-report=term-missing \
		--cov-fail-under=70 \
		-v

test-frontend:
	@echo "▶ Frontend — typecheck + vitest"
	cd $(FRONTEND) && pnpm typecheck
	cd $(FRONTEND) && pnpm test --reporter=verbose

# ---------------------------------------------------------------------------
# lint
# ---------------------------------------------------------------------------

lint: lint-backend lint-frontend

lint-backend:
	@echo "▶ Backend — ruff"
	cd $(BACKEND) && uv run ruff check .
	cd $(BACKEND) && uv run ruff format --check .

lint-frontend:
	@echo "▶ Frontend — eslint"
	cd $(FRONTEND) && pnpm lint

# ---------------------------------------------------------------------------
# typecheck
# ---------------------------------------------------------------------------

typecheck: typecheck-backend typecheck-frontend

typecheck-backend:
	@echo "▶ Backend — mypy"
	cd $(BACKEND) && uv run mypy app/

typecheck-frontend:
	@echo "▶ Frontend — tsc"
	cd $(FRONTEND) && pnpm typecheck

# ---------------------------------------------------------------------------
# help
# ---------------------------------------------------------------------------

help:
	@echo ""
	@echo "Targets disponibles:"
	@echo "  make test              Corre backend + frontend"
	@echo "  make test-backend      pytest (unit + integration) — requiere Docker"
	@echo "  make test-frontend     tsc typecheck + vitest"
	@echo "  make lint              ruff + eslint"
	@echo "  make typecheck         mypy + tsc"
	@echo ""
