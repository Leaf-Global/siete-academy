.PHONY: help demo install seed test test-backend test-frontend test-e2e dev-backend dev-frontend clean

UV_BIN := $(HOME)/.local/bin/uv
NODE_BIN := $(HOME)/.nvm/versions/node/v24.13.0/bin
NODE_EXPORT := export PATH="$(NODE_BIN):$$PATH"

help:
	@echo "Siete Academy — make targets"
	@echo ""
	@echo "  make demo             Install + seed + run backend & frontend  (one-shot for local)"
	@echo "  make install          Install backend venv, frontend deps, e2e deps"
	@echo "  make seed             Reset local SQLite DB and load rich demo data"
	@echo "  make test             backend + frontend + e2e"
	@echo "  make test-backend     pytest for FastAPI modules"
	@echo "  make test-frontend    vitest for React components"
	@echo "  make test-e2e         Playwright smoke"
	@echo "  make dev-backend      uvicorn hot-reload on :8000 (SQLite)"
	@echo "  make dev-frontend     vite dev server on :5173"
	@echo "  make clean            Remove venvs, node_modules, local DB"

install:
	@echo "▶ backend venv + deps"
	cd backend && $(UV_BIN) venv --python 3.12 .venv
	cd backend && $(UV_BIN) pip install -r requirements-dev.txt --python .venv/bin/python
	@echo "▶ frontend deps"
	$(NODE_EXPORT) && cd frontend && npm install
	@echo "▶ e2e deps + playwright browsers"
	$(NODE_EXPORT) && cd e2e && npm install && npx playwright install chromium

seed:
	@echo "▶ Reset local SQLite DB"
	rm -f backend/siete_academy.db
	@echo "▶ Seed rich demo data"
	cd backend && DATABASE_URL="sqlite:///siete_academy.db" APP_ENV=development .venv/bin/python -m app.scripts.seed

demo:
	@test -d backend/.venv || $(MAKE) install
	@test -d frontend/node_modules || ($(NODE_EXPORT) && cd frontend && npm install)
	@$(MAKE) seed
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  Siete Academy — local demo"
	@echo ""
	@echo "  Frontend:  http://localhost:5173/academy/"
	@echo "  Backend:   http://localhost:8000/docs"
	@echo ""
	@echo "  Login en /academy/login → botones de rol (demo local):"
	@echo "    • Admin      → admin@siete.com"
	@echo "    • Profesor   → teacher@siete.com"
	@echo "    • Alumno     → student@siete.com"
	@echo "    • Reclutador → recruiter@siete.com"
	@echo ""
	@echo "  Ctrl+C para detener ambos servicios."
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@DATABASE_URL="sqlite:///siete_academy.db" APP_ENV=development DEV_AUTH_BYPASS=true \
		bash -c 'trap "kill 0" EXIT; \
			(cd backend && DATABASE_URL="sqlite:///siete_academy.db" APP_ENV=development DEV_AUTH_BYPASS=true .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000) & \
			($(NODE_EXPORT) && cd frontend && npm run dev -- --port 5173) & \
			wait'

test: test-backend test-frontend test-e2e

test-backend:
	cd backend && .venv/bin/python -m pytest -v

test-frontend:
	$(NODE_EXPORT) && cd frontend && npm run test

test-e2e:
	$(NODE_EXPORT) && cd e2e && npm run test

dev-backend:
	cd backend && DATABASE_URL="sqlite:///siete_academy.db" APP_ENV=development DEV_AUTH_BYPASS=true \
		.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

dev-frontend:
	$(NODE_EXPORT) && cd frontend && npm run dev

clean:
	rm -rf backend/.venv backend/.pytest_cache backend/htmlcov backend/.coverage backend/coverage.xml backend/siete_academy.db
	rm -rf frontend/node_modules frontend/dist frontend/coverage
	rm -rf e2e/node_modules e2e/playwright-report e2e/test-results
