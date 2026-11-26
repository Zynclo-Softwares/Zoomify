"""Shared fixtures for the Zoomify test suite."""

from __future__ import annotations


import pytest
from PIL import Image, ImageDraw


@pytest.fixture(autouse=True)
def _isolate_server_env(monkeypatch):
    """Tests should not inherit developer .env secrets or auth settings."""
    monkeypatch.delenv("CLERK_JWKS_URL", raising=False)
    monkeypatch.delenv("ZOOMIFY_DISABLE_QUOTAS", raising=False)
    monkeypatch.delenv("ZOOMIFY_MAX_IMAGE_PIXELS", raising=False)
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.delenv("MONGODB_DATABASE", raising=False)
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("RATE_LIMIT_FREE_PER_MINUTE", raising=False)
    monkeypatch.delenv("RATE_LIMIT_STARTER_PER_MINUTE", raising=False)
    monkeypatch.delenv("RATE_LIMIT_PRO_PER_MINUTE", raising=False)
    from zoomify import billing, clerk_auth, db, images, platform_keys, session

    clerk_auth.reset_jwks_cache()
    db.reset_memory_store()
    platform_keys.reset_platform_key_store()
    billing.reset_rate_limits()
    session.store.clear()
    images.uploads.clear()


@pytest.fixture
def small_img() -> Image.Image:
    """A small synthetic 'map' image so tests stay fast."""
    img = Image.new("RGB", (400, 300), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, 180, 140], outline="black", width=2)
    d.rectangle([220, 160, 380, 280], fill=(200, 220, 255))
    d.text((30, 30), "PANEL A", fill="black")
    d.text((230, 170), "INVERTER", fill="black")
    return img


@pytest.fixture
def state(small_img):
    from zoomify.tools import ImageState

    return ImageState.from_image(small_img, cols=8)


@pytest.fixture
def client():
    """HTTP client without the app lifespan (REST routes only)."""
    from fastapi.testclient import TestClient

    from server import app

    return TestClient(app)


@pytest.fixture
def live_client():
    """HTTP client with the app lifespan running, so ``/mcp`` is served."""
    from fastapi.testclient import TestClient

    from server import app

    with TestClient(app) as c:
        yield c


def _png_bytes(img: Image.Image) -> bytes:
    import io

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def small_png_bytes(small_img) -> bytes:
    return _png_bytes(small_img)


@pytest.fixture
def pdf_bytes(small_img) -> bytes:
    """A two-page PDF built from the synthetic image."""
    import io

    buf = io.BytesIO()
    small_img.save(buf, format="PDF", save_all=True, append_images=[small_img])
    return buf.getvalue()


@pytest.fixture
def text_pdf_bytes() -> bytes:
    """A three-page PDF with a real text layer: "Sheet N of 3 <topic>"."""
    topics = ["Cover and drawing index", "Single line diagram", "Panel schedule"]
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [%s] /Count 3 >>"
        % b" ".join(b"%d 0 R" % (4 + 2 * i) for i in range(3)),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for i, topic in enumerate(topics):
        stream = f"BT /F1 24 Tf 72 700 Td (Sheet {i + 1} of 3 {topic}) Tj ET".encode()
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>" % (5 + 2 * i)
        )
        objects.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream))
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % off for off in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)
