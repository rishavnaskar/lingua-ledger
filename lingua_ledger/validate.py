"""Deterministic cross-field validation rules. Pure functions over extracted data; no I/O."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from functools import partial
from typing import Any, Literal

from pydantic import BaseModel

from .normalize import normalize_text, parse_amount, parse_date, valid_currency, valid_iban, valid_vat_id
from .schemas import DocType, RuleResult

Data = dict[str, Any]
Rule = Callable[[Data], list[RuleResult]]

NOT_APPLICABLE = "Not applicable: required inputs are missing"


def _result(rule: str, fields: Iterable[str], passed: bool | None, message: str) -> RuleResult:
    return RuleResult(rule=rule, fields=list(fields), passed=passed, message=message)


def _na(rule: str, fields: Iterable[str], message: str = NOT_APPLICABLE) -> RuleResult:
    return _result(rule, fields, None, message)


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _num(source: dict, key: str) -> float | None:
    return parse_amount(source.get(key))


def _fmt(x: float) -> str:
    return f"{x:,.2f}"


def _close(a: float, b: float, tolerance: float) -> bool:
    return abs(a - b) <= tolerance + 1e-9


def _as_dict(item: Any) -> dict:
    if isinstance(item, BaseModel):
        return item.model_dump()
    return item if isinstance(item, dict) else {}


def _items(data: Data) -> list[dict]:
    return [_as_dict(item) for item in (data.get("line_items") or [])]


def _item_total(item: dict) -> float | None:
    total = _num(item, "total")
    if total is not None:
        return total
    quantity, unit_price = _num(item, "quantity"), _num(item, "unit_price")
    if quantity is not None and unit_price is not None:
        return quantity * unit_price
    return None


def required_fields_invoice(data: Data) -> list[RuleResult]:
    rule = "required_fields_present"
    required = ["invoice_number", "total", "invoice_date"]
    missing = [f for f in required if not _present(data.get(f))]
    if missing:
        return [_result(rule, missing, False, f"Missing required fields: {', '.join(missing)}")]
    return [_result(rule, required, True, "Invoice number, date and total are present")]


def required_fields_receipt(data: Data) -> list[RuleResult]:
    rule = "required_fields_present"
    missing = []
    if not _present(data.get("total")):
        missing.append("total")
    if not (_present(data.get("merchant_name")) or _present(data.get("date"))):
        missing += ["merchant_name", "date"]
    if missing:
        return [_result(rule, missing, False, f"Missing required fields: {', '.join(missing)}")]
    fields = ["total"] + [f for f in ("merchant_name", "date") if _present(data.get(f))]
    return [_result(rule, fields, True, "Total and merchant name or date are present")]


def total_positive(data: Data) -> list[RuleResult]:
    rule = "total_positive"
    total = _num(data, "total")
    if total is None:
        if _present(data.get("total")):
            return [_result(rule, ["total"], False, f"Total '{data.get('total')}' is not a number")]
        return [_na(rule, ["total"])]
    if total > 0:
        return [_result(rule, ["total"], True, f"Total {_fmt(total)} is positive")]
    return [_result(rule, ["total"], False, f"Total {_fmt(total)} is not positive")]


def line_items_sum_subtotal(data: Data) -> list[RuleResult]:
    rule = "line_items_sum_subtotal"
    items = _items(data)
    fields = ["subtotal", *[f"line_items[{i}].total" for i in range(len(items))]]
    subtotal = _num(data, "subtotal")
    totals = [_item_total(item) for item in items]
    if subtotal is None or not items or any(t is None for t in totals):
        return [_na(rule, fields)]
    line_sum = sum(totals)
    tolerance = max(0.02, 0.005 * abs(subtotal))
    if _close(line_sum, subtotal, tolerance):
        return [_result(rule, fields, True, f"Line items sum to the subtotal ({_fmt(subtotal)})")]
    return [
        _result(rule, fields, False, f"Line items sum to {_fmt(line_sum)} but subtotal is {_fmt(subtotal)}")
    ]


def line_item_arithmetic(data: Data) -> list[RuleResult]:
    rule = "line_item_arithmetic"
    results = []
    for i, item in enumerate(_items(data)):
        quantity, unit_price, total = _num(item, "quantity"), _num(item, "unit_price"), _num(item, "total")
        if quantity is None or unit_price is None or total is None:
            continue
        fields = [f"line_items[{i}].quantity", f"line_items[{i}].unit_price", f"line_items[{i}].total"]
        expected = quantity * unit_price
        if _close(expected, total, max(0.02, 0.005 * abs(total))):
            results.append(
                _result(rule, fields, True, f"Line {i + 1}: quantity x unit price = {_fmt(total)}")
            )
        else:
            results.append(
                _result(
                    rule,
                    fields,
                    False,
                    f"Line {i + 1}: quantity x unit price is {_fmt(expected)}, total is {_fmt(total)}",
                )
            )
    return results or [_na(rule, ["line_items"])]


def tax_math(data: Data) -> list[RuleResult]:
    rule = "tax_math"
    fields = ["subtotal", "tax_rate", "tax_amount"]
    subtotal, rate, tax = _num(data, "subtotal"), _num(data, "tax_rate"), _num(data, "tax_amount")
    if subtotal is None or rate is None or tax is None:
        return [_na(rule, fields)]
    expected = subtotal * rate / 100
    if _close(expected, tax, max(0.02, 0.01 * abs(expected))):
        return [_result(rule, fields, True, f"Tax {_fmt(tax)} matches {rate:g}% of {_fmt(subtotal)}")]
    return [
        _result(rule, fields, False, f"{rate:g}% of {_fmt(subtotal)} is {_fmt(expected)}, tax is {_fmt(tax)}")
    ]


def total_matches_components(data: Data, receipt: bool) -> list[RuleResult]:
    rule = "total_equals_subtotal_plus_tax"
    subtotal, tax, total = _num(data, "subtotal"), _num(data, "tax_amount"), _num(data, "total")
    extras = ("service_charge", "discount") if receipt else ()
    fields = ["subtotal", "tax_amount", *extras, "total"]
    if subtotal is None or total is None or (tax is None and not receipt):
        return [_na(rule, fields)]
    used = ["subtotal"] + (["tax_amount"] if tax is not None else [])
    expected = subtotal + (tax or 0.0)
    if receipt:
        service, discount = _num(data, "service_charge"), _num(data, "discount")
        if service is not None:
            expected += service
            used.append("service_charge")
        if discount is not None:
            expected -= abs(discount)
            used.append("discount")
    used.append("total")
    parts = " + ".join(used[:-1]).replace("+ discount", "- discount")
    if _close(expected, total, max(0.02, 0.001 * abs(total))):
        return [_result(rule, used, True, f"{parts} = total ({_fmt(total)})")]
    return [_result(rule, used, False, f"{parts} = {_fmt(expected)}, total is {_fmt(total)}")]


def change_math(data: Data) -> list[RuleResult]:
    rule = "change_math"
    fields = ["cash_paid", "total", "change"]
    cash, total, change = _num(data, "cash_paid"), _num(data, "total"), _num(data, "change")
    if cash is None or total is None or change is None:
        return [_na(rule, fields)]
    expected = cash - total
    if _close(expected, change, max(0.02, 0.001 * abs(cash))):
        return [_result(rule, fields, True, f"Cash paid minus total equals change ({_fmt(change)})")]
    return [
        _result(rule, fields, False, f"Cash paid minus total is {_fmt(expected)}, change is {_fmt(change)}")
    ]


def dates_parseable(data: Data, date_fields: tuple[str, ...], rule: str) -> list[RuleResult]:
    results = []
    for name in date_fields:
        value = data.get(name)
        if not _present(value):
            results.append(_na(rule, [name]))
        elif parse_date(value):
            results.append(_result(rule, [name], True, f"{name} parses as {parse_date(value)}"))
        else:
            results.append(_result(rule, [name], False, f"{name} '{value}' is not a recognisable date"))
    return results


def date_order(data: Data, earlier: str, later: str, rule: str, strict: bool) -> list[RuleResult]:
    first, second = parse_date(data.get(earlier)), parse_date(data.get(later))
    fields = [earlier, later]
    if not first or not second:
        return [_na(rule, fields)]
    ok = second > first if strict else second >= first
    relation = "after" if strict else "on or after"
    if ok:
        return [_result(rule, fields, True, f"{later} {second} is {relation} {earlier} {first}")]
    return [_result(rule, fields, False, f"{later} {second} is not {relation} {earlier} {first}")]


def currency_valid(data: Data) -> list[RuleResult]:
    rule = "currency_valid"
    value = data.get("currency")
    if not _present(value):
        return [_na(rule, ["currency"])]
    if valid_currency(value):
        return [_result(rule, ["currency"], True, f"{value} is an ISO 4217 code")]
    return [_result(rule, ["currency"], False, f"'{value}' is not a known ISO 4217 code")]


def iban_valid(data: Data) -> list[RuleResult]:
    rule = "iban_valid"
    value = data.get("iban")
    if not _present(value):
        return [_na(rule, ["iban"])]
    if valid_iban(value):
        return [_result(rule, ["iban"], True, "IBAN checksum is valid")]
    return [_result(rule, ["iban"], False, "IBAN fails the length or mod-97 check")]


def vat_id_valid(data: Data) -> list[RuleResult]:
    rule = "vat_id_valid"
    value = data.get("vendor_tax_id")
    if not _present(value):
        return [_na(rule, ["vendor_tax_id"])]
    if valid_vat_id(value):
        return [_result(rule, ["vendor_tax_id"], True, "Tax id matches the expected format")]
    return [_result(rule, ["vendor_tax_id"], False, f"'{value}' does not match a known tax id format")]


def _form_fields(data: Data) -> list[dict]:
    return [_as_dict(entry) for entry in (data.get("fields") or [])]


def fields_non_empty(data: Data) -> list[RuleResult]:
    rule = "fields_non_empty"
    entries = _form_fields(data)
    if not entries:
        return [_na(rule, ["fields"])]
    results = []
    for i, entry in enumerate(entries):
        paths = [f"fields[{i}].key", f"fields[{i}].value"]
        empty = [name for name in ("key", "value") if not _present(entry.get(name))]
        if empty:
            results.append(_result(rule, paths, False, f"Field {i + 1} has an empty {' and '.join(empty)}"))
        else:
            results.append(_result(rule, paths, True, f"Field {i + 1} has a key and a value"))
    return results


def no_duplicate_keys(data: Data) -> list[RuleResult]:
    rule = "no_duplicate_keys"
    entries = _form_fields(data)
    keys = [normalize_text(entry.get("key")) for entry in entries]
    present = [i for i, k in enumerate(keys) if k]
    if not present:
        return [_na(rule, ["fields"])]
    duplicates = [i for i in present if keys.count(keys[i]) > 1]
    if duplicates:
        names = sorted({str(entries[i].get("key")) for i in duplicates})
        return [
            _result(
                rule, [f"fields[{i}].key" for i in duplicates], None, f"Duplicate keys {', '.join(names)}"
            )
        ]
    return [_result(rule, [f"fields[{i}].key" for i in present], True, "All keys are unique")]


def min_fields(data: Data) -> list[RuleResult]:
    count = len(_form_fields(data))
    if count >= 1:
        return [_result("min_fields", ["fields"], True, f"{count} fields extracted")]
    return [_result("min_fields", ["fields"], False, "No fields extracted")]


def parties_count(data: Data) -> list[RuleResult]:
    rule = "parties_count"
    parties = [p for p in (data.get("parties") or []) if _present(p)]
    if not parties:
        return [_na(rule, ["parties"], "No parties extracted")]
    if len(parties) >= 2:
        return [_result(rule, ["parties"], True, f"{len(parties)} parties found")]
    return [_result(rule, ["parties"], False, "Only one party found; a contract needs at least two")]


def governing_law_present(data: Data) -> list[RuleResult]:
    if _present(data.get("governing_law")):
        return [_result("governing_law_present", ["governing_law"], True, "Governing law is stated")]
    return [_result("governing_law_present", ["governing_law"], False, "Governing law not found")]


INVOICE_RULES: list[Rule] = [
    required_fields_invoice,
    total_positive,
    line_items_sum_subtotal,
    line_item_arithmetic,
    tax_math,
    partial(total_matches_components, receipt=False),
    partial(dates_parseable, date_fields=("invoice_date", "due_date"), rule="date_parseable"),
    partial(date_order, earlier="invoice_date", later="due_date", rule="due_after_invoice", strict=False),
    currency_valid,
    iban_valid,
    vat_id_valid,
]

RECEIPT_RULES: list[Rule] = [
    required_fields_receipt,
    total_positive,
    line_items_sum_subtotal,
    line_item_arithmetic,
    partial(total_matches_components, receipt=True),
    change_math,
    partial(dates_parseable, date_fields=("date",), rule="date_parseable"),
    currency_valid,
]

FORM_RULES: list[Rule] = [fields_non_empty, no_duplicate_keys, min_fields]

CONTRACT_RULES: list[Rule] = [
    partial(
        dates_parseable,
        date_fields=("agreement_date", "effective_date", "expiration_date"),
        rule="dates_parseable",
    ),
    partial(
        date_order,
        earlier="agreement_date",
        later="effective_date",
        rule="effective_not_before_agreement",
        strict=False,
    ),
    partial(
        date_order,
        earlier="effective_date",
        later="expiration_date",
        rule="expiration_after_effective",
        strict=True,
    ),
    parties_count,
    governing_law_present,
]

RULES: dict[DocType, list[Rule]] = {
    DocType.invoice: INVOICE_RULES,
    DocType.receipt: RECEIPT_RULES,
    DocType.form: FORM_RULES,
    DocType.contract: CONTRACT_RULES,
}


def validate(doc_type: str | DocType, data: Data | BaseModel | None) -> list[RuleResult]:
    """Run every rule for the document type. passed is None where a rule's inputs are missing."""
    try:
        kind = DocType(doc_type)
    except ValueError:
        return []
    payload = data.model_dump() if isinstance(data, BaseModel) else (data or {})
    return [result for rule in RULES[kind] for result in rule(payload)]


def _touches(rule_field: str, field: str) -> bool:
    if rule_field == field:
        return True
    return any(
        longer.startswith(shorter + sep)
        for shorter, longer in ((field, rule_field), (rule_field, field))
        for sep in (".", "[")
    )


def rule_outcome_for_field(results: list[RuleResult], field: str) -> Literal["pass", "fail", "na"]:
    """'fail' if any rule touching the field failed, 'pass' if any passed and none failed, else 'na'."""
    outcomes = [r.passed for r in results if any(_touches(f, field) for f in r.fields)]
    if False in outcomes:
        return "fail"
    if True in outcomes:
        return "pass"
    return "na"
