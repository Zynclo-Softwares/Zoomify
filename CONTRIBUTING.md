# Contributing to Zoomify

Thanks for helping improve Zoomify. We accept **pull requests** and **issues**.

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

**Open http://127.0.0.1:5173** (Vite proxies `/api` to the backend on port 8000).
Paste **your own** [OpenRouter](https://openrouter.ai/keys) key in the app — it is
encrypted client-side and stored in the browser, not in server `.env`.

### Environment files (your machine only)

| File | Purpose |
|------|---------|
| `.env` | Backend config — copy from [`.env.example`](.env.example) |
| `frontend/.env.local` | Clerk publishable key for sign-in — copy from [`frontend/env.local.example`](frontend/env.local.example) |

Both are **gitignored**. Never commit real keys.

### What you need for different work

| Goal | Required setup |
|------|----------------|
| Python tests, grid/agent/API fixes | Nothing — `pytest` clears env in fixtures |
| UI + extraction locally | `make dev` + your OpenRouter key in the app |
| Stable BYOK keys across server restarts | Generate RSA keys (see `.env.example` comment) → `BYOK_PRIVATE_KEY` in `.env` |
| Clerk sign-in locally | Your Clerk app → `frontend/.env.local` + `CLERK_JWKS_URL` in `.env` |
| Billing / Stripe webhooks | Stripe **test** keys + `stripe listen` (see [README](README.md)) |
| MongoDB persistence | Your own Atlas URI → `MONGODB_URI` |
| Schema inquiry form | Your GitHub PAT (Issues write) → `GITHUB_TOKEN` |

With an **empty** `.env`, the server uses dev defaults: auth bypass (`dev-local`),
ephemeral BYOK keys, and an in-memory session store.

More detail: [README → Setup & Configuration](README.md#setup-uv).

## Issues

- Open an issue before you start if you are planning a code change.
- Keep each issue focused on **one task** (one bug, one feature, or one clear improvement).
- Describe what you want, why it matters, and how you would verify it is done.

## Pull requests

1. **Create the issue first** if you are implementing something new or fixing a bug.
2. Branch from `main` with name `patch/<short-description>`.
3. Open a PR that **references your issue** (for example: `Fixes #12`).
4. Keep PRs small and scoped to that single issue.
5. **Format** before pushing:

   ```bash
   make format
   ```

6. **Rebase onto `origin/main`** before requesting merge:

   ```bash
   git fetch origin
   git rebase origin/main
   git push --force-with-lease
   ```

7. Make sure **tests pass** locally:

   ```bash
   uv sync --dev
   uv run python -m pytest
   ```

PRs need a passing CI test check and at least **one approving review** before they can merge into `main`.

## Questions

If you are unsure whether something belongs in one issue or needs design discussion, open an issue and ask before coding.
