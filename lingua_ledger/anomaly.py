"""Business-level anomaly checks that go beyond a single document: duplicates, changed bank details,
implausible dates and tax rates. Pure functions over extracted data plus an optional vendor memory."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .normalize import normalize_text, parse_amount, parse_date
from .schemas import Anomaly, DocType

VAT_RATES = {
    "DE": {19, 7, 0},
    "FR": {20, 10, 5.5, 2.1, 0},
    "ES": {21, 10, 4, 0},
    "IT": {22, 10, 5, 4, 0},
    "PT": {23, 13, 6, 0},
    "NL": {21, 9, 0},
    "BE": {21, 12, 6, 0},
    "AT": {20, 13, 10, 0},
    "GB": {20, 5, 0},
    "IE": {23, 13.5, 9, 0},
    "PL": {23, 8, 5, 0},
    "JP": {10, 8, 0},
    "ID": {11, 12, 0},
    "IN": {5, 12, 18, 28, 0},
    "SG": {9, 0},
    "AU": {10, 0},
    "CH": {8.1, 2.6, 3.8, 0},
}
LANGUAGE_COUNTRY = {
    "de": "DE",
    "fr": "FR",
    "es": "ES",
    "it": "IT",
    "pt": "PT",
    "nl": "NL",
    "ja": "JP",
    "id": "ID",
    "pl": "PL",
    "hi": "IN",
}
CURRENCY_COUNTRY = {
    "JPY": "JP",
    "IDR": "ID",
    "INR": "IN",
    "GBP": "GB",
    "CHF": "CH",
    "PLN": "PL",
    "SGD": "SG",
    "AUD": "AU",
}
COUNTRY_CURRENCY = {
    "JP": "JPY",
    "ID": "IDR",
    "IN": "INR",
    "GB": "GBP",
    "CH": "CHF",
    "PL": "PLN",
    "SG": "SGD",
    "AU": "AUD",
    "DE": "EUR",
    "FR": "EUR",
    "ES": "EUR",
    "IT": "EUR",
    "PT": "EUR",
    "NL": "EUR",
    "BE": "EUR",
    "AT": "EUR",
    "IE": "EUR",
}


def vendor_key(data: dict[str, Any]) -> str | None:
    tax_id = normalize_text(data.get("vendor_tax_id") or "").replace(" ", "")
    if tax_id:
        return f"tax:{tax_id}"
    name = normalize_text(data.get("vendor_name") or data.get("merchant_name") or "")
    return f"name:{name}" if name else None


def fingerprint(data: dict[str, Any]) -> str | None:
    total = parse_amount(data.get("total"))
    when = parse_date(data.get("invoice_date") or data.get("date"))
    if total is None or not when:
        return None
    return f"{when}|{total:.2f}"


def country_of(data: dict[str, Any], language: str | None) -> str | None:
    for key in ("vendor_tax_id", "iban"):
        value = str(data.get(key) or "").strip().upper()
        if len(value) >= 2 and value[:2].isalpha() and value[:2] in VAT_RATES:
            return value[:2]
    currency = str(data.get("currency") or "").upper()
    if currency in CURRENCY_COUNTRY:
        return CURRENCY_COUNTRY[currency]
    return LANGUAGE_COUNTRY.get((language or "").lower())


def detect(
    doc_type: DocType | str,
    data: dict[str, Any],
    language: str | None = None,
    vendor: dict[str, Any] | None = None,
    today: date | None = None,
) -> list[Anomaly]:
    kind = DocType(doc_type)
    today = today or date.today()
    out: list[Anomaly] = []
    if kind in (DocType.invoice, DocType.receipt):
        out += _dates(kind, data, today)
        out += _vendor_memory(kind, data, vendor)
    if kind == DocType.invoice:
        out += _tax_rate(data, language)
        out += _currency(data, language)
    if kind == DocType.contract:
        out += _contract_dates(data, today)
    return out


def _dates(kind: DocType, data: dict[str, Any], today: date) -> list[Anomaly]:
    out = []
    field = "invoice_date" if kind == DocType.invoice else "date"
    when = parse_date(data.get(field))
    if when:
        d = date.fromisoformat(when)
        if d > today + timedelta(days=7):
            out.append(
                Anomaly(
                    code="date_in_future",
                    severity="high",
                    fields=[field],
                    message=f"{field.replace('_', ' ').capitalize()} {when} is in the future",
                )
            )
        elif d < today - timedelta(days=730):
            out.append(
                Anomaly(
                    code="date_stale",
                    severity="warn",
                    fields=[field],
                    message=f"{field.replace('_', ' ').capitalize()} {when} is more than two years old",
                )
            )
    due = parse_date(data.get("due_date"))
    if due and when and (date.fromisoformat(due) - date.fromisoformat(when)).days > 180:
        out.append(
            Anomaly(
                code="long_payment_term",
                severity="info",
                fields=["due_date"],
                message=f"Due date {due} is more than 180 days after the invoice date",
            )
        )
    return out


def _vendor_memory(kind: DocType, data: dict[str, Any], vendor: dict[str, Any] | None) -> list[Anomaly]:
    out = []
    key = vendor_key(data)
    if key is None:
        return out
    if not vendor:
        out.append(
            Anomaly(
                code="new_vendor",
                severity="info",
                fields=["vendor_name" if kind == DocType.invoice else "merchant_name"],
                message="First document from this vendor; nothing to compare against yet",
            )
        )
        return out
    number = normalize_text(data.get("invoice_number") or "")
    if number and number in vendor.get("invoice_numbers", []):
        out.append(
            Anomaly(
                code="duplicate_invoice",
                severity="high",
                fields=["invoice_number"],
                message=f"Invoice number {data.get('invoice_number')} was already posted for this vendor",
            )
        )
    fp = fingerprint(data)
    if fp and fp in vendor.get("fingerprints", []) and not any(a.code == "duplicate_invoice" for a in out):
        out.append(
            Anomaly(
                code="duplicate_document",
                severity="high",
                fields=["total"],
                message="Same vendor, date and total as a document already posted",
            )
        )
    iban = normalize_text(data.get("iban") or "").replace(" ", "")
    known = vendor.get("ibans", [])
    if iban and known and iban not in known:
        out.append(
            Anomaly(
                code="bank_account_changed",
                severity="high",
                fields=["iban"],
                message="IBAN differs from the account this vendor was paid to before",
            )
        )
    currency = str(data.get("currency") or "").upper()
    seen = vendor.get("currencies", [])
    if currency and seen and currency not in seen:
        out.append(
            Anomaly(
                code="currency_changed",
                severity="warn",
                fields=["currency"],
                message=f"Vendor previously invoiced in {', '.join(seen)}, now {currency}",
            )
        )
    out.append(
        Anomaly(
            code="known_vendor",
            severity="info",
            fields=[],
            message=f"Vendor seen {vendor.get('documents', 0)} time(s) before",
        )
    )
    return out


def _tax_rate(data: dict[str, Any], language: str | None) -> list[Anomaly]:
    rate = parse_amount(data.get("tax_rate"))
    if rate is None:
        return []
    country = country_of(data, language)
    allowed = VAT_RATES.get(country or "")
    if not allowed:
        return []
    if not any(abs(rate - r) < 0.05 for r in allowed):
        shown = ", ".join(f"{r:g}" for r in sorted(allowed, reverse=True) if r)
        return [
            Anomaly(
                code="unusual_tax_rate",
                severity="warn",
                fields=["tax_rate"],
                message=f"Tax rate {rate:g}% is not a standard rate in {country} ({shown}%)",
            )
        ]
    return []


def _currency(data: dict[str, Any], language: str | None) -> list[Anomaly]:
    currency = str(data.get("currency") or "").upper()
    country = country_of({k: v for k, v in data.items() if k != "currency"}, language)
    expected = COUNTRY_CURRENCY.get(country or "")
    if currency and expected and currency != expected:
        return [
            Anomaly(
                code="currency_mismatch",
                severity="info",
                fields=["currency"],
                message=f"{currency} is unusual for a {country} vendor; {expected} expected",
            )
        ]
    return []


def _contract_dates(data: dict[str, Any], today: date) -> list[Anomaly]:
    out = []
    exp = parse_date(data.get("expiration_date"))
    if exp and date.fromisoformat(exp) < today:
        out.append(
            Anomaly(
                code="contract_expired",
                severity="warn",
                fields=["expiration_date"],
                message=f"Contract expired on {exp}",
            )
        )
    elif exp and date.fromisoformat(exp) < today + timedelta(days=90):
        out.append(
            Anomaly(
                code="contract_expiring",
                severity="info",
                fields=["expiration_date"],
                message=f"Contract expires within 90 days, on {exp}",
            )
        )
    return out
