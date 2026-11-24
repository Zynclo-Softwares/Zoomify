# Contributing to Zoomify

Thanks for helping improve Zoomify. The short version: **open an issue, wait for a
maintainer to approve it, then open a pull request.** We review it, tell you if
anything needs to change, and merge it when it is ready.

## Local development

Most contributions do **not** need production secrets. Clone, install, run tests, and
optionally start the UI:

```bash
git clone https://github.com/Zynclo-Softwares/Zoomify.git
cd Zoomify
make install
uv run python -m pytest          # no .env required
make dev                         # optional — full UI at http://127.0.0.1:5173
```

**Open http://127.0.0.1:5173** (Vite proxies `/api` and `/mcp` to the backend on
port 8000). The Connect page shows the snippet for pointing your own agent at the
local MCP endpoint, `http://127.0.0.1:8000/mcp` — no key is needed locally.

### Environment files (your machine only)

| File | Purpose |
|------|---------|
| `.env` | Backend config — copy from [`.env.example`](.env.example) |
| `frontend/.env.local` | Clerk publishable key for sign-in — copy from [`frontend/env.local.example`](frontend/env.local.example) |

Both are **gitignored**. Never commit real keys.

### What you need for different work

| Goal | Required setup |
|------|----------------|
| Python tests, grid/MCP/API fixes | Nothing — `pytest` clears env in fixtures |
| Try the tools from a real agent | `make dev`, then add `http://127.0.0.1:8000/mcp` to your agent |
| Add or improve a skill | Edit or add `src/zoomify/skills/<name>.md` — no code change needed |
| Clerk sign-in locally | Your Clerk app → `frontend/.env.local` + `CLERK_JWKS_URL` in `.env` |
| Billing / Stripe webhooks | Stripe **test** keys + `stripe listen` (see [README](README.md)) |
| MongoDB persistence | Your own Atlas URI → `MONGODB_URI` |
| Contact form | Your GitHub PAT (Issues write) → `GITHUB_TOKEN` |

With an **empty** `.env`, the server uses dev defaults: auth bypass (`dev-local`
account, Free-plan limits) and in-memory storage. Set `ZOOMIFY_DISABLE_QUOTAS=true`
if the limits get in your way.

More detail: [README → Self-hosting](README.md#self-hosting) and [Configuration](README.md#configuration).

## How a contribution moves

Every change, large or small, follows the same five steps.

### 1. Open an issue first

- Open an issue **before** writing code or opening a pull request.
- Keep each issue focused on **one task** (one bug, one feature, one skill, or one clear improvement).
- Describe what you want, why it matters, and how you would verify it is done.
- For bugs, include the image or PDF (or a similar public one), the tool calls, and what you expected.

### 2. Wait for approval

A maintainer reads the issue and replies. We may ask questions, suggest a
different approach, or explain why the idea is not a fit right now. An issue is
approved when a maintainer says so in a comment or adds the `approved` label.
Pull requests without an approved issue may be closed and pointed back to this
step, so please wait; it saves your time as much as ours.

### 3. Open a pull request

1. Fork the repository and branch from `main` with the name `patch/<short-description>`.
2. Keep the change small and scoped to the approved issue.
3. **Format** before pushing:

   ```bash
   make format
   ```

4. Make sure **tests pass** locally, and add tests for new behaviour:

   ```bash
   uv sync --dev
   uv run python -m pytest
   ```

5. **Rebase onto `origin/main`** (use `upstream` if that is what you named this repository in your fork):

   ```bash
   git fetch origin
   git rebase origin/main
   git push --force-with-lease
   ```

6. Open the PR and **reference your issue** in the description (for example: `Fixes #12`).

### 4. Review

A maintainer reviews every PR. If anything needs to change, we will say what
and why in the review. Push follow-up commits to the same branch and reply to
the comments when they are addressed; do not open a new PR. Reviewers look for:

- The change matches the approved issue and nothing more.
- Tests cover the new behaviour and the suite is green.
- Tool descriptions and skills are written for an agent to read: short, concrete, and accurate.
- No secrets, keys, or private images are committed.

### 5. Merge

PRs need a passing CI test check and at least **one approving review**. A
maintainer then merges into `main`, which closes the linked issue. Contributors
do not merge their own PRs.

## Questions

If you are unsure whether something belongs in one issue or needs design discussion, open an issue and ask before coding.
