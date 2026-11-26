"""Image intake for the MCP server: decode, PDF rasterisation, URL fetch, uploads.

Agents hand Zoomify an image in one of two ways:

- ``image_url`` — a public http(s) URL the server downloads (SSRF-guarded).
- ``image_id``  — returned by ``POST /api/images`` after uploading a local file.

Both accept raster images (anything Pillow reads) and PDFs. A PDF is stored once
and addressed by page number: :func:`pdf_outline` lists pages (count, text,
thumbnails) and :func:`load_image` renders only the page that is asked for.
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
UPLOAD_TICKET_PREFIX = "upl_"
UPLOAD_TICKET_TTL_SECONDS = 15 * 60
MAX_TICKETS_PER_USER = 10
MAX_REDIRECTS = 3
FETCH_TIMEOUT_SECONDS = 20.0
PDF_RENDER_DPI = 200
PDF_MAX_SIDE_PX = 9000
PDF_OUTLINE_MAX_PAGES = 30  # pages listed by one `pdf_pages` call
PDF_PREVIEW_MAX_PAGES = 12  # thumbnails on one contact sheet
PDF_SNIPPET_CHARS = 240  # text shown per page when listing several pages
PDF_PAGE_TEXT_CHARS = 6000  # text shown when exactly one page is asked for
PDF_THUMB_SIDE_PX = 380

# PDFium is not thread-safe, and tools run on worker threads.
_PDF_LOCK = threading.Lock()


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


def _open_pdf(data: bytes):
    """Open a PDF with pdfium; the caller holds ``_PDF_LOCK`` and closes it."""
    import pypdfium2 as pdfium

    try:
        pdf = pdfium.PdfDocument(data)
    except Exception as exc:
        raise ImageError(f"Could not open PDF: {exc}") from exc
    if len(pdf) == 0:
        pdf.close()
        raise ImageError("PDF has no pages.")
    return pdf


def _render_pdf_page(data: bytes, page: int) -> tuple[Image.Image, int]:
    with _PDF_LOCK:
        pdf = _open_pdf(data)
        try:
            count = len(pdf)
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


def parse_page_selection(spec: str | None, count: int, limit: int) -> tuple[list[int], bool]:
    """Turn ``"3"``, ``"2-6"`` or ``"1,4,9-12"`` into page numbers.

    Returns ``(pages, truncated)``: at most ``limit`` pages in ascending order,
    and whether more were asked for. An empty spec means "from page 1".
    """
    text = (spec or "").strip()
    wanted: set[int] = set()
    if not text:
        wanted.update(range(1, count + 1))
    for part in filter(None, (p.strip() for p in text.split(","))):
        lo, sep, hi = part.partition("-")
        try:
            first = int(lo)
            last = int(hi) if sep else first
        except ValueError as exc:
            raise ImageError(
                f"Could not read pages {spec!r}. Use a page ('3'), a range ('2-6'), "
                "or a list ('1,4,9-12')."
            ) from exc
        if first < 1 or last < first:
            raise ImageError(f"Invalid page range {part!r}. Pages start at 1.")
        if first > count:
            raise ImageError(f"Page {first} is out of range — this PDF has {count} page(s).")
        wanted.update(range(first, min(last, count) + 1))
    pages = sorted(wanted)
    return pages[:limit], len(pages) > limit


@dataclass
class PdfPageInfo:
    page: int
    width_in: float
    height_in: float
    text: str  # extracted text layer, possibly cut to the requested length
    text_chars: int  # full length of the page's text layer (0 for a scan)


@dataclass
class PdfOutline:
    page_count: int
    pages: list[PdfPageInfo]
    truncated: bool  # more pages matched than were returned
    preview: Image.Image | None = None


def _page_text(pdf_page) -> str:
    try:
        textpage = pdf_page.get_textpage()
    except Exception:
        return ""
    try:
        raw = textpage.get_text_bounded()
    except Exception:
        return ""
    finally:
        textpage.close()
    lines = (" ".join(line.split()) for line in raw.replace("\x00", "").splitlines())
    return "\n".join(line for line in lines if line)


def _contact_sheet(thumbs: list[tuple[int, Image.Image]]) -> Image.Image:
    """Lay page thumbnails out on one sheet, each captioned with its page number."""
    from PIL import ImageDraw

    from .gridder import load_font

    cols = min(4, len(thumbs))
    rows = -(-len(thumbs) // cols)
    pad, caption = 14, 34
    cell_w = max(t.width for _, t in thumbs) + pad
    cell_h = max(t.height for _, t in thumbs) + caption + pad
    sheet = Image.new("RGB", (cols * cell_w + pad, rows * cell_h + pad), (236, 238, 242))
    draw = ImageDraw.Draw(sheet)
    font = load_font(22)
    for i, (number, thumb) in enumerate(thumbs):
        x = pad + (i % cols) * cell_w
        y = pad + (i // cols) * cell_h
        draw.text((x, y), f"Page {number}", fill=(20, 24, 32), font=font)
        sheet.paste(thumb, (x, y + caption))
        draw.rectangle(
            (x - 1, y + caption - 1, x + thumb.width, y + caption + thumb.height),
            outline=(120, 126, 138),
        )
    return sheet


def pdf_outline(data: bytes, pages: str | None = None, previews: bool = False) -> PdfOutline:
    """Describe PDF pages without opening a zoom session.

    Reports the page count plus, for the selected pages, their size and text
    layer (a snippet per page, or most of the text when one page is selected).
    With ``previews`` it also renders small thumbnails onto one contact sheet,
    which is how an agent picks a page in a scanned PDF that has no text.
    """
    if not is_pdf(data):
        raise ImageError("That file is an image, not a PDF, so it has no pages to list.")
    limit = PDF_PREVIEW_MAX_PAGES if previews else PDF_OUTLINE_MAX_PAGES
    with _PDF_LOCK:
        pdf = _open_pdf(data)
        try:
            count = len(pdf)
            selected, truncated = parse_page_selection(pages, count, limit)
            max_chars = PDF_PAGE_TEXT_CHARS if len(selected) == 1 else PDF_SNIPPET_CHARS
            infos: list[PdfPageInfo] = []
            thumbs: list[tuple[int, Image.Image]] = []
            for number in selected:
                pdf_page = pdf[number - 1]
                width_pt, height_pt = pdf_page.get_size()
                text = _page_text(pdf_page)
                infos.append(
                    PdfPageInfo(
                        page=number,
                        width_in=round(width_pt / 72, 1),
                        height_in=round(height_pt / 72, 1),
                        text=text[:max_chars],
                        text_chars=len(text),
                    )
                )
                if previews:
                    scale = PDF_THUMB_SIDE_PX / max(width_pt, height_pt, 1)
                    thumbs.append((number, pdf_page.render(scale=scale).to_pil().convert("RGB")))
                pdf_page.close()
        finally:
            pdf.close()
    return PdfOutline(
        page_count=count,
        pages=infos,
        truncated=truncated,
        preview=_contact_sheet(thumbs) if thumbs else None,
    )


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
        with _PDF_LOCK:
            pdf = _open_pdf(data)
            try:
                count = len(pdf)
            finally:
                pdf.close()
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
    source: str = ""  # URL the server downloaded it from, if any

    @property
    def expires_at(self) -> float:
        return self.created_at + UPLOAD_TTL_SECONDS


@dataclass(frozen=True)
class UploadTicket:
    """One-time permission to upload a single file without an API key.

    Issued to an agent by the ``request_upload`` MCP tool. The ``token`` is the
    only credential: it is unguessable, short-lived, bound to one account, and
    can only ever create the upload ``image_id``.
    """

    token: str
    owner: str
    image_id: str
    max_bytes: int
    created_at: float
    filename: str = ""

    @property
    def expires_at(self) -> float:
        return self.created_at + UPLOAD_TICKET_TTL_SECONDS


class UploadStore:
    """Short-lived, per-process store for uploaded files and upload tickets."""

    def __init__(self) -> None:
        self._items: dict[str, Upload] = {}
        self._tickets: dict[str, UploadTicket] = {}
        self._lock = threading.Lock()

    def _purge(self, now: float) -> None:
        for key in [k for k, u in self._items.items() if u.expires_at <= now]:
            del self._items[key]
        for key in [k for k, t in self._tickets.items() if t.expires_at <= now]:
            del self._tickets[key]

    def issue_ticket(self, owner: str, max_bytes: int, filename: str = "") -> UploadTicket:
        now = time.time()
        ticket = UploadTicket(
            token=UPLOAD_TICKET_PREFIX + secrets.token_urlsafe(24),
            owner=owner,
            image_id=UPLOAD_ID_PREFIX + secrets.token_urlsafe(12),
            max_bytes=max_bytes,
            created_at=now,
            filename=filename,
        )
        with self._lock:
            self._purge(now)
            mine = sorted(
                (t for t in self._tickets.values() if t.owner == owner),
                key=lambda t: t.created_at,
            )
            for old in mine[: max(0, len(mine) - MAX_TICKETS_PER_USER + 1)]:
                del self._tickets[old.token]
            self._tickets[ticket.token] = ticket
        return ticket

    def peek_ticket(self, token: str) -> UploadTicket | None:
        with self._lock:
            self._purge(time.time())
            return self._tickets.get(token)

    def redeem_ticket(self, token: str) -> UploadTicket | None:
        """Consume a ticket; returns ``None`` if it is unknown, expired, or already used."""
        with self._lock:
            self._purge(time.time())
            return self._tickets.pop(token, None)

    def put(
        self,
        owner: str,
        data: bytes,
        filename: str,
        kind: str,
        pages: int,
        upload_id: str | None = None,
        source: str = "",
    ) -> Upload:
        now = time.time()
        upload = Upload(
            id=upload_id or UPLOAD_ID_PREFIX + secrets.token_urlsafe(12),
            owner=owner,
            data=data,
            filename=filename,
            kind=kind,
            pages=pages,
            created_at=now,
            source=source,
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

    def find_by_source(self, owner: str, source: str) -> Upload | None:
        """The newest live upload this account's server-side download of ``source`` made."""
        if not source:
            return None
        with self._lock:
            self._purge(time.time())
            mine = [u for u in self._items.values() if u.owner == owner and u.source == source]
        return max(mine, key=lambda u: u.created_at, default=None)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self._tickets.clear()


uploads = UploadStore()
