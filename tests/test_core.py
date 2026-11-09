from lingua_ledger.confidence import Calibrator, agreement, flatten, raw_score, unflatten
from lingua_ledger.llm import strict_schema
from lingua_ledger.ocr import locate_value
from lingua_ledger.schemas import Invoice, OcrPage, Word


def test_flatten_roundtrip():
    data = Invoice(
        vendor_name="ACME",
        line_items=[{"description": "Widget", "quantity": 2, "unit_price": 5, "total": 10}],
        total=10,
    ).model_dump()
    flat = flatten(data)
    assert flat["line_items[0].total"] == 10
    assert flat["vendor_name"] == "ACME"
    back = unflatten(flat, Invoice().model_dump())
    assert back["line_items"][0]["description"] == "Widget"
    assert back["total"] == 10


def test_agreement_numeric_and_text():
    assert agreement("total", 1475.6, "1 475,60") is True
    assert agreement("vendor_name", "Müller GmbH", "Muller GmbH") is True
    assert agreement("total", 10, 11) is False
    assert agreement("total", None, None) is None
    assert agreement("total", None, 5) is False


def test_raw_score_ordering():
    good = raw_score(True, 0.95, "pass", 0.95, True)
    bad = raw_score(False, 0.4, "fail", 0.5, True)
    mid = raw_score(None, None, "na", None, True)
    assert good > mid > bad
    assert 0.02 <= bad and good <= 0.99


def test_calibrator_identity_without_fit():
    assert Calibrator()(0.7, "invoice") == 0.7


def test_calibrator_fit_monotone():
    rows = [("invoice", s / 20, s > 10) for s in range(21)] * 10
    cal = Calibrator.fit(rows, min_rows=10)
    assert cal(0.2, "invoice") <= cal(0.9, "invoice")


def _page():
    words = [
        Word(text=t, conf=c, x0=10 + 60 * i, y0=10, x1=60 + 60 * i, y1=30, line=0)
        for i, (t, c) in enumerate([("Gesamtbetrag", 96), ("1", 80), ("475,60", 92), ("EUR", 95)])
    ]
    return [OcrPage(page=0, width=400, height=100, words=words)]


def test_locate_numeric_value_spanning_words():
    loc = locate_value(1475.6, _page())
    assert loc is not None
    conf, bbox, page = loc
    assert 0.8 <= conf <= 1.0
    assert bbox[0] == 70 and page == 0


def test_locate_missing_value():
    assert locate_value("Rechnungsnummer 42", _page()) is None


def test_strict_schema_closes_objects():
    s = strict_schema({"type": "object", "properties": {"a": {"type": "string", "default": None}}})
    assert s["additionalProperties"] is False
    assert s["required"] == ["a"]
    assert "default" not in s["properties"]["a"]
