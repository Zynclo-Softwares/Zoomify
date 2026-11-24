<div align="center">
  <img src="frontend/public/zoomify-logo.png" alt="Zoomify logo" width="88" />
  <h1>Zoomify — a zoom lens for AI agents (MCP server)</h1>
  <p><strong>Vision LLMs are bad at reading whole images when the detail matters.</strong></p>
</div>

Send a blueprint, site map, single-line diagram, long screenshot, or dense scan
to a vision model in one shot and it will miss labels, invent values, or skim
past the tiny parts — breaker ratings, parcel IDs, footnotes, table cells that
only become readable when you zoom in. The model sees the full frame, downscaled;
it does not naturally pan, magnify, and re-read the way a person does with a PDF
viewer.

**Zoomify gives any agent that ability.** It is a remote
[Model Context Protocol](https://modelcontextprotocol.io) server: connect it to
Claude Code, Cursor, VS Code, Codex, Gemini CLI, or your own agent, and the agent
gets tools to overlay a **labeled grid** on an image, **zoom** into the cells that
matter, and back out again — plus built-in **skills** that teach it to do this
well. Your agent stays in charge of the reasoning; Zoomify does the looking.

Good for:

- **Blueprints & single-line diagrams** — electrical, mechanical, architectural
- **Site maps & parcel plans** — boundaries, labels, legend text
- **Scans, forms, and multi-page PDFs** — one page at a time, at high resolution
- **Long screenshots** — chat logs, tables, dashboards, multi-panel UIs
- **Posters and dense infographics** — mixed font sizes on one canvas

> **Zoomify is open source and built with its community.** New skills, better
> tools, client snippets, bug fixes, and docs are all welcome. The process is
> simple: **open an issue first**, wait for a maintainer to approve it, then send
> a pull request. See [Contributing](#contributing) for the full walkthrough.

**Contents:** [Quick start](#quick-start) · [Tools](#tools) · [Skills](#skills) ·
[Contributing](#contributing) · [Plans](#plans) · [Self-hosting](#self-hosting) ·
[REST API](#rest-api) · [Configuration](#configuration) · [License](#license)

## Quick start

1. Sign up on the hosted site and create an API key on the **Connect** page
   (or [self-host](#self-hosting) and skip the key).
2. Add the server to your agent. For Claude Code:

   ```bash
   claude mcp add --transport http zoomify https://<host>/mcp \
     --header "Authorization: Bearer zfy_live_…"
   ```

   Any client that speaks Streamable HTTP works the same way — endpoint
   `https://<host>/mcp`, header `Authorization: Bearer <key>`:

   ```json
   {
     "mcpServers": {
       "zoomify": {
         "url": "https://<host>/mcp",
         "headers": { "Authorization": "Bearer zfy_live_…" }
       }
     }
   }
   ```

   The Connect page has ready-to-paste snippets for Cursor, VS Code, Codex,
   Gemini CLI, Windsurf, and Claude Desktop. Clients that cannot send headers
   can use `https://<host>/mcp?api_key=zfy_live_…` (treat that URL as a secret).

3. Ask your agent something like:

   > Use Zoomify to open https://example.com/site-plan.png, read the zoom-basics
   > skill, then list every label in the legend. Zoom until each one is sharp.

### Getting images to the server

The server runs in the cloud, so it cannot read files on your machine.

| Source | How |
|--------|-----|
| Public URL | `open_image(image_url="https://…")` — the server downloads it |
| Local / private file | Upload first, then `open_image(image_id="img_…")` |

```bash
curl -s https://<host>/api/images \
  -H "Authorization: Bearer $ZOOMIFY_API_KEY" \
  -F "file=@drawing.pdf"
# → {"image_id": "img_…", "kind": "pdf", "pages": 4, ...}
```

Uploads are private to your account, kept in memory, and expire after an hour.
PNG, JPEG, WebP, TIFF, GIF, BMP, and PDF (one page per session) are supported.

## Tools

| Tool | Cost | What it does |
|------|------|--------------|
| `open_image` | 1 request | Opens an image or PDF page; returns a `session_id` and the full image with a labeled grid (columns `A…`, rows `1…`). |
| `zoom` | 1 request | Crops a selection (`C2`, `1-3-B-E`, `1C,3B`), upscales it, re-grids it, and **pushes** a step onto the session's zoom stack. |
| `undo` | free | **Pops** the last zoom step. |
| `redo` | free | Re-pushes the step last popped by `undo`. |
| `restore` | free | Clears the stack back to the full gridded image. |
| `view` | free | Shows the current view again. |
| `usage` | free | Plan, requests left this month, limits. |
| `read_skill` | free | Returns one of the skills below. |

Each zoom step is stored as a **recipe** (selection + factor + regrid); views are
rendered from the original on demand, so there are no stored intermediates.
Sessions close after 30 minutes without use. Engine files:
`src/zoomify/gridder.py` (grid overlay) and `src/zoomify/gridzoom.py` (crop, zoom,
path rendering).

## Skills

Skills are short Markdown playbooks that teach an agent to use the tools well.
The server exposes each one three ways — as an MCP **prompt**, an MCP
**resource** (`zoomify://skills/<name>`), and through the `read_skill` tool — so
they work in every client with nothing to install. They are also downloadable
from the Connect page (`GET /api/skills/<name>.md`) if you prefer a local skill
file.

| Skill | Use it for |
|-------|-----------|
| `zoom-basics` | The core loop: locate, zoom, read, navigate. Read first. |
| `engineering-drawings` | Single-line diagrams, title blocks, schedules, revisions. |
| `long-documents` | Tall screenshots, scans, tables, forms, multi-page PDFs. |
| `extraction-reporting` | Verified values, sources, structured JSON output. |

**Adding a skill** is one file: drop `src/zoomify/skills/<name>.md` with a
`name` / `title` / `description` frontmatter block and it is served everywhere
automatically. Domain skills are the contribution we want most; see
[Contributing](#contributing).

## Contributing

Zoomify gets better when people who read drawings, scans, and documents for a
living teach it what they know. You do not need to be a maintainer, and most
contributions need no accounts, keys, or secrets.

### How a contribution moves

Every change follows the same path, so nobody spends time on work that cannot
be merged:

1. **Open an issue first.** Use
   [New issue](https://github.com/Zynclo-Softwares/Zoomify/issues/new) and
   describe one thing: the bug, the feature, or the skill you have in mind, why
   it matters, and how we would know it is done. Please do not open a pull
   request before this step.
2. **Wait for approval.** A maintainer reads the issue, asks questions if
   something is unclear, and either approves it, suggests a different approach,
   or explains why it is not a fit. Approval is a comment or an `approved` label
   on the issue. If someone else is already on it, we will say so.
3. **Open a pull request.** Once the issue is approved, fork the repository,
   branch from `main` as `patch/<short-description>`, make the change, and open
   a PR that says `Fixes #<issue number>`. Keep it scoped to that one issue.
4. **Review.** A maintainer reviews the PR. If anything needs to change, we
   will tell you in the review, with the reason. Push follow-up commits to the
   same branch; there is no need to open a new PR.
5. **Merge.** When the review is approved and the test check is green, a
   maintainer merges it into `main`, and the issue closes automatically.

Small fixes such as typos or broken links still start with an issue, but those
are usually approved the same day. Not sure whether an idea fits? Open an issue
and ask before writing code.

### Good places to start

| Contribution | Where | Notes |
|--------------|-------|-------|
| A new **skill** for a kind of document you know well (P&IDs, floor plans, lab reports, invoices, maps) | `src/zoomify/skills/<name>.md` | One Markdown file, no code. Served as a prompt, a resource, and through `read_skill` automatically. |
| Improve an existing skill | `src/zoomify/skills/` | Tell us in the issue what the agent got wrong before your change. |
| A new or better **tool** | `src/zoomify/mcp_server.py`, `src/zoomify/tools.py` | Add tests in `tests/test_mcp_server.py`. |
| A connection snippet for another MCP client | `frontend/src/connectSnippets.ts` | Append one entry to `CLIENTS`. |
| Grid and zoom engine | `src/zoomify/gridder.py`, `src/zoomify/gridzoom.py` | Before and after images in the PR help a lot. |
| Docs, examples, bug reports | anywhere | A clear bug report with a sample image is a real contribution. |

### Set up and test

```bash
git clone https://github.com/<you>/Zoomify.git && cd Zoomify
make install
uv run python -m pytest   # no keys or network needed
make dev                  # UI on http://127.0.0.1:5173, MCP on http://127.0.0.1:8000/mcp
```

With an empty `.env` there is no sign-in and no database, so you can point your
own agent at `http://127.0.0.1:8000/mcp` and try a change immediately. Before
pushing, run `make format` and the tests. The suite covers the grid engine, the
MCP tools and HTTP transport, metering, image intake, uploads, billing, and
auth.

[CONTRIBUTING.md](CONTRIBUTING.md) has the full guide: environment files, what
each kind of change needs, rebasing, and what reviewers look for.

### Project layout

```
Zoomify/
├── server.py                   # FastAPI app: /mcp endpoint, account API, web UI
├── src/zoomify/
│   ├── mcp_server.py           # MCP tools, prompts, resources, auth, metering hooks
│   ├── skills.py               # skill loader
│   ├── skills/*.md             # the skills themselves
│   ├── tools.py                # zoom stack state + tool dispatch
│   ├── gridder.py              # grid overlay primitives
│   ├── gridzoom.py             # crop + zoom + re-grid
│   ├── images.py               # decode, PDF render, URL fetch (SSRF-guarded), uploads
│   ├── session.py              # in-memory zoom sessions (TTL, per-account cap)
│   ├── plans.py                # Free / Starter / Pro limits
│   ├── billing.py              # quota + rate-limit enforcement
│   ├── db.py                   # MongoDB or in-memory users + monthly usage
│   ├── platform_keys.py        # zfy_live_… API keys
│   ├── clerk_auth.py           # browser sign-in (JWT) for the web UI
│   └── stripe_webhook.py       # subscription lifecycle
├── frontend/                   # React (Vite): landing, pricing, Connect page
├── terraform/                  # Stripe products/prices/links, Railway, DNS
└── tests/                      # pytest
```

## Plans

A **request** is one `open_image` or `zoom` call. Everything else — navigation,
uploads, skills, the REST API — is free. Reading one drawing typically takes 5
to 15 requests.

| Plan | Requests / month | Rate limit | Max file | Open images | Price |
|------|------------------|-----------|----------|-------------|-------|
| **Free** | 1,000 | 20 / min | 20 MB | 3 | $0 |
| **Starter** | 25,000 | 60 / min | 50 MB | 10 | $10 / mo |
| **Pro** | 150,000 | 120 / min | 100 MB | 25 | $25 / mo |

Yearly billing is 15% off. Allowances reset on the 1st of each month (UTC).
When a limit is reached the tool returns a clear message to the agent; there are
no overage charges. Limits are defined in one place, `src/zoomify/plans.py`.

Stripe products, prices, Payment Links, and the webhook are provisioned with
Terraform — see [`terraform/README.md`](terraform/README.md).

## Self-hosting

Zoomify is MIT-licensed and runs fine on your own machine or server.

```bash
git clone https://github.com/Zynclo-Softwares/Zoomify.git && cd Zoomify
make install
make dev            # UI on http://127.0.0.1:5173, MCP on http://127.0.0.1:8000/mcp
```

or with Docker:

```bash
make docker-build
docker run --rm -p 8000:8000 -e ZOOMIFY_DISABLE_QUOTAS=true zoomify
```

With an empty `.env` there is no sign-in: `/mcp` accepts requests without a key
as a single `dev-local` account. Set `ZOOMIFY_DISABLE_QUOTAS=true` to turn plan
limits off. To run it as a multi-user service, configure Clerk (sign-in),
MongoDB (accounts, keys, usage), and Stripe (subscriptions) — see
[Configuration](#configuration).

Zoom sessions and uploads live in process memory, so run **one server instance**
per deployment (or put sticky routing in front of several).

## REST API

The MCP endpoint is `/mcp`. The REST API around it (interactive docs at
`/api/docs`) handles accounts and uploads:

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/health` | — | Service status |
| `GET` | `/api/mcp/info` | — | Endpoint URL, auth scheme, tools, skills |
| `GET` | `/api/skills`, `/api/skills/{name}.md` | — | Skills as JSON / Markdown |
| `POST` | `/api/images` | key | Upload an image or PDF → `image_id` |
| `GET` | `/api/auth/me` | key | Who am I |
| `GET` | `/api/platform-key` | key | Key status (prefix only) |
| `POST` | `/api/platform-key` | Clerk JWT | Create the API key (returned once) |
| `POST` | `/api/platform-key/rotate` | key | Rotate the API key |
| `GET` | `/api/billing/plans` | — | Plan catalog + Stripe Payment Links |
| `GET` | `/api/billing/status` | key | Plan and this month's usage |
| `POST` | `/api/billing/webhook` | Stripe sig | Subscription events |

“key” means `Authorization: Bearer zfy_live_…` (or a Clerk session JWT from the
web UI).

## Configuration

Set in `.env` (see `.env.example`) — everything is optional for local use:

| Variable | Purpose |
|----------|---------|
| `CLERK_JWKS_URL` | Enables sign-in; `/mcp` then requires an API key |
| `MONGODB_URI`, `MONGODB_DATABASE` | Persistent accounts, keys, and usage (in-memory when unset) |
| `PUBLIC_BASE_URL` | Origin shown in connection snippets (defaults to the request origin) |
| `ZOOMIFY_DISABLE_QUOTAS` | `true` turns plan limits off (self-hosting) |
| `RATE_LIMIT_{FREE,STARTER,PRO}_PER_MINUTE` | Override per-plan rate limits |
| `ZOOMIFY_MAX_IMAGE_PIXELS` | Largest decoded image (default 120 MP) |
| `STRIPE_LINK_*` | Payment Link URLs (Starter/Pro, monthly/yearly) |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Stripe webhook verification |
| `GITHUB_TOKEN` | Contact form → GitHub issues |

## License

Zoomify is released under the **[MIT License](LICENSE)**.

You are free to use, modify, and ship this code in your own projects — commercial
or open source — as long as you **keep the copyright notice and license text**
and **give credit to [Zynclo Softwares](https://github.com/Zynclo-Softwares)**.
A link back to this repository or a mention in your docs or README is enough.

Want to help? Start with [Contributing](#contributing): open an issue, get it
approved, then send a pull request.
