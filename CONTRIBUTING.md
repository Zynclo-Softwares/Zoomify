# Contributing to Zoomify

Thanks for helping improve Zoomify. We accept **pull requests** and **issues**.

## Issues

- Open an issue before you start if you are planning a code change.
- Keep each issue focused on **one task** (one bug, one feature, or one clear improvement).
- Describe what you want, why it matters, and how you would verify it is done.

## Pull requests

1. **Create the issue first** if you are implementing something new or fixing a bug.
2. Open a PR that **references your issue** (for example: `Fixes #12`).
3. Keep PRs small and scoped to that single issue.
4. **Rebase onto `origin/main`** before requesting merge:

   ```bash
   git fetch origin
   git rebase origin/main
   git push --force-with-lease
   ```

5. Make sure **tests pass** locally:

   ```bash
   uv sync --dev
   uv run python -m pytest
   ```

PRs need a passing CI test check and at least **one approving review** before they can merge into `main`.

## Questions

If you are unsure whether something belongs in one issue or needs design discussion, open an issue and ask before coding.
