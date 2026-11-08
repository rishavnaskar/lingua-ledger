"""Pure parsing and comparison helpers for amounts, dates, identifiers and free text."""

from __future__ import annotations

import math
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal

from dateutil import parser as date_parser
from rapidfuzz import fuzz

AMOUNT_TOLERANCE = 0.01
FUZZY_MATCH_THRESHOLD = 0.9

NUMERIC_FIELDS = frozenset({
    "subtotal", "tax_rate", "tax_amount", "total", "quantity", "unit_price", "service_charge",
    "discount", "cash_paid", "change", "amount", "price",
})
IDENTIFIER_FIELDS = frozenset({"invoice_number", "iban", "vendor_tax_id", "tax_id", "vat_id"})

THREE_DECIMAL_CURRENCIES = ("BHD", "KWD", "OMR", "JOD", "TND", "LYD", "IQD")

ISO_CURRENCIES = frozenset({
    "EUR", "USD", "GBP", "JPY", "CHF", "CNY", "HKD", "SGD", "AUD", "NZD", "CAD", "SEK", "NOK", "DKK",
    "PLN", "CZK", "HUF", "RON", "BGN", "TRY", "RUB", "UAH", "INR", "IDR", "MYR", "THB", "VND", "PHP",
    "KRW", "TWD", "BRL", "MXN", "ARS", "CLP", "COP", "PEN", "ZAR", "AED", "SAR", "QAR", "ILS", "EGP",
    "NGN", "KES", "KWD", "BHD", "OMR", "PKR", "BDT", "LKR",
})

CURRENCY_SYMBOLS = {
    "€": "EUR", "$": "USD", "US$": "USD", "£": "GBP", "¥": "JPY", "円": "JPY", "₹": "INR", "RS": "INR",
    "RP": "IDR", "R$": "BRL", "₩": "KRW", "元": "CNY", "RMB": "CNY", "S$": "SGD", "RM": "MYR",
    "₫": "VND", "฿": "THB", "₱": "PHP", "ZŁ": "PLN", "KČ": "CZK", "₺": "TRY", "FR.": "CHF",
}

IBAN_LENGTHS = {
    "AD": 24, "AE": 23, "AT": 20, "BE": 16, "BG": 22, "CH": 21, "CY": 28, "CZ": 24, "DE": 22, "DK": 18,
    "EE": 20, "ES": 24, "FI": 18, "FR": 27, "GB": 22, "GR": 27, "HR": 21, "HU": 28, "IE": 22, "IS": 26,
    "IT": 27, "LI": 21, "LT": 20, "LU": 20, "LV": 21, "MC": 27, "MT": 31, "NL": 18, "NO": 15, "PL": 28,
    "PT": 25, "RO": 24, "SA": 24, "SE": 24, "SI": 19, "SK": 24, "SM": 27, "TR": 26,
}

VAT_PATTERNS = {
    "DE": r"DE\d{9}",
    "FR": r"FR[0-9A-HJ-NP-Z]{2}\d{9}",
    "ES": r"ES[A-Z0-9]\d{7}[A-Z0-9]",
    "IT": r"IT\d{11}",
    "PT": r"PT\d{9}",
    "NL": r"NL\d{9}B\d{2}",
    "GB": r"GB(?:\d{9}|\d{12}|GD\d{3}|HA\d{3})",
    "XI": r"XI(?:\d{9}|\d{12}|GD\d{3}|HA\d{3})",
    "AT": r"ATU\d{8}",
    "BE": r"BE[01]\d{9}",
    "DK": r"DK\d{8}",
    "FI": r"FI\d{8}",
    "IE": r"IE\d[A-Z0-9+*]\d{5}[A-Z]{1,2}",
    "LU": r"LU\d{8}",
    "PL": r"PL\d{10}",
    "SE": r"SE\d{12}",
    "EL": r"EL\d{9}",
    "CH": r"CHE\d{9}(?:MWST|TVA|IVA)?",
}
OTHER_TAX_ID_PATTERNS = (
    r"T\d{13}",
    r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]",
    r"\d{15,16}",
)
GENERIC_VAT_PATTERN = r"[A-Z]{2}[0-9A-Z]{8,12}"

_AMOUNT_TOKEN = re.compile(r"\d+(?:(?:[.,'’]|\s(?=\d{3}(?!\d)))\d+)*|[.,]\d+")
_LEADING_MINUS = re.compile(r"(?<!\d)[-−–]\s*[^\d\s]{0,4}\s*$")
_TRAILING_MINUS = re.compile(r"\s*[-−](?!\d)")
_OPEN_PAREN = re.compile(r"\(\s*[^\d\s()]{0,4}\s*$")
_CLOSE_PAREN = re.compile(r"\s*[^\d\s()]{0,4}\s*\)")
_THREE_DECIMAL_HINT = re.compile(r"\b(?:" + "|".join(THREE_DECIMAL_CURRENCIES) + r")\b", re.IGNORECASE)

_CJK_DATE = re.compile(r"(\d{2,4})\s*[年년]\s*(\d{1,2})\s*[月월]\s*(\d{1,2})")
_YEAR_FIRST = re.compile(r"(?<!\d)(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)")
_COMPACT_DATE = re.compile(r"((?:19|20)\d{2})(\d{2})(\d{2})")
_NUMERIC_DATE = re.compile(r"(?<!\d)(\d{1,2})[-/.](\d{1,2})[-/.](\d{4}|\d{2})(?!\d)")
_DAY_MONTH_NAME = re.compile(r"(?<![\d])(\d{1,2})(?:st|nd|rd|th|er|o)? ([a-z]+) (\d{4}|\d{2})(?!\d)")
_MONTH_NAME_DAY = re.compile(r"(?<![a-z])([a-z]+) (\d{1,2})(?:st|nd|rd|th)? (\d{4})(?!\d)")
_TIME = re.compile(r"(\d{1,2})\s*[:.h]\s*(\d{2})")

_MONTH_NAMES = (
    ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
     "november", "december"),
    ("januar", "februar", "marz", "april", "mai", "juni", "juli", "august", "september", "oktober",
     "november", "dezember"),
    ("janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout", "septembre", "octobre",
     "novembre", "decembre"),
    ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
     "noviembre", "diciembre"),
    ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre",
     "novembre", "dicembre"),
    ("janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
     "novembro", "dezembro"),
    ("januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober",
     "november", "december"),
    ("januari", "februari", "maret", "april", "mei", "juni", "juli", "agustus", "september", "oktober",
     "november", "desember"),
)
_MONTH_ABBREVIATIONS = {
    "jan": 1, "janv": 1, "ene": 1, "gen": 1, "jaenner": 1, "janner": 1,
    "feb": 2, "fev": 2, "fevr": 2, "febr": 2,
    "mar": 3, "maerz": 3, "mrt": 3,
    "apr": 4, "avr": 4, "abr": 4,
    "may": 5, "mai": 5, "mag": 5,
    "jun": 6, "giu": 6,
    "jul": 7, "juil": 7, "lug": 7,
    "aug": 8, "ago": 8, "agu": 8, "agt": 8,
    "sep": 9, "sept": 9, "set": 9,
    "oct": 10, "okt": 10, "ott": 10, "out": 10,
    "nov": 11,
    "dec": 12, "dez": 12, "dic": 12, "des": 12,
}
MONTHS: dict[str, int] = {name: i + 1 for names in _MONTH_NAMES for i, name in enumerate(names)}
MONTHS.update(_MONTH_ABBREVIATIONS)


def _nfkc(s: object) -> str:
    return unicodedata.normalize("NFKC", str(s))


def _strip_accents(s: str) -> str:
    decomposed = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _number_from_token(token: str, three_decimals: bool) -> float | None:
    t = re.sub(r"[\s'’]", "", token)
    has_dot, has_comma = "." in t, "," in t
    if has_dot and has_comma:
        dec = "." if t.rfind(".") > t.rfind(",") else ","
        other = "," if dec == "." else "."
        head, frac = t.rsplit(dec, 1)
        if dec in head or other in frac:
            return None
        return float(f"{head.replace(other, '') or '0'}.{frac}")
    if not has_dot and not has_comma:
        return float(t)
    sep = "." if has_dot else ","
    parts = t.split(sep)
    head = parts[0]
    if len(parts) > 2:
        if 1 <= len(head) <= 3 and all(len(p) == 3 for p in parts[1:]):
            return float("".join(parts))
        return None
    frac = parts[1]
    if len(frac) == 3 and head not in ("", "0") and len(head) <= 3 and not three_decimals:
        return float(head + frac)
    return float(f"{head or '0'}.{frac}")


def parse_amount(s: object) -> float | None:
    """Parse a money or quantity string in any common locale format into a float."""
    if s is None or isinstance(s, bool):
        return None
    if isinstance(s, (int, float, Decimal)):
        value = float(s)
        return value if math.isfinite(value) else None
    text = _nfkc(s).strip()
    tokens = list(_AMOUNT_TOKEN.finditer(text))
    if not tokens:
        return None
    match = max(reversed(tokens), key=lambda m: sum(ch.isdigit() for ch in m.group()))
    value = _number_from_token(match.group(), bool(_THREE_DECIMAL_HINT.search(text)))
    if value is None:
        return None
    prefix, suffix = text[: match.start()], text[match.end():]
    negative = (
        bool(_LEADING_MINUS.search(prefix))
        or bool(_TRAILING_MINUS.match(suffix))
        or (bool(_OPEN_PAREN.search(prefix)) and bool(_CLOSE_PAREN.match(suffix)))
    )
    return -value if negative and value else value


def _make_date(year: int, month: int, day: int) -> str | None:
    if year < 100:
        year += 2000 if year < 70 else 1900
    if not 1900 <= year <= 2100:
        return None
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _month_number(word: str) -> int | None:
    if word in MONTHS:
        return MONTHS[word]
    if len(word) < 3:
        return None
    candidates = {month for name, month in MONTHS.items() if name.startswith(word)}
    return candidates.pop() if len(candidates) == 1 else None


def _parse_cjk(text: str, dayfirst: bool) -> str | None:
    m = _CJK_DATE.search(text)
    return _make_date(int(m[1]), int(m[2]), int(m[3])) if m else None


def _parse_year_first(text: str, dayfirst: bool) -> str | None:
    m = _YEAR_FIRST.search(text) or _COMPACT_DATE.fullmatch(text)
    return _make_date(int(m[1]), int(m[2]), int(m[3])) if m else None


def _parse_numeric(text: str, dayfirst: bool) -> str | None:
    m = _NUMERIC_DATE.search(text)
    if not m:
        return None
    a, b, year = int(m[1]), int(m[2]), int(m[3])
    if a > 12 >= b:
        day, month = a, b
    elif b > 12 >= a:
        month, day = a, b
    elif dayfirst:
        day, month = a, b
    else:
        month, day = a, b
    return _make_date(year, month, day)


def _parse_month_name(text: str, dayfirst: bool) -> str | None:
    cleaned = _strip_accents(text).lower()
    cleaned = re.sub(r"\b(?:de|del)\b", " ", cleaned)
    cleaned = re.sub(r"[.,/\-]", " ", cleaned)
    cleaned = " ".join(cleaned.split())
    for m in _DAY_MONTH_NAME.finditer(cleaned):
        month = _month_number(m[2])
        if month:
            result = _make_date(int(m[3]), month, int(m[1]))
            if result:
                return result
    for m in _MONTH_NAME_DAY.finditer(cleaned):
        month = _month_number(m[1])
        if month:
            result = _make_date(int(m[3]), month, int(m[2]))
            if result:
                return result
    return None


def _parse_dateutil(text: str, dayfirst: bool) -> str | None:
    try:
        first = date_parser.parse(text, dayfirst=dayfirst, default=datetime(1904, 1, 1))
        second = date_parser.parse(text, dayfirst=dayfirst, default=datetime(1908, 2, 2))
    except (ValueError, OverflowError, TypeError):
        return None
    if first.date() != second.date():
        return None
    return _make_date(first.year, first.month, first.day)


_DATE_PARSERS = (_parse_cjk, _parse_year_first, _parse_numeric, _parse_month_name, _parse_dateutil)


def parse_date(s: object, dayfirst_default: bool = True) -> str | None:
    """Parse a date in any common format into ISO YYYY-MM-DD, or None if no complete date is found."""
    if s is None or isinstance(s, bool):
        return None
    if isinstance(s, datetime):
        return s.date().isoformat()
    if isinstance(s, date):
        return s.isoformat()
    text = _nfkc(s).strip()
    if not text:
        return None
    for parser in _DATE_PARSERS:
        result = parser(text, dayfirst_default)
        if result:
            return result
    return None


def _is_edge_junk(ch: str) -> bool:
    return ch.isspace() or unicodedata.category(ch).startswith("P")


def normalize_text(s: object) -> str:
    """Casefolded, NFKC-normalized text with collapsed whitespace and no punctuation at either end."""
    if s is None:
        return ""
    text = " ".join(_nfkc(s).casefold().split())
    start, end = 0, len(text)
    while start < end and _is_edge_junk(text[start]):
        start += 1
    while end > start and _is_edge_junk(text[end - 1]):
        end -= 1
    return text[start:end]


def text_match(a: object, b: object) -> float:
    """Similarity in [0, 1] between two strings after normalization."""
    na, nb = normalize_text(a), normalize_text(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    return fuzz.ratio(na, nb) / 100.0


def normalize_currency(s: object) -> str | None:
    """Map a currency symbol or code to an upper-case ISO 4217 code where possible."""
    if s is None:
        return None
    text = _nfkc(s).strip().upper()
    if not text:
        return None
    if text in CURRENCY_SYMBOLS:
        return CURRENCY_SYMBOLS[text]
    return text.rstrip(".")


def _compact(s: object) -> str:
    return re.sub(r"[\W_]+", "", _nfkc(s).casefold())


def _leaf(field_name: str) -> str:
    return re.sub(r"\[\d+\]", "", field_name).rsplit(".", 1)[-1]


def _is_blank(v: object) -> bool:
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, (list, dict)) and not v)


def _is_number(v: object) -> bool:
    return isinstance(v, (int, float, Decimal)) and not isinstance(v, bool)


def _times_match(a: object, b: object) -> bool | None:
    ma, mb = _TIME.search(_nfkc(a)), _TIME.search(_nfkc(b))
    if not ma or not mb:
        return None
    return (int(ma[1]), int(ma[2])) == (int(mb[1]), int(mb[2]))


def values_match(field_name: str, a: object, b: object) -> bool:
    """Whether two values of the named field (leaf name or dotted path) should count as the same."""
    if _is_blank(a) and _is_blank(b):
        return True
    if _is_blank(a) or _is_blank(b):
        return False
    leaf = _leaf(field_name)
    if leaf in NUMERIC_FIELDS or (_is_number(a) and _is_number(b)):
        x, y = parse_amount(a), parse_amount(b)
        if x is not None and y is not None:
            return abs(x - y) <= AMOUNT_TOLERANCE + 1e-9
    if leaf.endswith("date"):
        x, y = parse_date(a), parse_date(b)
        if x and y:
            return x == y
    if leaf == "time":
        same = _times_match(a, b)
        if same is not None:
            return same
    if leaf == "currency":
        return normalize_currency(a) == normalize_currency(b)
    if leaf in IDENTIFIER_FIELDS:
        return _compact(a) == _compact(b)
    return normalize_text(a) == normalize_text(b) or text_match(a, b) >= FUZZY_MATCH_THRESHOLD


def _alnum_to_digits(s: str) -> str:
    return "".join(str(int(ch, 36)) for ch in s)


def iban_check_digits(country: str, bban: str) -> str:
    """The two IBAN check digits for a country code and BBAN."""
    remainder = int(_alnum_to_digits((bban + country + "00").upper())) % 97
    return f"{98 - remainder:02d}"


def valid_iban(s: object) -> bool:
    """ISO 13616 structure, known country length and mod-97 checksum."""
    if _is_blank(s):
        return False
    iban = re.sub(r"[\s\-]", "", _nfkc(s)).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", iban):
        return False
    expected = IBAN_LENGTHS.get(iban[:2])
    if expected and len(iban) != expected:
        return False
    return int(_alnum_to_digits(iban[4:] + iban[:4])) % 97 == 1


def valid_vat_id(s: object) -> bool:
    """Format check for EU VAT ids by country prefix, a few other tax ids, and a generic fallback."""
    if _is_blank(s):
        return False
    raw = _nfkc(s).upper()
    if re.fullmatch(r"\s*\d{2}-\d{7}\s*", raw):
        return True
    vat = re.sub(r"[^A-Z0-9+*]", "", raw)
    pattern = VAT_PATTERNS.get(vat[:2])
    if pattern:
        return re.fullmatch(pattern, vat) is not None
    if any(re.fullmatch(p, vat) for p in OTHER_TAX_ID_PATTERNS):
        return True
    return re.fullmatch(GENERIC_VAT_PATTERN, vat) is not None


def valid_currency(code: object) -> bool:
    """Whether the value is a common ISO 4217 currency code."""
    if _is_blank(code):
        return False
    return _nfkc(code).strip().upper() in ISO_CURRENCIES
