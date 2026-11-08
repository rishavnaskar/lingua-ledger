from __future__ import annotations

import re

import pytesseract
from PIL import Image
from rapidfuzz import fuzz

from .config import tesseract_lang
from .normalize import normalize_text, parse_date
from .schemas import OcrPage, Word


def ocr_page(img: Image.Image, language: str | None, page: int = 0) -> OcrPage:
    lang = tesseract_lang(language)
    data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT, config="--psm 6")
    words: list[Word] = []
    line_ids: dict[tuple[int, int, int], int] = {}
    for i, text in enumerate(data["text"]):
        text = (text or "").strip()
        conf = float(data["conf"][i])
        if not text or conf < 0:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        line = line_ids.setdefault(key, len(line_ids))
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        words.append(Word(text=text, conf=conf, x0=x, y0=y, x1=x + w, y1=y + h, page=page, line=line))
    return OcrPage(page=page, width=img.width, height=img.height, words=words)


def ocr_pages(images: list[Image.Image], language: str | None) -> list[OcrPage]:
    return [ocr_page(img, language, i) for i, img in enumerate(images)]


def pages_text(pages: list[OcrPage]) -> str:
    return "\n\n".join(f"[page {p.page + 1}]\n{p.text()}" for p in pages)


_non_digit = re.compile(r"[^\d]")
_non_alnum = re.compile(r"[^0-9a-z]")
_numeric_like = re.compile(r"[\d\s.,\-]+")
_iso_date = re.compile(r"\d{4}-\d{2}-\d{2}")
_cjk = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")


def _kind(value) -> str:
    if isinstance(value, (int, float)):
        return "number"
    s = str(value).strip()
    if _iso_date.fullmatch(s):
        return "date"
    if _numeric_like.fullmatch(s):
        return "number"
    if " " not in s and re.search(r"\d", s):
        return "identifier"
    return "text"


def _score(kind: str, target: str, chunk_text: str) -> float:
    if kind == "number":
        cand = _non_digit.sub("", chunk_text)
        if not cand:
            return 0.0
        if cand == target:
            return 100.0
        return fuzz.ratio(cand, target) * (0.5 if abs(len(cand) - len(target)) > 2 else 1.0)
    if kind == "date":
        parsed = parse_date(chunk_text) or parse_date(chunk_text.replace(" ", ""))
        return 100.0 if parsed == target else 0.0
    if kind == "identifier":
        cand = _non_alnum.sub("", normalize_text(chunk_text))
        if not cand:
            return 0.0
        return 100.0 if cand == target else fuzz.ratio(cand, target)
    cand = normalize_text(chunk_text)
    if _cjk.search(target):
        cand, target = cand.replace(" ", ""), target.replace(" ", "")
    return fuzz.ratio(cand, target) if cand else 0.0


def locate_value(value, pages: list[OcrPage]) -> tuple[float, list[int], int] | None:
    """Find the OCR span best matching a value. Returns (mean conf 0-1, bbox, page) or None."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    kind = _kind(value)
    if kind == "number":
        target = _non_digit.sub("", raw)
    elif kind == "date":
        target = raw
    elif kind == "identifier":
        target = _non_alnum.sub("", normalize_text(raw))
    else:
        target = normalize_text(raw)
    if not target:
        return None
    max_span = {"number": 4, "date": 6, "identifier": 8}.get(kind, min(12, len(raw.split()) + 1))
    if kind == "text" and _cjk.search(target):
        max_span = 12
    best: tuple[float, list[Word], int] | None = None
    for page in pages:
        words = sorted(page.words, key=lambda w: (w.line, w.x0))
        for i in range(len(words)):
            for span in range(1, max_span + 1):
                chunk = words[i:i + span]
                if len(chunk) < span:
                    break
                if span > 1 and chunk[-1].line != chunk[0].line:
                    break
                score = _score(kind, target, " ".join(w.text for w in chunk))
                if best is None or score > best[0]:
                    best = (score, chunk, page.page)
                if score >= 99.5:
                    break
            if best and best[0] >= 99.5:
                break
        if best and best[0] >= 99.5:
            break
    floor = 85 if kind in ("identifier", "text") else 70
    if best is None or best[0] < floor:
        return None
    _, chunk, pg = best
    conf = sum(w.conf for w in chunk) / len(chunk) / 100.0
    bbox = [min(w.x0 for w in chunk), min(w.y0 for w in chunk), max(w.x1 for w in chunk), max(w.y1 for w in chunk)]
    return conf, bbox, pg
