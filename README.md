<div align="center">
  <img src="frontend/public/zoomify-logo.png" alt="Zoomify logo" width="88" />
  <h1>Zoomify — Image Detail Extraction Agent</h1>
  <p><strong>Vision LLMs are bad at reading whole images when the detail matters.</strong></p>
</div>

Send a blueprint, site map, engineering diagram, long desktop screenshot, dense
dashboard, or any large info graphic to GPT-4o (or similar) in one shot and it
will miss labels, invent values, or skim past the tiny parts — small UI icons,
footnote text, legend entries, breaker ratings, parcel IDs, and table cells that
only become readable when you zoom in. The model sees the full frame at once;
it does not naturally pan, magnify, and re-read the way a human would with a
PDF viewer.

**Zoomify is a helper agent for exactly that.** Upload the image, ask a question,
and a vision model navigates a **labeled grid** — cropping, upscaling,
and re-gridding regions until it can read the small print. It works like a
human using zoom on a site plan or SLD: start at the overview, drill into the
cells that matter, back out and retry if the wrong area was picked.

Built for coders who need to **extract structured data from images models
normally fail on**:

- **Blueprints & single-line diagrams** — electrical, mechanical, architectural
- **Site maps & parcel plans** — boundaries, labels, legend text
- **Large desktop / app screenshots** — toolbars, status bars, small icons
- **Long scrolling captures** — chat logs, tables, multi-panel UIs
- **Posters, scans, and dense infographics** — mixed font sizes on one canvas

The **primary app** is a **React UI** backed by **FastAPI**. You bring your own
**OpenRouter API key** (encrypted in the browser; decrypted only on the server).
Platform usage on `POST /api/query` is metered by subscription tier. A legacy
**Gradio** UI (`app.py`) remains for quick experiments.

## Tools

| Tool | What it does |
|------|--------------|
| **zoom** | Crops a selected cell/region (e.g. `2C`, `1-3-B-E`), upscales it, re-grids it, and **pushes** a step onto the stack. |
| **undo** | **Pops** the last zoom step (step back one level). |
| **redo** | Re-pushes the step you last popped with `undo`. |
| **restore** | Clears the stack back to the **root** — full auto-gridded image. |

The current view is always the top of the stack. Each step is stored as a
**recipe** (selection + zoom + regrid settings); the gridded image is rendered
from the original on demand — no branching node tree or stored intermediates.
Wrong zoom → `undo` → try again; the trail **collapses** as you pop. Engine
files: `src/zoomify/gridder.py` (grid overlay) and `src/zoomify/gridzoom.py`
(crop, zoom, path rendering).

## Project layout

```
Zoomify/
├── pyproject.toml              # uv project
├── .env.example                # BYOK, Clerk, MongoDB, Stripe
├── Makefile                    # install, backend, frontend, make dev
├── server.py                   # FastAPI + React (primary)
├── app.py                      # Legacy Gradio UI
├── frontend/                   # React UI (Vite)
├── terraform/                  # Stripe products, prices, payment links
├── "Example Files"/            # sample images (Aviva electrical SLD, etc.)
├── src/zoomify/
│   ├── agent.py                # vision + tool-calling loop
│   ├── billing.py              # quotas, plan enforcement
│   ├── byok_crypto.py          # client-side key encryption (RSA)
│   ├── clerk_auth.py           # JWT verification
│   ├── db.py                   # MongoDB or in-memory user store
│   ├── gridder.py              # auto-grid + re-grid primitives
│   ├── gridzoom.py             # crop + zoom + re-grid
│   ├── plans.py                # Free / Starter / Pro tiers
│   ├── query_runner.py         # streaming query orchestration
│   ├── stripe_webhook.py       # subscription lifecycle
│   ├── tools.py                # tool schemas, stack state, dispatch
│   └── trail.py                # zoom trail HTML for the UI
└── tests/                      # pytest (grid, agent, API, billing, BYOK, auth)
```

## Setup (uv)

Install [`uv`](https://docs.astral.sh/uv/) (`brew install uv` or
`curl -LsSf https://astral.sh/uv/install.sh | sh`), then:

```bash
make install                    # uv sync --dev + bun install in frontend/
cp .env.example .env            # optional — see CONTRIBUTING.md for what you need
```

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for the full local-dev guide (zero-config
pytest, optional `.env` tiers, and Clerk frontend setup).

Generate a BYOK keypair once (paste the private PEM into `.env` as `BYOK_PRIVATE_KEY`):

```bash
uv run python -c "from zoomify.byok_crypto import generate_keypair_pem; p,u=generate_keypair_pem(); print(p)"
```

## Run

### Local development (recommended)

```bash
make dev
```

Starts the FastAPI backend (`http://127.0.0.1:8000`), the Vite dev server
(`http://127.0.0.1:5173`, proxies `/api`), and — if the [Stripe CLI](https://stripe.com/docs/stripe-cli)
is installed — forwards webhooks to `/api/billing/webhook`.

Open **http://127.0.0.1:5173** for the UI. Enter your OpenRouter key on first use;
it is encrypted with the server public key and stored locally.

### Production-style (single server)

```bash
cd frontend && bun run build && cd ..
uv run uvicorn server:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 — chat on the left, zoom trail on the right.

### Legacy Gradio

```bash
uv run python app.py
```

## API

Interactive docs: **http://127.0.0.1:8000/api/docs** (ReDoc at `/api/redoc`).

**Authentication:** most endpoints need two headers — see the Swagger description at
`/api/docs` (click **Authorize** for both schemes):

| Header | Purpose |
|--------|---------|
| `Authorization: Bearer …` | Zoomify platform key (`zfy_live_…`) or Clerk JWT |
| `X-Encrypted-Api-Key` | RSA-OAEP encrypted OpenRouter key (get PEM from `/api/byok/public-key`) |

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/health` | — | Service status (BYOK, Clerk, MongoDB, Stripe flags) |
| `GET` | `/api/byok/public-key` | — | RSA public key for client-side key encryption |
| `GET` | `/api/auth/me` | Zoomify | Signed-in user (platform key or Clerk JWT) |
| `GET` | `/api/platform-key` | Zoomify | Platform key status (prefix only) |
| `POST` | `/api/platform-key` | Clerk JWT | Create platform key (returned once) |
| `POST` | `/api/platform-key/rotate` | Zoomify | Rotate platform key |
| `GET` | `/api/models` | Both | Vision models |
| `POST` | `/api/query` | Both | Stream extraction (multipart; metered by plan) |
| `DELETE` | `/api/session/{id}` | Zoomify | Clear server-side session state |
| `GET` | `/api/billing/plans` | — | Plan catalog + Stripe Payment Link URLs |
| `GET` | `/api/billing/status` | Zoomify | Current plan and daily usage |
| `POST` | `/api/billing/webhook` | Stripe sig | Stripe subscription events |

**Query stream:** `POST /api/query` accepts multipart fields `query`, optional
`image`, `model`, `schema`, `structured`, `session_id`. Responses are NDJSON
events (`session`, `trail`, `assistant`, `schema`, `error`, `done`).

**Business schemas:** tag images with metadata `structure-zoomify:<id>` (e.g.
`acme-sld-v1`) or pass `schema` in the request. See `src/zoomify/schema_registry.py`.

## Plans & billing

Zoomify is **BYOK** — you pay OpenRouter for model usage; Zoomify bills for
platform extractions on our server layer:

| Plan | Daily extractions | Price |
|------|-------------------|-------|
| **Free** | 50 | $0 |
| **Starter** | 500 | $10/mo |
| **Pro** | Unlimited* | $25/mo |

\*Fair-use rate limits apply on Pro.

Stripe Payment Links and webhooks are provisioned with Terraform — see
[`terraform/README.md`](terraform/README.md). For local webhook testing, copy the
`whsec_…` secret from `stripe listen` into `STRIPE_WEBHOOK_SECRET` in `.env`.

## How it works

1. On upload, the image is **auto-gridded** (labeled columns `A..`, rows `1..`).
2. The model identifies which cells hold the requested information.
3. It calls `zoom` (raise `zoom`/`regrid_cols` for tiny fonts) to read the
   detail, **pushing** steps onto a stack — each step re-grids the crop.
4. It can `undo` to pop back, `redo` to re-push the last pop, or `restore` to
   clear the stack to the full image.

Because the Chat Completions API can't embed images in `tool` messages, each
tool result is returned as a text status plus a follow-up multimodal `user`
message carrying the processed image, so the model can actually see it. Only the
**single most recent image** (the stack top) is kept in context — older images
are replaced with a text placeholder — so the model must navigate
(`undo` / `redo` / `restore` / `zoom`) to revisit earlier levels. As it
navigates, the right-hand trail updates **live**, collapsing when steps are popped.

## Configuration

Set in `.env` (see `.env.example`):

| Variable | Purpose |
|----------|---------|
| `BYOK_PRIVATE_KEY` | RSA private PEM — decrypts encrypted OpenRouter keys from clients |
| `CLERK_JWKS_URL` | Clerk JWT verification; omit for local dev bypass |
| `MONGODB_URI` | Optional MongoDB connection string; in-memory store when unset |
| `MONGODB_DATABASE` | MongoDB database name (default `Zoomify`; use e.g. `Zoomify-Prod` in production) |
| `STRIPE_LINK_*` | Payment Link URLs (Starter/Pro, monthly/yearly) |
| `STRIPE_SECRET_KEY` | Stripe API key for webhook verification |
| `STRIPE_WEBHOOK_SECRET` | Webhook signing secret (`stripe listen` locally) |
| `OPENROUTER_BASE_URL` | Optional override (default `https://openrouter.ai/api/v1`) |

Pick the **vision model** in the app dropdown (models are fetched from OpenRouter and
filtered to image + tool-calling capable). Default selection is
`anthropic/claude-opus-4.8-fast`.

## Tests

Grid tools, agent loop, FastAPI routes, billing, BYOK crypto, and Clerk auth are
covered by pytest:

```bash
uv sync --group dev
uv run python -m pytest
uv run python -m pytest --cov=zoomify --cov=server
```

No OpenRouter API key is required — agent tests use a scripted fake client. Stripe
env vars are cleared in test fixtures so local `.env` secrets do not affect CI.

## License

Zoomify is released under the **[MIT License](LICENSE)**.

You are free to use, modify, and ship this code in your own projects — commercial
or open source — as long as you **keep the copyright notice and license text**
and **give credit to [Zynclo Softwares](https://github.com/Zynclo-Softwares)**.
A link back to this repository or a mention in your docs or README is enough.

See [CONTRIBUTING.md](CONTRIBUTING.md) if you want to send a pull request.
