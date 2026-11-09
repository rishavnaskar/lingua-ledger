import json
import random
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from PIL import Image

from lingua_ledger.normalize import parse_amount, parse_date, valid_iban, valid_vat_id
from lingua_ledger.schemas import Invoice
from lingua_ledger.synth import (
    DATE_FORMATS,
    LANGS,
    LOCALES,
    format_date,
    format_money,
    format_number,
    generate,
    make_iban,
    make_vat_id,
)
from lingua_ledger.validate import validate

CORE_RULES = (
    "required_fields_present",
    "total_positive",
    "line_items_sum_subtotal",
    "line_item_arithmetic",
    "tax_math",
    "total_equals_subtotal_plus_tax",
    "date_parseable",
    "due_after_invoice",
    "currency_valid",
    "vat_id_valid",
)


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    out_dir = tmp_path_factory.mktemp("synth")
    return out_dir, generate(n_per_lang=1, out_dir=out_dir)


def test_generate_writes_files_and_manifest(generated):
    out_dir, records = generated
    assert [r["language"] for r in records] == list(LANGS)
    lines = (out_dir / "samples.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == records
    for r in records:
        assert r["dataset"] == "synth_invoices" and r["doc_type"] == "invoice" and r["split"] == "test"
        assert r["text"] is None
        jpg = Path(r["image_paths"][0])
        pdf = Path(r["pdf_path"])
        assert jpg.is_absolute() and jpg.exists() and jpg.suffix == ".jpg"
        assert pdf.exists() and pdf.read_bytes().startswith(b"%PDF")
        png = jpg.with_suffix(".png")
        assert png.exists()
        assert jpg.parent.name == r["language"]
        clean, noisy = Image.open(png), Image.open(jpg)
        assert clean.size == noisy.size
        assert abs(clean.width - 1240) <= 1 and abs(clean.height - 1754) <= 1
        assert noisy.format == "JPEG"


def test_gold_passes_all_validators(generated):
    _, records = generated
    for r in records:
        gold = r["gold"]
        assert Invoice.model_validate(gold).model_dump() == gold
        results = validate("invoice", gold)
        assert not [x.message for x in results if x.passed is False], r["doc_id"]
        passed = {x.rule for x in results if x.passed is True}
        assert set(CORE_RULES) <= passed, r["doc_id"]
        if r["language"] == "ja":
            assert gold["currency"] == "JPY" and gold["iban"] is None
            assert all(float(v).is_integer() for v in (gold["subtotal"], gold["tax_amount"], gold["total"]))
        else:
            assert "iban_valid" in passed
        assert round(sum(item["total"] for item in gold["line_items"]), 2) == gold["subtotal"]
        assert round(gold["subtotal"] + gold["tax_amount"], 2) == gold["total"]
        assert 2 <= len(gold["line_items"]) <= 6


def test_generation_is_deterministic(generated, tmp_path):
    _, records = generated
    again = generate(n_per_lang=1, langs=("de",), out_dir=tmp_path)
    original = next(r for r in records if r["language"] == "de")
    assert again[0]["gold"] == original["gold"]
    assert Path(again[0]["pdf_path"]).read_bytes() == Path(original["pdf_path"]).read_bytes()


def test_generate_rejects_unknown_language(tmp_path):
    with pytest.raises(ValueError):
        generate(n_per_lang=1, langs=("xx",), out_dir=tmp_path)


@pytest.mark.parametrize("lang", LANGS)
def test_printed_amounts_and_dates_round_trip(lang):
    values = [Decimal("0.5"), Decimal("7.20"), Decimal("999.99"), Decimal("1234.56"), Decimal("1234567.89")]
    if lang == "ja":
        values = [Decimal(500), Decimal(1234), Decimal(1234567)]
    for value in values:
        assert parse_amount(format_number(value, lang)) == pytest.approx(float(value))
        assert parse_amount(format_money(value, lang)) == pytest.approx(float(value))
    for day in (date(2026, 1, 1), date(2025, 3, 9), date(2026, 11, 3), date(2025, 12, 31)):
        for variant in range(len(DATE_FORMATS[lang])):
            assert parse_date(format_date(day, lang, variant)) == day.isoformat()


@pytest.mark.parametrize("lang", LANGS)
def test_identifiers_are_valid(lang):
    rng = random.Random(lang)
    country = LOCALES[lang]["country"]
    for _ in range(25):
        assert valid_vat_id(make_vat_id(country, rng))
        if lang != "ja":
            assert valid_iban(make_iban(country, rng, "NWBK" if country == "GB" else ""))
