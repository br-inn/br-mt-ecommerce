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
        test-e2e test-e2e-remote seed-e2e-users \
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
# e2e — Playwright (requiere usuarios seed; ver docs/e2e-test-users.md)
# ---------------------------------------------------------------------------

# Local Docker stack (E2E_USE_REAL_SUPABASE=1 + usuarios seed)
E2E_LOCAL_URL ?= http://localhost:8081

test-e2e:
	@echo "▶ E2E — Playwright contra Docker local"
	cd $(FRONTEND) && \
	  E2E_BASE_URL=$(E2E_LOCAL_URL) \
	  E2E_USE_REAL_SUPABASE=1 \
	  pnpm test:e2e --project=chromium

# Contra servidor remoto: make test-e2e-remote E2E_URL=https://100-53-214-97.sslip.io
E2E_URL ?= https://100-53-214-97.sslip.io

test-e2e-remote:
	@echo "▶ E2E — Playwright contra $(E2E_URL)"
	cd $(FRONTEND) && \
	  E2E_BASE_URL=$(E2E_URL) \
	  E2E_BACKEND_URL=$(E2E_URL) \
	  E2E_USE_REAL_SUPABASE=1 \
	  pnpm test:e2e --project=chromium

# Crea/actualiza los usuarios E2E en Supabase Auth + public.users
seed-e2e-users:
	@echo "▶ Seed usuarios E2E (docker exec mt-backend)"
	docker exec mt-backend python -m scripts.seed_e2e_users

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
	@echo "  make seed-e2e-users    Crea/actualiza usuarios E2E en Supabase + DB"
	@echo "  make test-e2e          E2E Playwright — Docker local (E2E_LOCAL_URL=…)"
	@echo "  make test-e2e-remote   E2E Playwright — servidor remoto (E2E_URL=…)"
	@echo ""
	@echo "Docs: docs/e2e-test-users.md"
	@echo ""
