"""OpenAPI / Swagger UI metadata for the Zoomify FastAPI app."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

OPENAPI_TAGS = [
    {
        "name": "system",
        "description": "Health checks and OpenRouter connectivity.",
    },
    {
        "name": "byok",
        "description": (
            "Bring-your-own OpenRouter key. Fetch the RSA public key, encrypt "
            "your `sk-or-v1-…` key client-side, and send it in "
            "`X-Encrypted-Api-Key`."
        ),
    },
    {
        "name": "auth",
        "description": (
            "Zoomify account identity. Use a **platform API key** (`zfy_live_…`) "
            "for scripts, or a Clerk session JWT from the browser."
        ),
    },
    {
        "name": "billing",
        "description": "Plan catalog, daily extraction usage, and Stripe webhooks.",
    },
    {
        "name": "query",
        "description": (
            "Vision extraction. `POST /api/query` streams NDJSON events and "
            "requires **both** Zoomify auth and an encrypted OpenRouter key."
        ),
    },
]

OPENAPI_DESCRIPTION = """\
Vision extraction with a smart zoom grid, live trail, and optional structured JSON.

## Authentication

Most API calls need **two credentials** in separate headers:

| Header | Purpose | Example |
|--------|---------|---------|
| `Authorization` | Zoomify account & billing | `Bearer zfy_live_abc…` |
| `X-Encrypted-Api-Key` | OpenRouter model access | Base64 RSA-OAEP ciphertext |

Click **Authorize** (top right) and fill **both** schemes before trying
`POST /api/query` or `GET /api/models`.

### Zoomify platform key (`Authorization`)

1. Sign in at the product UI and create an API key (or rotate an existing one).
2. Copy the full `zfy_live_…` secret — it is shown **once**.
3. In Swagger **Authorize → ZoomifyAuth**, paste the key only (Swagger adds the `Bearer` prefix).

Verify with `GET /api/auth/me` → expect `"auth": "platform_key"`.

Browser clients may send a **Clerk session JWT** instead of a platform key.

### OpenRouter key (`X-Encrypted-Api-Key`)

**Never** send your OpenRouter key in plain text.

1. `GET /api/byok/public-key` — download the RSA public key PEM.
2. Encrypt your `sk-or-v1-…` key with **RSA-OAEP (SHA-256)**, then **base64**-encode.
3. Paste the ciphertext into **Authorize → EncryptedOpenRouterKey**.

**Python helper (from this repo):**

```python
import json, urllib.request
from zoomify.byok_crypto import encrypt_api_key

pem = json.load(urllib.request.urlopen("https://zoomify.zynclo.com/api/byok/public-key"))[
    "public_key_pem"
]
print(encrypt_api_key("sk-or-v1-YOUR_KEY", public_pem=pem))
```

## Query stream (`POST /api/query`)

- **Content-Type:** `multipart/form-data` with fields `query`, optional `image`, `model`, etc.
- **Response:** `application/x-ndjson` — one JSON object per line.
- **Events:** `session`, `user`, `trail`, `assistant`, `schema`, `error`, `cancelled`, `done`.
- Each successful request counts as **one extraction** against your daily plan limit.
"""

NDJSON_STREAM_RESPONSE: dict[str, Any] = {
    "description": "Newline-delimited JSON — one event object per line",
    "content": {
        "application/x-ndjson": {
            "schema": {"type": "string"},
            "examples": {
                "extraction": {
                    "summary": "Typical stream",
                    "value": (
                        '{"type":"session","session_id":"abc123"}\n'
                        '{"type":"assistant","content":"Part number: XY-42"}\n'
                        '{"type":"done"}\n'
                    ),
                }
            },
        }
    },
}


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

    encrypted = schemes.get("EncryptedOpenRouterKey")
    if encrypted:
        encrypted.setdefault(
            "description",
            "Base64 RSA-OAEP ciphertext of your OpenRouter `sk-or-v1-…` key. "
            "Encrypt with the public key from `GET /api/byok/public-key`.",
        )

    # FastAPI lists multiple security dependencies as OR; these routes need AND.
    for method, path in (("post", "/api/query"), ("get", "/api/models")):
        operation = schema.get("paths", {}).get(path, {}).get(method)
        if operation:
            operation["security"] = [
                {"ZoomifyAuth": [], "EncryptedOpenRouterKey": []},
            ]

    app.openapi_schema = schema
    return schema
