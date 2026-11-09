import math
from datetime import date

import pytest

from lingua_ledger.normalize import (
    iban_check_digits,
    normalize_currency,
    normalize_text,
    parse_amount,
    parse_date,
    text_match,
    valid_currency,
    valid_iban,
    valid_vat_id,
    values_match,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1 240,00", 1240.0),
        ("1.240,00", 1240.0),
        ("1,240.00", 1240.0),
        ("27.000", 27000.0),
        ("Rp 27.000", 27000.0),
        ("Rp. 27.000,-", 27000.0),
        ("EUR 1.234,56", 1234.56),
        ("$1,234.56", 1234.56),
        ("1 234,56 €", 1234.56),
        ("1 234,56 €", 1234.56),
        ("(12.50)", -12.5),
        ("12,5", 12.5),
        ("-3.00", -3.0),
        ("€ -3.00", -3.0),
        ("12.50-", -12.5),
        ("12.50", 12.5),
        ("1,240", 1240.0),
        ("0.500", 0.5),
        ("BHD 1.234", 1.234),
        ("1.234.567", 1234567.0),
        ("1,234,567.89", 1234567.89),
        ("12 345 678,90", 12345678.9),
        ("1'234.50", 1234.5),
        ("¥55,000", 55000.0),
        ("55,000円", 55000.0),
        ("１２３", 123.0),
        (".50", 0.5),
        ("19%", 19.0),
        ("Total: 1.234,56 (incl. 19% MwSt.)", 1234.56),
        (12, 12.0),
        (3.5, 3.5),
    ],
)
def test_parse_amount(raw, expected):
    assert parse_amount(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", [None, "", "abc", "€", True, float("nan"), "03.11.2026"])
def test_parse_amount_rejects(raw):
    assert parse_amount(raw) is None


def test_parse_amount_zero_is_not_negative():
    value = parse_amount("-0.00")
    assert value == 0.0 and not math.copysign(1, value) < 0


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("03.11.2026", "2026-11-03"),
        ("03/11/2026", "2026-11-03"),
        ("2026-11-03", "2026-11-03"),
        ("11/03/2026", "2026-03-11"),
        ("11/13/2026", "2026-11-13"),
        ("13/11/2026", "2026-11-13"),
        ("3 Nov 2026", "2026-11-03"),
        ("Nov 3, 2026", "2026-11-03"),
        ("25 DEC 2018", "2018-12-25"),
        ("2026年11月3日", "2026-11-03"),
        ("2026年 11月 3日", "2026-11-03"),
        ("03-Nov-26", "2026-11-03"),
        ("2026-11-03T14:30:00Z", "2026-11-03"),
        ("2026-11-03 14:30:00+09:00", "2026-11-03"),
        ("2026/11/03", "2026-11-03"),
        ("20261103", "2026-11-03"),
        ("3. November 2026", "2026-11-03"),
        ("3. März 2026", "2026-03-03"),
        ("1er novembre 2026", "2026-11-01"),
        ("3 février 2026", "2026-02-03"),
        ("3 de noviembre de 2026", "2026-11-03"),
        ("3 de março de 2026", "2026-03-03"),
        ("3 settembre 2026", "2026-09-03"),
        ("Tuesday, November 3rd, 2026", "2026-11-03"),
        ("Date: 3 Nov 2026", "2026-11-03"),
        ("3.11.26", "2026-11-03"),
    ],
)
def test_parse_date(raw, expected):
    assert parse_date(raw) == expected


def test_parse_date_month_first_when_requested():
    assert parse_date("11/03/2026", dayfirst_default=False) == "2026-11-03"
    assert parse_date("13/03/2026", dayfirst_default=False) == "2026-03-13"


def test_parse_date_accepts_date_objects():
    assert parse_date(date(2026, 11, 3)) == "2026-11-03"


@pytest.mark.parametrize("raw", [None, "", "hello", "November 2026", "31/02/2026", "12345678"])
def test_parse_date_rejects(raw):
    assert parse_date(raw) is None


def test_normalize_text():
    assert normalize_text("  ＡＣＭＥ   GmbH.  ") == "acme gmbh"
    assert normalize_text('"Straße"') == "strasse"
    assert normalize_text(None) == ""


def test_text_match():
    assert text_match("ACME GmbH", "acme gmbh.") == 1.0
    assert text_match("", "") == 1.0
    assert text_match("abc", "") == 0.0
    assert 0.8 < text_match("Müller & Schmidt GmbH", "Muller & Schmidt GmbH") < 1.0


@pytest.mark.parametrize(
    ("field", "a", "b", "expected"),
    [
        ("total", "1.234,56 €", 1234.56, True),
        ("total", 1234.56, 1234.57, True),
        ("total", 1234.56, 1234.58, False),
        ("line_items[2].total", "1,240.00", "1 240,00", True),
        ("quantity", "2,5", 2.5, True),
        ("invoice_date", "03.11.2026", "2026-11-03", True),
        ("invoice_date", "03.11.2026", "2026-11-04", False),
        ("due_date", "Nov 3, 2026", "2026年11月3日", True),
        ("vendor_name", "Müller & Schmidt GmbH", "MÜLLER & SCHMIDT GMBH", True),
        ("vendor_name", "Müller & Schmidt GmbH", "Mueller & Schmidt GmbH", True),
        ("vendor_name", "Müller & Schmidt GmbH", "Bergmann Technik AG", False),
        ("invoice_number", "INV-2026-0012", "INV-2026-0013", False),
        ("invoice_number", "INV-2026-0012", "inv 2026 0012", True),
        ("iban", "DE89 3704 0044 0532 0130 00", "DE89370400440532013000", True),
        ("currency", "€", "EUR", True),
        ("currency", "usd", "USD", True),
        ("time", "14:30", "14:30:00", True),
        ("time", "14:30", "14:31", False),
        ("vendor_name", None, "", True),
        ("vendor_name", None, "X", False),
    ],
)
def test_values_match(field, a, b, expected):
    assert values_match(field, a, b) is expected


@pytest.mark.parametrize(
    "iban",
    [
        "DE89 3704 0044 0532 0130 00",
        "GB82 WEST 1234 5698 7654 32",
        "FR14 2004 1010 0505 0001 3M02 606",
        "ES91 2100 0418 4502 0005 1332",
        "IT60 X054 2811 1010 0000 0123 456",
        "PT50 0002 0123 1234 5678 9015 4",
        "NL91ABNA0417164300",
    ],
)
def test_valid_iban(iban):
    assert valid_iban(iban)


@pytest.mark.parametrize(
    "iban",
    ["DE89 3704 0044 0532 0130 01", "DE89370400440532013", "XX00", "", None, "GB82WEST1234569876543"],
)
def test_invalid_iban(iban):
    assert not valid_iban(iban)


def test_iban_check_digits_round_trip():
    bban = "370400440532013000"
    assert valid_iban(f"DE{iban_check_digits('DE', bban)}{bban}")


@pytest.mark.parametrize(
    "vat",
    [
        "DE123456789",
        "DE 123 456 789",
        "FR40303265045",
        "ESB12345678",
        "IT12345678901",
        "PT123456789",
        "NL123456789B01",
        "GB123456789",
        "ATU12345678",
        "T1234567890123",
        "LT123456789",
        "12-3456789",
    ],
)
def test_valid_vat_id(vat):
    assert valid_vat_id(vat)


@pytest.mark.parametrize("vat", ["DE12345678", "FR123", "IT1234567890", "NL123456789", "HELLO", "", None])
def test_invalid_vat_id(vat):
    assert not valid_vat_id(vat)


def test_valid_currency():
    assert valid_currency("EUR")
    assert valid_currency(" jpy ")
    assert not valid_currency("XYZ")
    assert not valid_currency("€")
    assert not valid_currency(None)


def test_normalize_currency():
    assert normalize_currency("€") == "EUR"
    assert normalize_currency("Rp") == "IDR"
    assert normalize_currency("gbp") == "GBP"
    assert normalize_currency(None) is None
