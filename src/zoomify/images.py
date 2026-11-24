"""Image intake for the MCP server: decode, PDF rasterisation, URL fetch, uploads.

Agents hand Zoomify an image in one of two ways:

- ``image_url`` — a public http(s) URL the server downloads (SSRF-guarded).
- ``image_id``  — returned by ``POST /api/images`` after uploading a local file.

Both accept raster images (anything Pillow reads) and PDFs (one page at a time,
rendered with pdfium).
"""

from __future__ import annotations

import io
import ipaddress
import os
import secrets
import socket
import threading
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx
from PIL import Image, UnidentifiedImageError

UPLOAD_ID_PREFIX = "img_"
UPLOAD_TTL_SECONDS = 60 * 60
MAX_UPLOADS_PER_USER = 10
MAX_REDIRECTS = 3
FETCH_TIMEOUT_SECONDS = 20.0
PDF_RENDER_DPI = 200
PDF_MAX_SIDE_PX = 9000


class ImageError(ValueError):
    """User-facing problem with an image source (bad URL, too large, not an image…)."""


def max_image_pixels() -> int:
    """Largest decoded image accepted, in pixels (decompression-bomb guard)."""
    raw = os.environ.get("ZOOMIFY_MAX_IMAGE_PIXELS", "").strip()
    try:
        return max(1_000_000, int(raw)) if raw else 120_000_000
    except ValueError:
        return 120_000_000


@dataclass
class LoadedImage:
    image: Image.Image
    source_kind: str  # "image" | "pdf"
    page: int = 1
    page_count: int = 1


# --------------------------------------------------------------- decoding


def is_pdf(data: bytes) -> bool:
    return data[:1024].lstrip().startswith(b"%PDF-")


def _decode_raster(data: bytes) -> Image.Image:
    try:
        img = Image.open(io.BytesIO(data))
    except UnidentifiedImageError as exc:
        raise ImageError(
            "Unsupported file — expected an image (PNG, JPEG, WebP, TIFF, GIF, BMP) or a PDF."
        ) from exc
    w, h = img.size
    if w * h > max_image_pixels():
        raise ImageError(
            f"Image is too large to decode ({w}x{h} px). "
            f"The limit is {max_image_pixels() // 1_000_000} megapixels."
        )
    try:
        img.load()
    except Exception as exc:
        raise ImageError(f"Could not decode image: {exc}") from exc
    return img.convert("RGB")


def _render_pdf_page(data: bytes, page: int) -> tuple[Image.Image, int]:
    import pypdfium2 as pdfium

    try:
        pdf = pdfium.PdfDocument(data)
    except Exception as exc:
        raise ImageError(f"Could not open PDF: {exc}") from exc
    try:
        count = len(pdf)
        if count == 0:
            raise ImageError("PDF has no pages.")
        if not (1 <= page <= count):
            raise ImageError(f"Page {page} is out of range — this PDF has {count} page(s).")
        pdf_page = pdf[page - 1]
        width_pt, height_pt = pdf_page.get_size()
        scale = PDF_RENDER_DPI / 72
        longest = max(width_pt, height_pt) * scale
        if longest > PDF_MAX_SIDE_PX:
            scale *= PDF_MAX_SIDE_PX / longest
        budget = max_image_pixels()
        pixels = width_pt * height_pt * scale * scale
        if pixels > budget:
            scale *= (budget / pixels) ** 0.5
        img = pdf_page.render(scale=scale).to_pil().convert("RGB")
        return img, count
    finally:
        pdf.close()


def load_image(data: bytes, page: int = 1) -> LoadedImage:
    """Decode image bytes or render one PDF page into an RGB image."""
    if not data:
        raise ImageError("The file is empty.")
    if is_pdf(data):
        img, count = _render_pdf_page(data, max(1, int(page or 1)))
        return LoadedImage(
            image=img, source_kind="pdf", page=max(1, int(page or 1)), page_count=count
        )
    return LoadedImage(image=_decode_raster(data), source_kind="image")


def describe_upload(data: bytes) -> dict:
    """Validate upload bytes cheaply and return ``{kind, pages}`` metadata."""
    if is_pdf(data):
        import pypdfium2 as pdfium

        try:
            pdf = pdfium.PdfDocument(data)
        except Exception as exc:
            raise ImageError(f"Could not open PDF: {exc}") from exc
        try:
            count = len(pdf)
        finally:
            pdf.close()
        if count == 0:
            raise ImageError("PDF has no pages.")
        return {"kind": "pdf", "pages": count}
    try:
        with Image.open(io.BytesIO(data)) as img:
            w, h = img.size
    except UnidentifiedImageError as exc:
        raise ImageError(
            "Unsupported file — expected an image (PNG, JPEG, WebP, TIFF, GIF, BMP) or a PDF."
        ) from exc
    if w * h > max_image_pixels():
        raise ImageError(
            f"Image is too large ({w}x{h} px). "
            f"The limit is {max_image_pixels() // 1_000_000} megapixels."
        )
    return {"kind": "image", "pages": 1, "width": w, "height": h}


# --------------------------------------------------------------- URL fetch


def _assert_public_host(host: str, port: int) -> None:
    """Reject hosts that resolve to private, loopback, or otherwise internal addresses."""
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ImageError(f"Could not resolve host {host!r}.") from exc
    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if not addr.is_global or addr.is_multicast:
            raise ImageError(
                "That URL points to a private or internal address, which is not allowed."
            )


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ImageError("image_url must be an http(s) URL.")
    if not parsed.hostname:
        raise ImageError("image_url has no host.")
    if parsed.username or parsed.password:
        raise ImageError("URLs with embedded credentials are not allowed.")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    _assert_public_host(parsed.hostname, port)


def fetch_url(url: str, max_bytes: int) -> bytes:
    """Download ``url`` (public hosts only), following a few validated redirects."""
    current = url.strip()
    headers = {"User-Agent": "Zoomify-MCP/1.0", "Accept": "image/*,application/pdf,*/*;q=0.5"}
    with httpx.Client(follow_redirects=False, timeout=FETCH_TIMEOUT_SECONDS) as client:
        for _ in range(MAX_REDIRECTS + 1):
            _validate_url(current)
            try:
                with client.stream("GET", current, headers=headers) as resp:
                    if resp.status_code in (301, 302, 303, 307, 308):
                        location = resp.headers.get("location")
                        if not location:
                            raise ImageError("Redirect without a Location header.")
                        current = urljoin(current, location)
                        continue
                    if resp.status_code != 200:
                        raise ImageError(
                            f"Could not download the image (HTTP {resp.status_code}). "
                            "If the file is private, upload it with POST /api/images instead."
                        )
                    declared = resp.headers.get("content-length")
                    if declared and declared.isdigit() and int(declared) > max_bytes:
                        raise ImageError(_too_large_message(max_bytes))
                    chunks: list[bytes] = []
                    total = 0
                    for chunk in resp.iter_bytes():
                        total += len(chunk)
                        if total > max_bytes:
                            raise ImageError(_too_large_message(max_bytes))
                        chunks.append(chunk)
                    return b"".join(chunks)
            except httpx.HTTPError as exc:
                raise ImageError(f"Could not download the image: {exc}") from exc
    raise ImageError("Too many redirects.")


def _too_large_message(max_bytes: int) -> str:
    return f"File is larger than this plan's {max_bytes // (1024 * 1024)} MB limit."


# --------------------------------------------------------------- upload store


@dataclass
class Upload:
    id: str
    owner: str
    data: bytes
    filename: str
    kind: str
    pages: int
    created_at: float

    @property
    def expires_at(self) -> float:
        return self.created_at + UPLOAD_TTL_SECONDS


class UploadStore:
    """Short-lived, per-process store for files uploaded via ``POST /api/images``."""

    def __init__(self) -> None:
        self._items: dict[str, Upload] = {}
        self._lock = threading.Lock()

    def _purge(self, now: float) -> None:
        for key in [k for k, u in self._items.items() if u.expires_at <= now]:
            del self._items[key]

    def put(self, owner: str, data: bytes, filename: str, kind: str, pages: int) -> Upload:
        now = time.time()
        upload = Upload(
            id=UPLOAD_ID_PREFIX + secrets.token_urlsafe(12),
            owner=owner,
            data=data,
            filename=filename,
            kind=kind,
            pages=pages,
            created_at=now,
        )
        with self._lock:
            self._purge(now)
            mine = sorted(
                (u for u in self._items.values() if u.owner == owner), key=lambda u: u.created_at
            )
            for old in mine[: max(0, len(mine) - MAX_UPLOADS_PER_USER + 1)]:
                del self._items[old.id]
            self._items[upload.id] = upload
        return upload

    def get(self, owner: str, upload_id: str) -> Upload | None:
        with self._lock:
            self._purge(time.time())
            upload = self._items.get(upload_id)
        if upload is None or upload.owner != owner:
            return None
        return upload

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


uploads = UploadStore()
