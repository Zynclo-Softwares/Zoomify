"""Tests for image intake — decoding, PDFs, upload store, and the URL fetch guard."""

from __future__ import annotations

import pytest

from zoomify import images
from zoomify.images import ImageError, UploadStore, describe_upload, fetch_url, load_image


def test_load_raster(small_png_bytes):
    loaded = load_image(small_png_bytes)
    assert loaded.source_kind == "image"
    assert loaded.image.size == (400, 300)
    assert loaded.image.mode == "RGB"


def test_load_pdf_pages(pdf_bytes):
    first = load_image(pdf_bytes)
    assert (first.source_kind, first.page, first.page_count) == ("pdf", 1, 2)
    assert min(first.image.size) > 300  # rendered above screen resolution
    assert load_image(pdf_bytes, page=2).page == 2
    with pytest.raises(ImageError, match="out of range"):
        load_image(pdf_bytes, page=9)


def test_load_rejects_garbage_and_empty():
    with pytest.raises(ImageError, match="Unsupported file"):
        load_image(b"definitely not an image")
    with pytest.raises(ImageError, match="empty"):
        load_image(b"")


def test_pixel_limit_guards_decompression_bombs(small_png_bytes, monkeypatch):
    monkeypatch.setattr(images, "max_image_pixels", lambda: 1000)
    with pytest.raises(ImageError, match="too large"):
        load_image(small_png_bytes)
    with pytest.raises(ImageError, match="too large"):
        describe_upload(small_png_bytes)


def test_describe_upload(small_png_bytes, pdf_bytes):
    assert describe_upload(small_png_bytes) == {
        "kind": "image",
        "pages": 1,
        "width": 400,
        "height": 300,
    }
    assert describe_upload(pdf_bytes) == {"kind": "pdf", "pages": 2}


def test_upload_store_ownership_expiry_and_cap(monkeypatch):
    s = UploadStore()
    first = s.put("u1", b"a", "a.png", "image", 1)
    assert s.get("u1", first.id) is first
    assert s.get("u2", first.id) is None

    for i in range(images.MAX_UPLOADS_PER_USER):
        s.put("u1", b"x", f"{i}.png", "image", 1)
    assert s.get("u1", first.id) is None  # oldest evicted at the per-user cap

    latest = s.put("u1", b"z", "z.png", "image", 1)
    monkeypatch.setattr(
        images.time, "time", lambda: latest.created_at + images.UPLOAD_TTL_SECONDS + 1
    )
    assert s.get("u1", latest.id) is None


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/a.png",
        "http://localhost:8000/a.png",
        "http://10.0.0.5/a.png",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/a.png",
    ],
)
def test_fetch_url_blocks_internal_hosts(url):
    with pytest.raises(ImageError, match="private or internal"):
        fetch_url(url, 1024)


@pytest.mark.parametrize("url", ["ftp://example.com/a.png", "file:///etc/passwd", "notaurl"])
def test_fetch_url_rejects_non_http(url):
    with pytest.raises(ImageError):
        fetch_url(url, 1024)


def test_fetch_url_rejects_embedded_credentials():
    with pytest.raises(ImageError, match="credentials"):
        fetch_url("https://user:pw@example.com/a.png", 1024)


class _FakeStream:
    def __init__(self, status, headers=None, body=b""):
        self.status_code, self.headers, self._body = status, headers or {}, body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def iter_bytes(self):
        yield self._body


def _fake_client(responses, seen):
    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def stream(self, method, url, headers=None):
            seen.append(url)
            return responses.pop(0)

    return Client


def test_fetch_url_follows_validated_redirects(monkeypatch):
    seen: list[str] = []
    responses = [
        _FakeStream(302, {"location": "/moved.png"}),
        _FakeStream(200, {"content-length": "3"}, b"abc"),
    ]
    monkeypatch.setattr(images, "_assert_public_host", lambda host, port: None)
    monkeypatch.setattr(images.httpx, "Client", _fake_client(responses, seen))
    assert fetch_url("https://cdn.example.com/a.png", 1024) == b"abc"
    assert seen == ["https://cdn.example.com/a.png", "https://cdn.example.com/moved.png"]


def test_fetch_url_redirect_to_internal_host_is_blocked(monkeypatch):
    seen: list[str] = []
    responses = [_FakeStream(302, {"location": "http://127.0.0.1/secret"})]
    real_check = images._assert_public_host
    monkeypatch.setattr(
        images,
        "_assert_public_host",
        lambda host, port: None if host == "cdn.example.com" else real_check(host, port),
    )
    monkeypatch.setattr(images.httpx, "Client", _fake_client(responses, seen))
    with pytest.raises(ImageError, match="private or internal"):
        fetch_url("https://cdn.example.com/a.png", 1024)
    assert seen == ["https://cdn.example.com/a.png"]


def test_fetch_url_enforces_size_and_status(monkeypatch):
    monkeypatch.setattr(images, "_assert_public_host", lambda host, port: None)

    monkeypatch.setattr(
        images.httpx, "Client", _fake_client([_FakeStream(200, {"content-length": "999"})], [])
    )
    with pytest.raises(ImageError, match="larger than"):
        fetch_url("https://cdn.example.com/a.png", 10)

    monkeypatch.setattr(images.httpx, "Client", _fake_client([_FakeStream(200, {}, b"x" * 50)], []))
    with pytest.raises(ImageError, match="larger than"):
        fetch_url("https://cdn.example.com/a.png", 10)

    monkeypatch.setattr(images.httpx, "Client", _fake_client([_FakeStream(404)], []))
    with pytest.raises(ImageError, match="HTTP 404"):
        fetch_url("https://cdn.example.com/a.png", 10)


def test_parse_page_selection():
    from zoomify.images import parse_page_selection

    assert parse_page_selection(None, 5, 30) == ([1, 2, 3, 4, 5], False)
    assert parse_page_selection("4, 1-2", 5, 30) == ([1, 2, 4], False)
    assert parse_page_selection("2-99", 5, 2) == ([2, 3], True)
    for bad in ("x", "0", "3-1", "9"):
        with pytest.raises(ImageError):
            parse_page_selection(bad, 5, 30)


def test_pdf_outline(text_pdf_bytes, small_png_bytes):
    from zoomify.images import pdf_outline

    outline = pdf_outline(text_pdf_bytes, pages="1-2", previews=True)
    assert outline.page_count == 3
    assert [p.page for p in outline.pages] == [1, 2]
    assert outline.pages[0].text.startswith("Sheet 1 of 3")
    assert outline.preview is not None
    with pytest.raises(ImageError, match="not a PDF"):
        pdf_outline(small_png_bytes)


def test_upload_store_finds_by_source(pdf_bytes):
    uploads = UploadStore()
    uploads.put("u1", pdf_bytes, "a.pdf", "pdf", 2, source="https://x.test/a.pdf")
    assert uploads.find_by_source("u1", "https://x.test/a.pdf") is not None
    assert uploads.find_by_source("u2", "https://x.test/a.pdf") is None
    assert uploads.find_by_source("u1", "") is None
