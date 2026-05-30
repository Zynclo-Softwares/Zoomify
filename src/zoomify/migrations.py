"""Deploy-time MongoDB index migration (idempotent)."""

from __future__ import annotations

import sys


def run() -> None:
    from zoomify.db import ensure_indexes, mongodb_enabled

    if not mongodb_enabled():
        print("MONGODB_URI not set — skipping index migration")
        return
    ensure_indexes()
    print("MongoDB indexes ensured")


def main() -> None:
    try:
        run()
    except Exception as exc:
        print(f"Index migration failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
