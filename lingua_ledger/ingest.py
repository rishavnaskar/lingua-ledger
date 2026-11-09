from __future__ import annotations

import base64
import io
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageOps

from .config import MAX_PAGES, RENDER_DPI

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}


def load_pages(
    source: str | Path | bytes, filename: str | None = None, dpi: int = RENDER_DPI, max_pages: int = MAX_PAGES
) -> list[Image.Image]:
    if isinstance(source, (str, Path)):
        path = Path(source)
        data = path.read_bytes()
        filename = filename or path.name
    else:
        data = source
        filename = filename or "upload"
    ext = Path(filename).suffix.lower()
    if ext == ".pdf" or data[:5] == b"%PDF-":
        return _render_pdf(data, dpi, max_pages)
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    return [img.convert("RGB")]


def _render_pdf(data: bytes, dpi: int, max_pages: int) -> list[Image.Image]:
    doc = pdfium.PdfDocument(data)
    pages = []
    for i in range(min(len(doc), max_pages)):
        page = doc[i]
        bitmap = page.render(scale=dpi / 72)
        pages.append(bitmap.to_pil().convert("RGB"))
    return pages


def to_jpeg_base64(img: Image.Image, max_side: int = 1800, quality: int = 85) -> str:
    im = img.copy()
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode()


def to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
