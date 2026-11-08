from __future__ import annotations

import re

import pytesseract
from PIL import Image
from rapidfuzz import fuzz

from .config import tesseract_lang
from .normalize import normalize_text
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


_digits = re.compile(r"[^\d]")


def locate_value(value, pages: list[OcrPage]) -> tuple[float, list[int], int] | None:
    """Find the OCR span best matching a value. Returns (mean conf 0-1, bbox, page) or None."""
    if value is None:
        return None
    target = str(value).strip()
    if not target:
        return None
    numeric = isinstance(value, (int, float)) or bool(re.fullmatch(r"[\d\s.,\-]+", target))
    norm_target = _digits.sub("", target) if numeric else normalize_text(target)
    if not norm_target:
        return None
    n_tokens = max(1, min(12, len(target.split())))
    best = None
    for page in pages:
        words = sorted(page.words, key=lambda w: (w.line, w.x0))
        for i in range(len(words)):
            for span in range(1, n_tokens + 2):
                chunk = words[i:i + span]
                if len(chunk) < span:
                    break
                joined = " ".join(w.text for w in chunk)
                cand = _digits.sub("", joined) if numeric else normalize_text(joined)
                if not cand:
                    continue
                if numeric:
                    score = 100.0 if cand == norm_target else fuzz.ratio(cand, norm_target)
                    if abs(len(cand) - len(norm_target)) > 2:
                        score *= 0.5
                else:
                    score = fuzz.ratio(cand, norm_target)
                if best is None or score > best[0]:
                    best = (score, chunk, page.page)
                if score >= 99.5:
                    break
            if best and best[0] >= 99.5:
                break
    if best is None or best[0] < 70:
        return None
    _, chunk, pg = best
    conf = sum(w.conf for w in chunk) / len(chunk) / 100.0
    bbox = [min(w.x0 for w in chunk), min(w.y0 for w in chunk), max(w.x1 for w in chunk), max(w.y1 for w in chunk)]
    return conf, bbox, pg
