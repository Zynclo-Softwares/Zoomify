"""OpenAPI / Swagger UI metadata for the Zoomify FastAPI app."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

OPENAPI_TAGS = [
    {"name": "system", "description": "Health checks and MCP connection details."},
    {
        "name": "auth",
        "description": (
            "Zoomify account identity. Use a **platform API key** (`zfy_live_…`) "
            "for agents and scripts, or a Clerk session JWT from the browser."
        ),
    },
    {
        "name": "images",
        "description": "Upload local images or PDFs for the `open_image` MCP tool.",
    },
    {"name": "skills", "description": "Agent skills bundled with the MCP server."},
    {
        "name": "billing",
        "description": "Plan catalog, monthly request usage, and Stripe webhooks.",
    },
    {"name": "support", "description": "Contact form for custom skills and enterprise needs."},
]

OPENAPI_DESCRIPTION = """\
Zoomify is a remote **MCP server** that gives any AI agent grid + zoom tools for
reading large, dense, or fine-printed images and PDFs. Agents talk to the MCP
endpoint at **`/mcp`** (Streamable HTTP); this REST API covers everything around
it — API keys, uploads, skills, plans, and usage.

## Authentication

Send your platform key on every request, to `/mcp` and to this API alike:

```
Authorization: Bearer zfy_live_…
```

1. Sign in on the web UI and create an API key (shown once — rotate if lost).
2. In Swagger **Authorize → ZoomifyAuth**, paste the key only (Swagger adds `Bearer`).

Verify with `GET /api/auth/me` → expect `"auth": "platform_key"`.

## Metering

Only the `open_image` and `zoom` MCP tools count as requests. Uploads,
navigation tools, skills, and this REST API are free. Allowances reset on the
1st of each month (UTC) — see `GET /api/billing/status`.
"""


def customize_openapi(app: FastAPI) -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=OPENAPI_DESCRIPTION,
        routes=app.routes,
        tags=OPENAPI_TAGS,
    )

    schemes = schema.setdefault("components", {}).setdefault("securitySchemes", {})
    zoomify = schemes.get("ZoomifyAuth")
    if zoomify:
        zoomify.setdefault(
            "description",
            "Zoomify account auth: platform API key (`zfy_live_…`) or Clerk JWT.",
        )
        zoomify.setdefault("bearerFormat", "zfy_live_… or Clerk JWT")

    app.openapi_schema = schema
    return schema
