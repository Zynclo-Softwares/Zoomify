"""HTTP coverage for the account API around the MCP server."""

from __future__ import annotations


from zoomify.account.db import get_user, upsert_user


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["mcp_path"] == "/mcp"
    assert data["metering_enabled"] is True
    assert data["mongodb_enabled"] is False
    assert data["stripe_webhook_configured"] is False


def test_mcp_info_lists_tools_and_skills(client, monkeypatch):
    r = client.get("/api/mcp/info")
    assert r.status_code == 200
    data = r.json()
    assert data["url"].endswith("/mcp")
    assert data["auth"]["required"] is False
    names = [t["name"] for t in data["tools"]]
    assert names[:2] == ["open_image", "zoom"]
    assert [t["name"] for t in data["tools"] if t["metered"]] == ["open_image", "zoom"]
    assert data["skills"][0]["name"] == "zoom-basics"

    monkeypatch.setenv("PUBLIC_BASE_URL", "https://zoomify.example.com/")
    data = client.get("/api/mcp/info").json()
    assert data["url"] == "https://zoomify.example.com/mcp"
    assert data["upload_url"] == "https://zoomify.example.com/api/images"


def test_auth_me_dev_bypass(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["bypass"] is True


def test_openapi_and_redoc(client):
    assert client.get("/api/docs").status_code == 200
    assert client.get("/api/redoc").status_code == 200
    schema = client.get("/api/openapi.json").json()
    assert "ZoomifyAuth" in schema["components"]["securitySchemes"]
    assert "Metering" in schema["info"]["description"]


# --------------------------------------------------------------- skills


def test_skills_endpoints(client):
    data = client.get("/api/skills").json()
    names = [s["name"] for s in data["skills"]]
    assert names[0] == "zoom-basics"
    assert "engineering-drawings" in names
    assert all(s["body"] and s["description"] for s in data["skills"])

    r = client.get("/api/skills/zoom-basics.md")
    assert r.status_code == 200
    assert r.text.startswith("---\nname: zoom-basics\n")
    assert client.get("/api/skills/nope.md").status_code == 404


# --------------------------------------------------------------- uploads


def test_upload_image_returns_id(client, small_png_bytes):
    r = client.post("/api/images", files={"file": ("plan.png", small_png_bytes, "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert body["image_id"].startswith("img_")
    assert body["kind"] == "image"
    assert body["pages"] == 1
    assert body["bytes"] == len(small_png_bytes)

    from zoomify.core.images import uploads

    assert uploads.get("dev-local", body["image_id"]).data == small_png_bytes
    assert uploads.get("someone-else", body["image_id"]) is None


def test_upload_pdf_reports_pages(client, pdf_bytes):
    r = client.post("/api/images", files={"file": ("set.pdf", pdf_bytes, "application/pdf")})
    assert r.status_code == 200
    assert r.json()["kind"] == "pdf"
    assert r.json()["pages"] == 2


def test_upload_rejects_non_image(client):
    r = client.post("/api/images", files={"file": ("a.txt", b"hello", "text/plain")})
    assert r.status_code == 422
    assert "Unsupported file" in r.json()["detail"]


def test_upload_rejects_empty(client):
    r = client.post("/api/images", files={"file": ("a.png", b"", "image/png")})
    assert r.status_code == 422


def test_upload_enforces_plan_size(client, small_png_bytes, monkeypatch):
    from zoomify.api import app as server
    from zoomify.account.plans import PLANS, Plan

    tiny = Plan(**{**PLANS["free"].__dict__, "max_image_mb": 0})
    monkeypatch.setattr(server, "plan_for_id", lambda _id: tiny)
    r = client.post("/api/images", files={"file": ("plan.png", small_png_bytes, "image/png")})
    assert r.status_code == 413


def test_upload_requires_auth_when_clerk_enabled(client, small_png_bytes, monkeypatch):
    from zoomify.account import clerk_auth
    from zoomify.account.platform_keys import create_platform_key

    monkeypatch.setenv("CLERK_JWKS_URL", "https://example.com/jwks.json")
    clerk_auth.reset_jwks_cache()
    files = {"file": ("plan.png", small_png_bytes, "image/png")}
    assert client.post("/api/images", files=files).status_code == 401

    key = create_platform_key("user_up")["key"]
    r = client.post("/api/images", files=files, headers={"Authorization": f"Bearer {key}"})
    assert r.status_code == 200


# --------------------------------------------------------------- billing


def test_billing_status_reflects_plan(client):
    upsert_user("dev-local", plan="pro", subscriptionStatus="active")
    data = client.get("/api/billing/status").json()
    assert data["plan"] == "pro"
    assert data["max_open_images"] == 25


def test_billing_webhook_subscription_deleted(client):
    upsert = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": "user_del",
                "subscription": "sub_del",
                "customer": "cus_del",
                "metadata": {"plan": "starter"},
            }
        },
    }
    client.post("/api/billing/webhook", json=upsert)

    payload = {
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_del",
                "metadata": {"clerk_user_id": "user_del"},
                "status": "canceled",
            }
        },
    }
    r = client.post("/api/billing/webhook", json=payload)
    assert r.status_code == 200
    user = get_user("user_del")
    assert user["plan"] == "free"
    assert user["subscriptionStatus"] == "canceled"


def test_billing_webhook_invalid_payload(client):
    r = client.post(
        "/api/billing/webhook",
        data="not-json",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 400
