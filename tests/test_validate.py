import copy

import pytest

from lingua_ledger.schemas import Invoice, RuleResult
from lingua_ledger.validate import rule_outcome_for_field, validate

INVOICE = {
    "vendor_name": "Müller & Schmidt GmbH",
    "vendor_tax_id": "DE123456789",
    "invoice_number": "RE-2026-00412",
    "invoice_date": "2026-11-03",
    "due_date": "2026-12-03",
    "currency": "EUR",
    "line_items": [
        {"description": "Beratung", "quantity": 2, "unit_price": 100.0, "total": 200.0},
        {"description": "Lizenz", "quantity": 1, "unit_price": 50.5, "total": 50.5},
    ],
    "subtotal": 250.5,
    "tax_rate": 19,
    "tax_amount": 47.6,
    "total": 298.1,
    "iban": "DE89 3704 0044 0532 0130 00",
}


def by_rule(results: list[RuleResult]) -> dict[str, list[RuleResult]]:
    grouped: dict[str, list[RuleResult]] = {}
    for r in results:
        grouped.setdefault(r.rule, []).append(r)
    return grouped


def outcome(results: list[RuleResult], rule: str) -> bool | None:
    passed = {r.passed for r in by_rule(results)[rule]}
    assert len(passed) == 1, f"mixed outcomes for {rule}"
    return passed.pop()


def test_valid_invoice_passes_every_rule():
    results = validate("invoice", INVOICE)
    assert not [r for r in results if r.passed is False]
    for rule in ("required_fields_present", "total_positive", "line_items_sum_subtotal", "line_item_arithmetic",
                 "tax_math", "total_equals_subtotal_plus_tax", "date_parseable", "due_after_invoice",
                 "currency_valid", "iban_valid", "vat_id_valid"):
        assert outcome(results, rule) is True, rule
    assert all(isinstance(r, RuleResult) and r.message for r in results)


def test_accepts_pydantic_model_and_locale_strings():
    data = copy.deepcopy(INVOICE)
    data.update(subtotal="250,50", tax_amount="47,60", total="298,10 €", invoice_date="03.11.2026",
                due_date="3. Dezember 2026")
    assert not [r for r in validate("invoice", data) if r.passed is False]
    model = Invoice.model_validate(INVOICE | {"iban": "DE89370400440532013000"})
    assert not [r for r in validate("invoice", model) if r.passed is False]


def test_invoice_with_wrong_total():
    data = INVOICE | {"total": 310.0}
    results = validate("invoice", data)
    assert outcome(results, "total_equals_subtotal_plus_tax") is False
    assert outcome(results, "tax_math") is True
    assert rule_outcome_for_field(results, "total") == "fail"
    assert rule_outcome_for_field(results, "subtotal") == "fail"
    assert rule_outcome_for_field(results, "invoice_number") == "pass"
    assert rule_outcome_for_field(results, "tax_rate") == "pass"


def test_line_sum_mismatch_and_item_arithmetic():
    data = copy.deepcopy(INVOICE)
    data["line_items"][1]["quantity"] = 3
    results = validate("invoice", data)
    assert outcome(results, "line_items_sum_subtotal") is True
    arithmetic = by_rule(results)["line_item_arithmetic"]
    assert [r.passed for r in arithmetic] == [True, False]
    assert rule_outcome_for_field(results, "line_items[1].quantity") == "fail"
    assert rule_outcome_for_field(results, "line_items[0].quantity") == "pass"

    data = INVOICE | {"subtotal": 260.0}
    results = validate("invoice", data)
    assert outcome(results, "line_items_sum_subtotal") is False
    assert rule_outcome_for_field(results, "line_items[0].total") == "fail"


def test_line_sum_tolerance_is_half_percent():
    data = INVOICE | {"subtotal": 251.5, "tax_amount": 47.79, "total": 299.29}
    assert outcome(validate("invoice", data), "line_items_sum_subtotal") is True
    data = INVOICE | {"subtotal": 252.0, "tax_amount": 47.88, "total": 299.88}
    assert outcome(validate("invoice", data), "line_items_sum_subtotal") is False


def test_invoice_bad_dates_iban_vat_currency():
    data = INVOICE | {"due_date": "2026-10-01", "iban": "DE89 3704 0044 0532 0130 01",
                      "vendor_tax_id": "DE12345", "currency": "EURO"}
    results = validate("invoice", data)
    assert outcome(results, "due_after_invoice") is False
    assert outcome(results, "iban_valid") is False
    assert outcome(results, "vat_id_valid") is False
    assert outcome(results, "currency_valid") is False

    results = validate("invoice", INVOICE | {"invoice_date": "sometime soon"})
    dates = {r.fields[0]: r.passed for r in by_rule(results)["date_parseable"]}
    assert dates == {"invoice_date": False, "due_date": True}
    assert outcome(results, "due_after_invoice") is None


def test_required_fields_and_total_positive():
    results = validate("invoice", INVOICE | {"invoice_number": None, "total": -5})
    required = by_rule(results)["required_fields_present"][0]
    assert required.passed is False and required.fields == ["invoice_number"]
    assert outcome(results, "total_positive") is False
    assert rule_outcome_for_field(results, "invoice_date") == "pass"
    assert outcome(validate("invoice", INVOICE | {"total": "n/a"}), "total_positive") is False
    assert outcome(validate("invoice", INVOICE | {"total": None}), "total_positive") is None


def test_not_applicable_when_inputs_missing():
    results = validate("invoice", {"invoice_number": "1", "total": 10, "invoice_date": "2026-01-01"})
    for rule in ("line_items_sum_subtotal", "line_item_arithmetic", "tax_math", "total_equals_subtotal_plus_tax",
                 "due_after_invoice", "currency_valid", "iban_valid", "vat_id_valid"):
        assert outcome(results, rule) is None, rule
    assert rule_outcome_for_field(results, "iban") == "na"
    assert rule_outcome_for_field(results, "payment_terms") == "na"
    partial_items = {"subtotal": 10, "line_items": [{"total": 5}, {"description": "no amount"}]}
    assert outcome(validate("invoice", partial_items), "line_items_sum_subtotal") is None


def test_receipt_change_math_and_extras():
    receipt = {
        "merchant_name": "Kopi Kenangan",
        "date": "2026-11-03",
        "line_items": [{"description": "Kopi", "quantity": 2, "unit_price": 25000, "total": 50000}],
        "subtotal": 50000,
        "tax_amount": 5000,
        "service_charge": 2500,
        "discount": -7500,
        "total": 50000,
        "cash_paid": 100000,
        "change": 50000,
        "currency": "IDR",
    }
    results = validate("receipt", receipt)
    assert not [r for r in results if r.passed is False]
    assert outcome(results, "change_math") is True
    assert outcome(results, "total_equals_subtotal_plus_tax") is True
    assert "tax_math" not in by_rule(results)

    results = validate("receipt", receipt | {"change": 40000})
    assert outcome(results, "change_math") is False
    assert rule_outcome_for_field(results, "change") == "fail"
    assert outcome(validate("receipt", receipt | {"cash_paid": None}), "change_math") is None


def test_receipt_required_fields():
    results = validate("receipt", {"total": "27.000"})
    assert outcome(results, "required_fields_present") is False
    assert outcome(results, "total_positive") is True
    assert outcome(validate("receipt", {"total": "27.000", "date": "03/11/2026"}), "required_fields_present") is True


def test_form_rules():
    form = {"title": "Application", "fields": [
        {"key": "Name", "value": "Ana Silva"},
        {"key": "Date of birth", "value": ""},
        {"key": "name", "value": "A. Silva"},
    ]}
    results = validate("form", form)
    non_empty = by_rule(results)["fields_non_empty"]
    assert [r.passed for r in non_empty] == [True, False, True]
    assert rule_outcome_for_field(results, "fields[1].value") == "fail"
    duplicates = by_rule(results)["no_duplicate_keys"][0]
    assert duplicates.passed is None and duplicates.message.startswith("Duplicate")
    assert duplicates.fields == ["fields[0].key", "fields[2].key"]
    assert outcome(results, "min_fields") is True
    assert rule_outcome_for_field(results, "fields[0].value") == "pass"

    empty = validate("form", {"fields": []})
    assert outcome(empty, "min_fields") is False
    assert outcome(empty, "fields_non_empty") is None
    assert outcome(empty, "no_duplicate_keys") is None


def test_contract_rules():
    contract = {
        "parties": ["Acme Corp", "Globex Ltd"],
        "agreement_date": "2026-01-10",
        "effective_date": "2026-02-01",
        "expiration_date": "2027-01-31",
        "governing_law": "State of New York",
    }
    results = validate("contract", contract)
    assert not [r for r in results if r.passed is False]

    reversed_dates = contract | {"effective_date": "2027-06-01", "expiration_date": "2026-03-01"}
    results = validate("contract", reversed_dates)
    assert outcome(results, "expiration_after_effective") is False
    assert outcome(results, "effective_not_before_agreement") is True
    assert rule_outcome_for_field(results, "expiration_date") == "fail"

    results = validate("contract", contract | {"effective_date": "2025-12-01"})
    assert outcome(results, "effective_not_before_agreement") is False


@pytest.mark.parametrize(("parties", "expected"), [(["A", "B", "C"], True), (["A"], False), ([], None),
                                                   (["", None], None)])
def test_contract_parties_count(parties, expected):
    results = validate("contract", {"parties": parties})
    assert outcome(results, "parties_count") is expected
    expected_outcome = {True: "pass", False: "fail", None: "na"}[expected]
    assert rule_outcome_for_field(results, "parties[0]") == expected_outcome


def test_contract_missing_fields():
    results = validate("contract", {})
    assert outcome(results, "governing_law_present") is False
    assert outcome(results, "dates_parseable") is None
    assert outcome(results, "expiration_after_effective") is None


def test_unknown_doc_type_and_empty_data():
    assert validate("passport", {"total": 1}) == []
    assert all(r.passed in (None, False) for r in validate("invoice", None))


def test_rule_outcome_for_field_paths():
    results = [
        RuleResult(rule="a", fields=["line_items[0].total", "subtotal"], passed=True),
        RuleResult(rule="b", fields=["line_items"], passed=None),
        RuleResult(rule="c", fields=["parties"], passed=False),
    ]
    assert rule_outcome_for_field(results, "line_items[0].total") == "pass"
    assert rule_outcome_for_field(results, "line_items[1].total") == "na"
    assert rule_outcome_for_field(results, "total") == "na"
    assert rule_outcome_for_field(results, "parties[1]") == "fail"
    assert rule_outcome_for_field(results, "line_items") == "pass"
    assert rule_outcome_for_field([], "total") == "na"
