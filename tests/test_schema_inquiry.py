def test_schema_inquiry_endpoint(client, monkeypatch):
    monkeypatch.setattr(
        "server.create_schema_inquiry_issue",
        lambda **kwargs: {
            "issue_number": 7,
            "issue_url": "https://github.com/Zynclo-Softwares/Zoomify/issues/7",
            "title": "Schema inquiry — Test User",
        },
    )
    r = client.post(
        "/api/schema-inquiry",
        json={
            "name": "Test User",
            "email": "test@example.com",
            "message": "Need a schema for utility bills.",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["issue_number"] == 7
    assert data["issue_url"].endswith("/issues/7")


def test_schema_inquiry_validation(client):
    r = client.post(
        "/api/schema-inquiry",
        json={"name": "", "email": "bad", "message": ""},
    )
    assert r.status_code == 422


def test_schema_inquiry_unconfigured(client, monkeypatch):
    monkeypatch.setattr(
        "server.create_schema_inquiry_issue",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("Schema inquiry is not configured")),
    )
    r = client.post(
        "/api/schema-inquiry",
        json={
            "name": "Test User",
            "email": "test@example.com",
            "message": "Need help",
        },
    )
    assert r.status_code == 503
