from datetime import date

import pytest

from lingua_ledger.anomaly import country_of, detect, fingerprint, vendor_key
from lingua_ledger.arbiter import _coerce, crop_for, disputes
from lingua_ledger.confidence import raw_score
from lingua_ledger.memory import Correction, Store
from lingua_ledger.schemas import OcrPage, Word

TODAY = date(2026, 11, 9)
INVOICE = {
    "vendor_name": "Bergmann Technik AG",
    "vendor_tax_id": "DE148300477",
    "invoice_number": "RE-2026-00723",
    "invoice_date": "2026-03-19",
    "due_date": "2026-04-02",
    "currency": "EUR",
    "tax_rate": 19.0,
    "total": 503.63,
    "iban": "DE89370400440532013000",
}


def codes(anomalies):
    return {a.code for a in anomalies}


def test_vendor_key_prefers_tax_id():
    assert vendor_key(INVOICE) == "tax:de148300477"
    assert vendor_key({"vendor_name": "Müller  GmbH"}) == "name:müller gmbh"
    assert vendor_key({}) is None


def test_country_from_tax_id_currency_or_language():
    assert country_of(INVOICE, "en") == "DE"
    assert country_of({"currency": "JPY"}, None) == "JP"
    assert country_of({"currency": "EUR"}, "fr") == "FR"


def test_clean_invoice_only_reports_new_vendor():
    assert codes(detect("invoice", INVOICE, "de", None, today=TODAY)) == {"new_vendor"}


def test_unusual_tax_rate_and_future_date():
    data = dict(INVOICE, tax_rate=16.0, invoice_date="2027-01-01", due_date="2027-01-15")
    found = codes(detect("invoice", data, "de", None, today=TODAY))
    assert {"unusual_tax_rate", "date_in_future"} <= found


def test_currency_mismatch_for_japanese_vendor():
    data = {"vendor_name": "佐藤システム", "currency": "EUR", "total": 10}
    assert "currency_mismatch" in codes(detect("invoice", data, "ja", None, today=TODAY))


def test_memory_flags_duplicates_and_bank_change(tmp_path):
    st = Store(tmp_path / "state.json")
    assert st.vendor_for(INVOICE) is None
    st.remember("doc-1", "invoice", INVOICE)
    again = detect("invoice", INVOICE, "de", st.vendor_for(INVOICE), today=TODAY)
    assert "duplicate_invoice" in codes(again)
    changed = dict(INVOICE, invoice_number="RE-2026-00724", iban="DE02120300000000202051")
    found = detect("invoice", changed, "de", st.vendor_for(changed), today=TODAY)
    assert "bank_account_changed" in codes(found)
    assert "duplicate_invoice" not in codes(found)
    reloaded = Store(tmp_path / "state.json")
    assert reloaded.summary()["documents_posted"] == 1


def test_duplicate_by_fingerprint_without_number(tmp_path):
    st = Store(tmp_path / "state.json")
    receipt = {"merchant_name": "Kopitiam", "date": "2026-10-01", "total": 12.5}
    assert fingerprint(receipt) == "2026-10-01|12.50"
    st.remember("r1", "receipt", receipt)
    assert "duplicate_document" in codes(
        detect("receipt", receipt, "id", st.vendor_for(receipt), today=TODAY)
    )


def test_corrections_persist(tmp_path):
    st = Store(tmp_path / "state.json")
    st.add_corrections(
        [Correction(doc_id="d", doc_type="invoice", field="iban", raw_score=0.4, accepted=False)]
    )
    assert Store(tmp_path / "state.json").summary()["fields_fixed"] == 1


def test_disputes_skip_forms_and_missing_values():
    merged = {
        "total": 10,
        "vendor_name": "A",
        "fields": [{"key": "k", "value": "v"}],
        "line_items": [{"total": 5}],
    }
    vision = {
        "total": 10,
        "vendor_name": "A GmbH",
        "fields": [{"key": "k", "value": "x"}],
        "line_items": [{"total": 5}],
    }
    ocr = {
        "total": 11,
        "vendor_name": None,
        "fields": [{"key": "k", "value": "v"}],
        "line_items": [{"total": 6}],
    }
    assert disputes(merged, vision, ocr) == ["total", "line_items[0].total"]


def test_arbiter_adjusts_raw_score():
    base = raw_score(False, 0.8, "na", None, True)
    assert raw_score(False, 0.8, "na", None, True, "vision") > base
    assert raw_score(False, 0.8, "na", None, True, "unreadable") < base


def test_coerce_by_field_type():
    assert _coerce("total", "1 475,60") == pytest.approx(1475.6)
    assert _coerce("invoice_date", "03.11.2026") == "2026-11-03"
    assert _coerce("vendor_name", "  Müller GmbH ") == "Müller GmbH"


def test_crop_falls_back_to_page_when_unlocated():
    from PIL import Image

    page = Image.new("RGB", (1000, 1400), "white")
    words = [Word(text="475,60", conf=90, x0=600, y0=700, x1=700, y1=730, line=0)]
    ocr = [OcrPage(page=0, width=1000, height=1400, words=words)]
    crop, cropped = crop_for([475.6, 476.6], [page], ocr)
    assert cropped and crop.width >= 700 and crop.height < 400
    whole, cropped = crop_for(["nothing here"], [page], ocr)
    assert not cropped and whole.width <= 1200
