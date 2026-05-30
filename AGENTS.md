# Agent instructions — Zoomify

Read this before making **any code change** or **git push** in this repo.
Human-facing details live in [CONTRIBUTING.md](CONTRIBUTING.md).

## Workflow (always follow)

Every change goes through **one issue → one patch branch → one PR**.

1. **Open an issue first** (single task only: one bug, one feature, or one doc fix).
   - Title: short and specific.
   - Body: what, why, and how to verify done.

2. **Branch from `main`** using `patch/<short-description>`  
   Example: `patch/readme-problem-statement-and-mit-license`

3. **Implement only what the issue describes.** Keep the diff small.

4. **Rebase on latest `main` before opening or updating the PR:**

   ```bash
   git fetch origin
   git rebase origin/main
   git push --force-with-lease
   ```

5. **Run tests locally before pushing:**

   ```bash
   uv sync --dev
   uv run python -m pytest
   ```

6. **Open a PR** that references the issue (`Fixes #N` in the body).

7. **Wait for CI** — the `test` status check must pass on the PR.

8. **Do not merge** until checks are green, branch protection is satisfied, **and the user has explicitly approved merging the PR.**

## PR checklist

- [ ] Issue exists and is single-task scoped
- [ ] Branch name starts with `patch/`
- [ ] Rebased on `origin/main`
- [ ] Tests pass locally
- [ ] PR body includes `Fixes #<issue-number>`
- [ ] CI `test` check is green
- [ ] User has explicitly approved merge (agents must not merge on their own)

## Do not

- Commit directly to `main`
- Bundle unrelated changes in one issue/PR
- Skip the issue when implementing fixes or features
- Push without running pytest
- Merge a PR without **explicit user approval**, even when CI is green

## Repo notes for agents

- Package lives under `src/zoomify/`; legacy Gradio entrypoint is `app.py`
- **Primary UI:** React (`frontend/`) + FastAPI (`server.py`) — `uv run uvicorn server:app`
- Session state is a **zoom stack** (`ImageState.path`); views render from `original + path`
- Grid drawing: `src/zoomify/gridder.py`; zoom/crop/path: `src/zoomify/gridzoom.py`
- Business schemas: `src/zoomify/schema_registry.py` (placeholder; metadata key `structure-zoomify`)
- `.vscode/` and `Example Files/` are gitignored — do not commit them
- License: MIT — keep copyright and credit to **Zynclo Softwares**

## Commands reference

```bash
# issue + PR (after commit on patch branch)
gh issue create --repo Zynclo-Softwares/Zoomify --title "..." --body "..."
gh pr create --repo Zynclo-Softwares/Zoomify --base main --head patch/... --title "..." --body "Fixes #N\n\n..."
```

When the user asks to "patch" or "push" a change, use this workflow unless they explicitly say otherwise.
