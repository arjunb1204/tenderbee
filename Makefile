# ==============================================================================
# TenderBee Monorepo Automation (Makefile)
# ==============================================================================

.PHONY: help run run-backend run-frontend migrate test audit openapi

help:
	@echo "Available commands:"
	@echo "  make run          - Run local environment via docker compose"
	@echo "  make run-backend  - Run Django REST backend server (port 8000)"
	@echo "  make run-frontend - Run Next.js frontend application (port 3000)"
	@echo "  make migrate      - Run Django database migrations using DIRECT_URL"
	@echo "  make test         - Run all test suites (security, engine, golden, apps, and frontend build)"
	@echo "  make audit        - Run dependency vulnerability audits (pip-audit & npm audit)"
	@echo "  make openapi      - Regenerate OpenAPI YAML schema and TypeScript types"

# 1. Run local environment
run:
	docker compose up

run-backend:
	python backend/manage.py runserver 127.0.0.1:8000

run-frontend:
	npm --prefix frontend run dev

# 2. Database migrations against Neon DIRECT_URL
migrate:
	DATABASE_URL=$${DIRECT_URL} python backend/manage.py migrate

# 3. Comprehensive testing (Security tests, Unit tests, Golden tests, Frontend build)
test:
	python backend/manage.py test apps.accounts.test_security apps.accounts.tests apps.documents.tests
	python -m pytest backend/golden/test_golden.py
	npm --prefix frontend run build

# 4. Dependency Vulnerability Audits
audit:
	pip-audit -r backend/requirements.txt
	npm --prefix frontend audit

# 5. OpenAPI Schema and TypeScript Types Generation
openapi:
	python backend/manage.py spectacular --file schema.yaml
	npx openapi-typescript schema.yaml -o frontend/src/lib/api-types.ts
