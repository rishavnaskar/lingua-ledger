from __future__ import annotations

from pathlib import Path

import pytest

from lingua_ledger.eval.datasets import (
    DATASETS,
    cord_receipt,
    form_from_entities,
    load,
    parse_amount,
    parse_date,
    parse_quantity,
    processed_path,
    sroie_receipt,
)
from lingua_ledger.schemas import SCHEMAS, DocType

EXPECTED = {
    "xfund": ("form", {"de", "es", "fr", "it", "ja", "pt", "zh"}),
    "funsd": ("form", {"en"}),
    "cord": ("receipt", {"id"}),
    "sroie": ("receipt", {"en"}),
    "cuad": ("contract", {"en"}),
}


@pytest.fixture(scope="module", params=DATASETS)
def dataset(request):
    name = request.param
    if not processed_path(name).exists():
        pytest.skip(f"{processed_path(name)} not built")
    return name, load(name)


def test_samples_present_and_unique(dataset):
    _, samples = dataset
    assert len(samples) > 0
    assert len({s.doc_id for s in samples}) == len(samples)


def test_metadata(dataset):
    name, samples = dataset
    doc_type, languages = EXPECTED[name]
    for s in samples:
        assert s.dataset == name
        assert s.doc_type == doc_type
        assert s.language in languages
        assert s.split in {"test", "val"}


def test_gold_matches_schema(dataset):
    _, samples = dataset
    for s in samples:
        schema = SCHEMAS[DocType(s.doc_type)]
        assert schema.model_validate(s.gold).model_dump() == s.gold


def test_files_exist(dataset):
    name, samples = dataset
    for s in samples:
        if name == "cuad":
            assert s.text
        else:
            assert s.image_paths
        for path in s.image_paths:
            assert Path(path).is_absolute() and Path(path).is_file(), path
        if s.pdf_path:
            assert Path(s.pdf_path).is_file(), s.pdf_path


def test_xfund_covers_all_languages():
    if not processed_path("xfund").exists():
        pytest.skip("xfund not built")
    assert {s.language for s in load("xfund")} == EXPECTED["xfund"][1]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("27.000", 27000.0),
        ("Rp 27.000", 27000.0),
        ("27,000", 27000.0),
        ("Rp.56.000", 56000.0),
        ("9.500,00", 9500.0),
        ("Rp 35000.00", 35000.0),
        ("-60.000", -60000.0),
        ("-2 600", -2600.0),
        ("RM 10.60", 10.6),
        ("205.5", 205.5),
        (["62,000", "201"], 62000.0),
        ("", None),
        (None, None),
    ],
)
def test_parse_amount(raw, expected):
    assert parse_amount(raw) == expected


def test_parse_quantity():
    assert [parse_quantity(v) for v in ["x1", "2X", "1 x", "1.00", None]] == [1.0, 2.0, 1.0, 1.0, None]


@pytest.mark.parametrize(
    ("raw", "dayfirst", "expected"),
    [
        ("25/12/2018", True, "2018-12-25"),
        ("25-12-18", True, "2018-12-25"),
        ("25 DEC 2018", True, "2018-12-25"),
        ("27/MAR/2018", True, "2018-03-27"),
        ("4/22/2018", True, "2018-04-22"),
        ("2018/03/27", True, "2018-03-27"),
        ("August 10, 2007", False, "2007-08-10"),
        ("1st day of April, 2018", False, "2018-04-01"),
        ("15t h day of January 2018", False, "2018-01-15"),
        ("9/24/2018", False, "2018-09-24"),
        ("[ ] day of [ ], 2020", False, None),
        ("effective November 1, 2002 until October 31, 2012", False, None),
    ],
)
def test_parse_date(raw, dayfirst, expected):
    assert parse_date(raw, dayfirst=dayfirst) == expected


def test_form_from_entities_pairs_links_in_order():
    entities = [
        {"id": 0, "text": "Application", "label": "header", "linking": []},
        {"id": 1, "text": "Name:", "label": "question", "linking": [[1, 2], [1, 3]]},
        {"id": 2, "text": "Ada", "label": "answer", "linking": [[1, 2]]},
        {"id": 3, "text": "Lovelace", "label": "answer", "linking": [[1, 3]]},
        {"id": 4, "text": "Date:", "label": "question", "linking": [[5, 4]]},
        {"id": 5, "text": " 1843 ", "label": "answer", "linking": []},
        {"id": 6, "text": "Notes", "label": "question", "linking": [[6, 7]]},
        {"id": 7, "text": "", "label": "answer", "linking": []},
    ]
    form = form_from_entities(entities)
    assert form.title == "Application"
    assert [(f.key, f.value) for f in form.fields] == [
        ("Name:", "Ada"),
        ("Name:", "Lovelace"),
        ("Date:", "1843"),
    ]


def test_cord_receipt_mapping():
    parse = {
        "menu": [
            {"nm": "NASI", "cnt": "2x", "unitprice": "@12.500", "price": "25.000"},
            {"nm": "TEH", "cnt": "1", "price": "5,000", "sub": {"nm": "LESS ICE"}},
        ],
        "sub_total": {"subtotal_price": "30.000", "tax_price": "3.000", "discount_price": "-1.000"},
        "total": {"total_price": "Rp 32.000", "cashprice": "50,000", "changeprice": "18.000"},
    }
    receipt = cord_receipt(parse)
    assert [(i.description, i.quantity, i.unit_price, i.total) for i in receipt.line_items] == [
        ("NASI", 2.0, 12500.0, 25000.0),
        ("TEH", 1.0, None, 5000.0),
    ]
    assert (receipt.subtotal, receipt.tax_amount, receipt.discount, receipt.total) == (
        30000,
        3000,
        1000,
        32000,
    )
    assert (receipt.cash_paid, receipt.change, receipt.currency) == (50000, 18000, "IDR")


def test_sroie_receipt_mapping():
    receipt = sroie_receipt(
        {"company": "ABC SDN BHD", "date": "25 DEC 2018", "address": "JOHOR", "total": "RM9.00"}
    )
    assert (receipt.merchant_name, receipt.date, receipt.total, receipt.currency) == (
        "ABC SDN BHD",
        "2018-12-25",
        9.0,
        "MYR",
    )
