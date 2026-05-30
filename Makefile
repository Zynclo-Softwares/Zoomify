.PHONY: install backend frontend stripe-forward dev help format format-py format-ts format-tf \
	frontend-build docker-build docker-run docker-up docker

.DEFAULT_GOAL := help

IMAGE_NAME ?= zoomify
DOCKER_PORT ?= 8000
DOCKERFILE ?= Dockerfile
# Backend secrets for `make docker-run` (not baked into the image — injected at runtime)
ENV_FILE ?= .env

# Pick up VITE_CLERK_PUBLISHABLE_KEY from frontend/.env.local when not exported.
-include frontend/.env.local
export VITE_CLERK_PUBLISHABLE_KEY

help:
	@echo "Zoomify — common commands"
	@echo ""
	@echo "  Development"
	@echo "    make install          Install Python (uv) + frontend (bun) deps"
	@echo "    make dev              Backend + Stripe webhooks + Vite dev UI"
	@echo "    make backend          FastAPI only → http://127.0.0.1:8000"
	@echo "    make frontend         Vite dev server → http://127.0.0.1:5173"
	@echo ""
	@echo "  Production bundle (Docker)"
	@echo "    make docker-build     Build image (bun build + uv inside Docker)"
	@echo "    make docker-run       Run image locally on port $(DOCKER_PORT) (loads $(ENV_FILE))"
	@echo "    make docker-up        Build then run (quick local prod test)"
	@echo "    make docker           Alias for make docker-up"
	@echo ""
	@echo "  Frontend only"
	@echo "    make frontend-build   Build SPA → frontend/dist (served by server.py)"
	@echo ""
	@echo "  Formatting & fixes"
	@echo "    make format           Format + auto-fix Python, TS, and Terraform"
	@echo "    make format-py        ruff format + ruff check --fix"
	@echo "    make format-ts        biome check --write (format, lint, imports)"
	@echo "    make format-tf        terraform fmt -recursive terraform/"
	@echo ""
	@echo "  Stripe"
	@echo "    make stripe-forward   Forward Stripe webhooks to localhost"

# Install Python + frontend dependencies (run once after clone / branch switch)
install:
	uv sync --dev
	@command -v bun >/dev/null 2>&1 || { \
		echo "Bun not found. Install: curl -fsSL https://bun.sh/install | bash"; \
		exit 1; \
	}
	cd frontend && bun install --frozen-lockfile

# FastAPI backend (http://127.0.0.1:8000)
backend:
	uv run python -m uvicorn server:app --reload --host 127.0.0.1 --port 8000

# React dev server (http://127.0.0.1:5173, proxies /api → backend)
frontend:
	cd frontend && bun run dev

# Forward Stripe webhooks to the local billing endpoint (run in a separate terminal if needed)
stripe-forward:
	@command -v stripe >/dev/null 2>&1 || { \
		echo "Stripe CLI not found. Install: brew install stripe/stripe-cli/stripe"; \
		exit 1; \
	}
	stripe listen \
		--forward-to localhost:8000/api/billing/webhook \
		--events checkout.session.completed,customer.subscription.created,customer.subscription.updated,customer.subscription.deleted

# Backend + Stripe CLI + frontend (Stripe forwards webhooks to /api/billing/webhook)
dev:
	@echo "Starting backend…"
	@uv run python -m uvicorn server:app --reload --host 127.0.0.1 --port 8000 & \
	BACKEND_PID=$$!; \
	STRIPE_PID=""; \
	trap 'kill $$BACKEND_PID $$STRIPE_PID 2>/dev/null' EXIT INT TERM; \
	for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do \
		curl -sf http://127.0.0.1:8000/api/health >/dev/null 2>&1 && break; \
		sleep 0.5; \
	done; \
	curl -sf http://127.0.0.1:8000/api/health >/dev/null 2>&1 || { \
		echo "Backend did not start. Run: make install"; \
		exit 1; \
	}; \
	echo "Backend ready → http://127.0.0.1:8000"; \
	if command -v stripe >/dev/null 2>&1; then \
		echo "Starting Stripe webhook forwarder → http://127.0.0.1:8000/api/billing/webhook"; \
		echo "Copy the whsec_... secret into STRIPE_WEBHOOK_SECRET in .env when it appears below."; \
		stripe listen \
			--forward-to localhost:8000/api/billing/webhook \
			--events checkout.session.completed,customer.subscription.created,customer.subscription.updated,customer.subscription.deleted \
			2>&1 & \
		STRIPE_PID=$$!; \
	else \
		echo "Stripe CLI not found — webhooks will not forward locally."; \
		echo "Install: brew install stripe/stripe-cli/stripe  (or run: make stripe-forward)"; \
	fi; \
	echo "Starting frontend → http://127.0.0.1:5173"; \
	$(MAKE) frontend

# Build React bundle to frontend/dist (same path FastAPI + Docker use)
frontend-build:
	cd frontend && bun run build

# Format + auto-fix — Python (ruff), frontend (biome), Terraform (terraform fmt)
format: format-py format-ts format-tf

format-py:
	uv run ruff format src tests server.py app.py
	uv run ruff check --fix src tests server.py app.py

format-ts:
	cd frontend && bun run format

format-tf:
	@command -v terraform >/dev/null 2>&1 || { \
		echo "Skipping terraform fmt (install: brew install terraform)"; \
		exit 0; \
	}; \
	terraform fmt -recursive terraform

# Production Docker image — frontend bun build + Python venv, bundled in one image
docker-build:
	@echo "Building Docker image '$(IMAGE_NAME)' (frontend/dist + backend)…"
	@if [ -z "$$VITE_CLERK_PUBLISHABLE_KEY" ]; then \
		echo "Note: VITE_CLERK_PUBLISHABLE_KEY not set — Clerk UI will be disabled in the bundle."; \
		echo "      Add it to frontend/.env.local or export before building."; \
	fi
	docker build -t $(IMAGE_NAME) \
		--build-arg VITE_CLERK_PUBLISHABLE_KEY=$${VITE_CLERK_PUBLISHABLE_KEY:-} \
		-f $(DOCKERFILE) .

# Run the production image locally — injects backend env from $(ENV_FILE), not from the image
docker-run:
	@test -f $(ENV_FILE) || { echo "Missing $(ENV_FILE) — copy .env.example and fill in secrets."; exit 1; }
	docker run --rm --env-file $(ENV_FILE) -p $(DOCKER_PORT):8000 $(IMAGE_NAME)

# Build + run in one step — easiest way to test the production container locally
docker-up: docker-build docker-run

docker: docker-up
