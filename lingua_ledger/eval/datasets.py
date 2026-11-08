"""Public document-understanding benchmarks, downloaded to data/raw and normalized into our schemas.

Each dataset becomes data/processed/<name>/samples.jsonl with one Sample per line. Gold labels are
instances of the schemas in lingua_ledger.schemas, serialized with model_dump().
"""

from __future__ import annotations

import json
import re
import shutil
import zipfile
from collections.abc import Callable
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import orjson
from PIL import Image
from pydantic import BaseModel
from tqdm import tqdm

from lingua_ledger.config import DATA_PROCESSED, DATA_RAW
from lingua_ledger.schemas import SCHEMAS, Contract, DocType, Form, KeyValue, LineItem, Receipt

DATASETS = ["xfund", "funsd", "cord", "sroie", "cuad"]

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)

XFUND_LANGS = ["de", "es", "fr", "it", "ja", "pt", "zh"]
XFUND_URL = "https://github.com/doc-analysis/XFUND/releases/download/v1.0/{file}"
FUNSD_URL = "https://guillaumejaume.github.io/FUNSD/dataset.zip"
FUNSD_HF = "nielsr/funsd"
CORD_HF = "naver-clova-ix/cord-v2"
SROIE_HF = ["rth/sroie-2019-v2"]
CUAD_SPLITS_URL = "https://github.com/TheAtticusProject/cuad/raw/main/data.zip"
CUAD_RELEASE_URL = "https://zenodo.org/records/4595826/files/CUAD_v1.zip"
CUAD_SIZE = 40


class DatasetUnavailable(RuntimeError):
    """No reachable source could provide the dataset."""


class Sample(BaseModel):
    doc_id: str
    dataset: str
    doc_type: str
    language: str
    split: str
    image_paths: list[str]
    pdf_path: str | None = None
    text: str | None = None
    gold: dict

    def gold_model(self) -> BaseModel:
        return SCHEMAS[DocType(self.doc_type)].model_validate(self.gold)


def processed_path(name: str) -> Path:
    return DATA_PROCESSED / name / "samples.jsonl"


def build(name: str, limit: int | None = None) -> list[Sample]:
    """Download `name` if missing, normalize it and write its JSONL. `limit` caps samples (per language for xfund)."""
    if name not in BUILDERS:
        raise ValueError(f"unknown dataset {name!r}; choose from {DATASETS}")
    samples = BUILDERS[name](limit)
    for sample in samples:
        sample.gold_model()
    path = processed_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".jsonl.tmp")
    tmp.write_bytes(b"".join(orjson.dumps(s.model_dump()) + b"\n" for s in samples))
    tmp.replace(path)
    return samples


def load(name: str) -> list[Sample]:
    path = processed_path(name)
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; run build({name!r}) or `uv run ll data {name}` first")
    return [Sample.model_validate_json(line) for line in path.read_bytes().splitlines() if line.strip()]


# Downloads and archives


def download(url: str, dest: Path) -> Path:
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    timeout = httpx.Timeout(60.0, read=300.0)
    try:
        with httpx.stream(
            "GET", url, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=timeout
        ) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length") or 0) or None
            with (
                part.open("wb") as fh,
                tqdm(total=total, unit="B", unit_scale=True, desc=dest.name, leave=False) as bar,
            ):
                for chunk in resp.iter_bytes(1 << 20):
                    fh.write(chunk)
                    bar.update(len(chunk))
    except httpx.HTTPError as exc:
        part.unlink(missing_ok=True)
        raise DatasetUnavailable(f"download failed for {url}: {exc}") from exc
    part.replace(dest)
    return dest


def _is_junk(member: str) -> bool:
    parts = Path(member).parts
    return "__MACOSX" in parts or parts[-1] in {".DS_Store", "Thumbs.db"}


def _extract_member(zf: zipfile.ZipFile, info: zipfile.ZipInfo, root: Path, rel: str) -> Path:
    target = (root / rel).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"refusing to extract {info.filename!r} outside {root}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with zf.open(info) as src, target.open("wb") as out:
        shutil.copyfileobj(src, out)
    return target


def extract(archive: Path, dest: Path) -> Path:
    marker = dest / ".extracted"
    if marker.exists():
        return dest
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            if not info.is_dir() and not _is_junk(info.filename):
                _extract_member(zf, info, dest, info.filename)
    marker.touch()
    return dest


def _hf_split(repo: str, split: str, raw: Path):
    from datasets import Image as HfImage
    from datasets import load_dataset

    try:
        ds = load_dataset(
            repo, data_files={split: f"data/{split}-*"}, split=split, cache_dir=str(raw / "hf_cache")
        )
    except Exception as exc:
        raise DatasetUnavailable(f"could not load {repo} [{split}] from Hugging Face: {exc}") from exc
    return ds.cast_column("image", HfImage(decode=False))


def _read_manifest(path: Path, root: Path) -> list[dict] | None:
    if not path.exists():
        return None
    rows = [orjson.loads(line) for line in path.read_bytes().splitlines() if line.strip()]
    if rows and all((root / row["image"]).exists() for row in rows):
        return rows
    return None


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(b"".join(orjson.dumps(row) + b"\n" for row in rows))
    tmp.replace(path)


# Value parsing

_NUMBER = re.compile(r"\d(?:[\d.,]|\s(?=\d{3}(?!\d)))*")
_MONTHS = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1
    )
}
_MONTH = (
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
    r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"
)
_DATE_PATTERNS = [
    ("ymd", re.compile(r"(?<!\d)(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)")),
    ("dmy_num", re.compile(r"(?<!\d)(\d{1,2})[-/.](\d{1,2})[-/.](\d{4}|\d{2})(?!\d)")),
    (
        "d_mon_y",
        re.compile(rf"(?<!\d)(\d{{1,2}})[\s\-/.,]*{_MONTH}[\s\-/.,]*(\d{{4}}|\d{{2}})(?!\d)", re.IGNORECASE),
    ),
    ("mon_d_y", re.compile(rf"\b{_MONTH}[\s\-/.]*(\d{{1,2}})[\s,\-/.]+(\d{{4}})(?!\d)", re.IGNORECASE)),
]


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        parts = [p for p in (_text(v) for v in value) if p]
        return " ".join(parts) or None
    text = str(value).strip()
    return text or None


def _first(value: Any) -> Any:
    while isinstance(value, list):
        value = value[0] if value else None
    return value


def _number(token: str) -> float:
    seps = [i for i, c in enumerate(token) if c in ".,"]
    if not seps:
        return float(token)
    last = seps[-1]
    tail = token[last + 1 :]
    single_kind = len({token[i] for i in seps}) == 1
    if single_kind and (len(seps) > 1 or len(tail) == 3):
        return float(re.sub(r"[.,]", "", token))
    whole = re.sub(r"[.,]", "", token[:last]) or "0"
    return float(f"{whole}.{tail}")


def parse_amount(value: Any) -> float | None:
    """Parse a printed amount. A lone separator before exactly three digits groups thousands
    ("27.000" and "27,000" are 27000); otherwise the last separator is the decimal point."""
    value = _first(value)
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    text = str(value)
    match = _NUMBER.search(text)
    if not match:
        return None
    amount = _number(re.sub(r"\s", "", match.group()).rstrip(".,"))
    prefix = text[: match.start()]
    negative = "-" in prefix or ("(" in prefix and ")" in text[match.end() :])
    return -amount if negative and amount else amount


def parse_quantity(value: Any) -> float | None:
    text = _text(_first(value))
    if not text:
        return None
    match = re.search(r"\d+(?:[.,]\d+)?", text)
    return float(match.group().replace(",", ".")) if match else None


def _year(token: str) -> int:
    year = int(token)
    if year < 100:
        year += 2000 if year < 70 else 1900
    return year


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _candidate(kind: str, groups: tuple[str, ...], dayfirst: bool) -> date | None:
    if kind == "ymd":
        return _safe_date(int(groups[0]), int(groups[1]), int(groups[2]))
    if kind == "dmy_num":
        a, b = int(groups[0]), int(groups[1])
        day, month = (a, b) if dayfirst else (b, a)
        if month > 12 >= day:
            day, month = month, day
        return _safe_date(_year(groups[2]), month, day)
    if kind == "d_mon_y":
        return _safe_date(_year(groups[2]), _MONTHS[groups[1][:3].lower()], int(groups[0]))
    return _safe_date(_year(groups[2]), _MONTHS[groups[0][:3].lower()], int(groups[1]))


def parse_date(value: Any, dayfirst: bool = True, max_len: int | None = None) -> str | None:
    """Return the ISO date when `value` contains exactly one unambiguous full date, else None."""
    text = _text(value)
    if not text or (max_len is not None and len(text) > max_len):
        return None
    text = re.sub(r"(\d)\s*(?:s\s?t|n\s?d|r\s?d|t\s?h)\b", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\bday\s+of\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"[()\[\]]", " ", text)
    taken: list[tuple[int, int]] = []
    found: set[date] = set()
    for kind, pattern in _DATE_PATTERNS:
        for match in pattern.finditer(text):
            span = match.span()
            if any(span[0] < end and start < span[1] for start, end in taken):
                continue
            parsed = _candidate(kind, match.groups(), dayfirst)
            if parsed:
                taken.append(span)
                found.add(parsed)
    return found.pop().isoformat() if len(found) == 1 else None


# Forms: XFUND and FUNSD


def form_from_entities(entities: list[dict]) -> Form:
    """Title from header entities; one KeyValue per linked question->answer pair, in document order."""
    by_id = {e["id"]: e for e in entities}
    order = {e["id"]: i for i, e in enumerate(entities)}
    headers = [t for t in (_text(e["text"]) for e in entities if e["label"] == "header") if t]
    pairs: set[tuple[int, int]] = set()
    for entity in entities:
        for a, b in entity.get("linking") or []:
            if a not in by_id or b not in by_id:
                continue
            labels = (by_id[a]["label"], by_id[b]["label"])
            if labels == ("question", "answer"):
                pairs.add((a, b))
            elif labels == ("answer", "question"):
                pairs.add((b, a))
    fields = []
    for q, a in sorted(pairs, key=lambda p: (order[p[0]], order[p[1]])):
        key, value = _text(by_id[q]["text"]), _text(by_id[a]["text"])
        if key and value:
            fields.append(KeyValue(key=key, value=value))
    return Form(title=" ".join(headers) or None, fields=fields)


def build_xfund(limit: int | None = None) -> list[Sample]:
    raw = DATA_RAW / "xfund"
    samples = []
    for lang in XFUND_LANGS:
        annotations = download(XFUND_URL.format(file=f"{lang}.val.json"), raw / f"{lang}.val.json")
        archive = download(XFUND_URL.format(file=f"{lang}.val.zip"), raw / f"{lang}.val.zip")
        image_dir = extract(archive, raw / "images" / lang)
        images = {p.name: p for p in image_dir.rglob("*") if p.is_file() and not p.name.startswith(".")}
        documents = json.loads(annotations.read_text("utf-8"))["documents"]
        for doc in documents[:limit]:
            image = images.get(doc["img"]["fname"])
            if image is None:
                raise FileNotFoundError(f"xfund image {doc['img']['fname']} missing from {archive}")
            samples.append(
                Sample(
                    doc_id=f"xfund_{doc['id']}",
                    dataset="xfund",
                    doc_type=DocType.form.value,
                    language=lang,
                    split="val",
                    image_paths=[str(image.resolve())],
                    gold=form_from_entities(doc["document"]).model_dump(),
                )
            )
    return samples


def build_funsd(limit: int | None = None) -> list[Sample]:
    raw = DATA_RAW / "funsd"
    try:
        root = extract(download(FUNSD_URL, raw / "dataset.zip"), raw / "extracted")
    except (DatasetUnavailable, zipfile.BadZipFile) as exc:
        raise DatasetUnavailable(
            f"FUNSD original zip unavailable ({exc}). The Hugging Face mirror {FUNSD_HF} only has BIO "
            "word tags without question->answer linking, so Form.fields cannot be rebuilt faithfully."
        ) from exc
    test = root / "dataset" / "testing_data"
    samples = []
    for ann in sorted((test / "annotations").glob("*.json"))[:limit]:
        image = test / "images" / f"{ann.stem}.png"
        if not image.exists():
            raise FileNotFoundError(f"funsd image missing for {ann.name}")
        entities = json.loads(ann.read_text("utf-8"))["form"]
        samples.append(
            Sample(
                doc_id=f"funsd_{ann.stem}",
                dataset="funsd",
                doc_type=DocType.form.value,
                language="en",
                split="test",
                image_paths=[str(image.resolve())],
                gold=form_from_entities(entities).model_dump(),
            )
        )
    return samples


# Receipts: CORD and SROIE


def _save_image(data: bytes, dest: Path, as_png: bool) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if as_png and not data.startswith(b"\x89PNG"):
        Image.open(BytesIO(data)).save(dest, format="PNG")
    else:
        dest.write_bytes(data)


def _cord_rows() -> list[dict]:
    raw = DATA_RAW / "cord"
    manifest = raw / "test.jsonl"
    rows = _read_manifest(manifest, raw)
    if rows is not None:
        return rows
    rows = []
    for i, row in enumerate(tqdm(_hf_split(CORD_HF, "test", raw), desc="cord", leave=False)):
        ground_truth = json.loads(row["ground_truth"])
        image_id = ground_truth.get("meta", {}).get("image_id", i)
        doc_id = f"cord_test_{image_id:03d}"
        rel = f"images/{doc_id}.png"
        _save_image(row["image"]["bytes"], raw / rel, as_png=True)
        rows.append({"doc_id": doc_id, "image": rel, "ground_truth": ground_truth})
    _write_jsonl(manifest, rows)
    return rows


def _merged(section: Any) -> dict:
    if isinstance(section, dict):
        return section
    merged: dict = {}
    for part in section or []:
        if isinstance(part, dict):
            for key, value in part.items():
                merged.setdefault(key, value)
    return merged


def _as_dicts(value: Any) -> list[dict]:
    return [v for v in (value if isinstance(value, list) else [value]) if isinstance(v, dict)]


def cord_line_items(menu: Any) -> list[LineItem]:
    """One LineItem per menu entry, followed by its priced add-ons (`sub` entries that carry a price)."""
    items = []
    for entry in _as_dicts(menu):
        price = entry.get("price") if entry.get("price") is not None else entry.get("itemsubtotal")
        items.append(
            LineItem(
                description=_text(entry.get("nm")),
                quantity=parse_quantity(entry.get("cnt")),
                unit_price=parse_amount(entry.get("unitprice")),
                total=parse_amount(price),
            )
        )
        for sub in _as_dicts(entry.get("sub")):
            if parse_amount(sub.get("price")) is not None:
                items.append(
                    LineItem(
                        description=_text(sub.get("nm")),
                        quantity=parse_quantity(sub.get("cnt")),
                        unit_price=parse_amount(sub.get("unitprice")),
                        total=parse_amount(sub.get("price")),
                    )
                )
    return [i for i in items if any(v is not None for v in i.model_dump().values())]


def cord_receipt(parse: dict) -> Receipt:
    items = cord_line_items(parse.get("menu"))
    sub_total = _merged(parse.get("sub_total"))
    total = _merged(parse.get("total"))
    discount = parse_amount(sub_total.get("discount_price"))
    return Receipt(
        currency="IDR",
        line_items=items,
        subtotal=parse_amount(sub_total.get("subtotal_price")),
        tax_amount=parse_amount(sub_total.get("tax_price")),
        service_charge=parse_amount(sub_total.get("service_price")),
        discount=abs(discount) if discount is not None else None,
        total=parse_amount(total.get("total_price")),
        cash_paid=parse_amount(total.get("cashprice")),
        change=parse_amount(total.get("changeprice")),
    )


def build_cord(limit: int | None = None) -> list[Sample]:
    raw = DATA_RAW / "cord"
    return [
        Sample(
            doc_id=row["doc_id"],
            dataset="cord",
            doc_type=DocType.receipt.value,
            language="id",
            split="test",
            image_paths=[str((raw / row["image"]).resolve())],
            gold=cord_receipt(row["ground_truth"]["gt_parse"]).model_dump(),
        )
        for row in _cord_rows()[:limit]
    ]


def _sroie_rows() -> list[dict]:
    raw = DATA_RAW / "sroie"
    manifest = raw / "test.jsonl"
    rows = _read_manifest(manifest, raw)
    if rows is not None:
        return rows
    errors = []
    for repo in SROIE_HF:
        try:
            ds = _hf_split(repo, "test", raw)
            break
        except DatasetUnavailable as exc:
            errors.append(str(exc))
    else:
        raise DatasetUnavailable(
            "SROIE task 3 test set unavailable. Tried: " + "; ".join(errors) + ". darentang/sroie is a "
            "loading-script dataset (unsupported by datasets>=4) and zzzDavid/ICDAR-2019-SROIE only ships "
            "the 626 training receipts."
        )
    rows, seen = [], set()
    for i, row in enumerate(tqdm(ds, desc="sroie", leave=False)):
        source = Path(row["image"].get("path") or f"test_{i:03d}.jpg")
        stem = source.stem if source.stem not in seen else f"{source.stem}_{i}"
        seen.add(stem)
        rel = f"images/{stem}{source.suffix.lower() or '.jpg'}"
        _save_image(row["image"]["bytes"], raw / rel, as_png=False)
        rows.append({"doc_id": f"sroie_{stem}", "image": rel, "entities": row["objects"]["entities"]})
    _write_jsonl(manifest, rows)
    return rows


def sroie_receipt(entities: dict) -> Receipt:
    return Receipt(
        merchant_name=_text(entities.get("company")),
        merchant_address=_text(entities.get("address")),
        date=parse_date(entities.get("date"), dayfirst=True),
        currency="MYR",
        total=parse_amount(entities.get("total")),
    )


def build_sroie(limit: int | None = None) -> list[Sample]:
    raw = DATA_RAW / "sroie"
    return [
        Sample(
            doc_id=row["doc_id"],
            dataset="sroie",
            doc_type=DocType.receipt.value,
            language="en",
            split="test",
            image_paths=[str((raw / row["image"]).resolve())],
            gold=sroie_receipt(row["entities"]).model_dump(),
        )
        for row in _sroie_rows()[:limit]
    ]


# Contracts: CUAD


def _norm_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _cuad_answers(paragraph: dict) -> dict[str, list[str]]:
    answers = {}
    for qa in paragraph["qas"]:
        category = qa["id"].rsplit("__", 1)[-1]
        spans = sorted(qa["answers"], key=lambda a: a["answer_start"])
        texts = [t for t in (_text(a["text"]) for a in spans) if t]
        answers[category] = list(dict.fromkeys(texts))
    return answers


def _cuad_date(answers: list[str]) -> str | None:
    for answer in answers:
        parsed = parse_date(answer, dayfirst=False, max_len=80)
        if parsed:
            return parsed
    return answers[0] if answers else None


def cuad_contract(title: str, answers: dict[str, list[str]], contract_type: str | None) -> Contract:
    def first(category: str) -> str | None:
        values = answers.get(category) or []
        return values[0] if values else None

    return Contract(
        document_name=first("Document Name") or title,
        parties=answers.get("Parties") or [],
        agreement_date=_cuad_date(answers.get("Agreement Date") or []),
        effective_date=_cuad_date(answers.get("Effective Date") or []),
        expiration_date=_cuad_date(answers.get("Expiration Date") or []),
        governing_law=first("Governing Law"),
        renewal_term=first("Renewal Term"),
        notice_period_to_terminate=first("Notice Period To Terminate Renewal"),
        contract_type=contract_type,
    )


def _cuad_pdfs(titles: list[str], raw: Path) -> dict[str, tuple[Path, str]]:
    """Match titles to PDFs in the CUAD v1 release and extract only those. Empty if the release is unreachable."""
    try:
        archive = download(CUAD_RELEASE_URL, raw / "CUAD_v1.zip")
    except DatasetUnavailable as exc:
        print(f"cuad: PDFs unavailable, pdf_path left empty ({exc})")
        return {}
    wanted = {_norm_name(t): t for t in titles}
    found: dict[str, tuple[Path, str]] = {}
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            path = Path(info.filename)
            if info.is_dir() or _is_junk(info.filename) or path.suffix.lower() != ".pdf":
                continue
            if "full_contract_pdf" not in path.parts:
                continue
            title = wanted.get(_norm_name(path.stem))
            if title is None or title in found:
                continue
            rel = Path(*path.parts[path.parts.index("full_contract_pdf") :])
            target = raw / rel
            if not target.exists():
                _extract_member(zf, info, raw, str(rel))
            found[title] = (target.resolve(), path.parent.name.replace("_", " ").strip())
    return found


def build_cuad(limit: int | None = None) -> list[Sample]:
    raw = DATA_RAW / "cuad"
    with zipfile.ZipFile(download(CUAD_SPLITS_URL, raw / "data.zip")) as zf:
        contracts = json.loads(zf.read("test.json"))["data"]
    candidates = []
    for entry in contracts:
        paragraph = entry["paragraphs"][0]
        answers = _cuad_answers(paragraph)
        if answers.get("Parties") and answers.get("Governing Law"):
            candidates.append((len(paragraph["context"]), entry["title"], paragraph["context"], answers))
    candidates.sort(key=lambda c: (c[0], c[1]))
    chosen = candidates[: limit or CUAD_SIZE]
    pdfs = _cuad_pdfs([c[1] for c in chosen], raw)
    samples = []
    for _, title, context, answers in chosen:
        pdf, contract_type = pdfs.get(title, (None, None))
        samples.append(
            Sample(
                doc_id="cuad_" + re.sub(r"[^A-Za-z0-9.-]+", "_", title).strip("_"),
                dataset="cuad",
                doc_type=DocType.contract.value,
                language="en",
                split="test",
                image_paths=[],
                pdf_path=str(pdf) if pdf else None,
                text=context,
                gold=cuad_contract(title, answers, contract_type).model_dump(),
            )
        )
    return samples


BUILDERS: dict[str, Callable[[int | None], list[Sample]]] = {
    "xfund": build_xfund,
    "funsd": build_funsd,
    "cord": build_cord,
    "sroie": build_sroie,
    "cuad": build_cuad,
}
