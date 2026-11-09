from lingua_ledger.eval.metrics import score_document, score_form_lenient
from lingua_ledger.extract import _clean_form, _task
from lingua_ledger.schemas import DocType

GOLD = {
    "fields": [
        {"key": "住所", "value": "〒391-0012"},
        {"key": "住所", "value": "長野県茅野市金沢2丁目409番地"},
        {"key": "氏名", "value": "木村奈々美印"},
        {"key": "証明の種類と通数", "value": "☑身分証明書"},
        {"key": "証明の種類と通数", "value": "1通"},
    ]
}
PRED = {
    "fields": [
        {"key": "住所", "value": "〒391-0012 長野県茅野市金沢2丁目409番地"},
        {"key": "氏名", "value": "木村奈々美"},
        {"key": "身分証明書", "value": "1通"},
    ]
}


def test_lenient_recovers_fragments_strict_does_not():
    strict = score_document(PRED, GOLD).counts
    lenient = score_form_lenient(PRED, GOLD)
    assert strict.tp == 2 and strict.fp == 1 and strict.fn == 3
    assert lenient.tp == 3 and lenient.fp == 0 and lenient.fn == 2
    assert lenient.f1 > strict.f1


def test_lenient_penalises_invented_pairs():
    pred = {"fields": [{"key": "Telefon", "value": "0000"}, {"key": "住所", "value": "〒391-0012"}]}
    c = score_form_lenient(pred, GOLD)
    assert c.fp == 1 and c.tp == 1


def test_clean_form_drops_booleans_and_trailing_colons():
    data = _clean_form(
        {
            "title": "x",
            "fields": [
                {"key": "Name:", "value": " Hans "},
                {"key": "Sommersemester", "value": "false"},
                {"key": "", "value": "orphan"},
                {"key": "E-Mail：", "value": None},
            ],
        }
    )
    assert data["fields"] == [{"key": "Name", "value": "Hans"}]


def test_form_task_has_extra_rules_only_for_forms():
    assert "checkboxes" in _task(DocType.form, "Extract")
    assert "checkboxes" not in _task(DocType.invoice, "Extract")


def test_form_agreement_matches_pairs_by_label():
    from lingua_ledger.pipeline import score_fields
    from lingua_ledger.schemas import PathOutput

    vision = {
        "title": None,
        "fields": [{"key": "Name:", "value": "Hans"}, {"key": "Telefon", "value": "123"}],
    }
    ocr = {"title": None, "fields": [{"key": "Telefon", "value": "124"}, {"key": "Name", "value": "Hans"}]}
    paths = [PathOutput(path="vision", data=vision), PathOutput(path="ocr_text", data=ocr)]
    out = {f.field: f for f in score_fields(DocType.form, vision, paths, [], [], 0.85)}
    assert out["fields[0].value"].agree is True
    assert out["fields[1].value"].agree is False and out["fields[1].value"].ocr_value == "124"
    assert out["fields[0].key"].agree is True
