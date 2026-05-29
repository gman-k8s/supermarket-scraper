import json
from datetime import date
from pathlib import Path
from models import Deal
from formatter import format_stdout_lines, write_results_json


def _deal(
    store="lidl", name="Hähnchenfilet 500g", price=2.49, brand="Metzgerfrisch",
    original_price=3.99, discount_pct=38.0,
    valid_from=date(2026, 6, 2), valid_to=date(2026, 6, 7), source="marktguru",
) -> Deal:
    return Deal(store, name, price, valid_from, valid_to, source,
                brand=brand, original_price=original_price, discount_pct=discount_pct)


def test_line_contains_store_uppercase():
    assert "[LIDL]" in format_stdout_lines([_deal()])[0]


def test_line_contains_brand_and_product_name():
    line = format_stdout_lines([_deal()])[0]
    assert "Metzgerfrisch" in line
    assert "Hähnchenfilet 500g" in line


def test_line_german_price_format():
    line = format_stdout_lines([_deal(price=2.49, original_price=3.99)])[0]
    assert "2,49€" in line
    assert "3,99€" in line


def test_line_discount_percent():
    assert "-38%" in format_stdout_lines([_deal(discount_pct=38.0)])[0]


def test_line_german_date_range():
    line = format_stdout_lines([_deal(valid_from=date(2026, 6, 2), valid_to=date(2026, 6, 7))])[0]
    assert "02.06" in line
    assert "07.06" in line


def test_line_no_brand_omits_brand_prefix():
    deal = Deal("aldi", "Butter 250g", 1.29, date(2026, 6, 2), date(2026, 6, 7), "marktguru")
    line = format_stdout_lines([deal])[0]
    assert "Butter 250g" in line


def test_line_no_original_price_omits_statt():
    deal = Deal("aldi", "Butter 250g", 1.29, date(2026, 6, 2), date(2026, 6, 7), "marktguru")
    assert "statt" not in format_stdout_lines([deal])[0]


def test_empty_deals_returns_no_results_message():
    assert format_stdout_lines([]) == ["Keine neuen Angebote gefunden."]


def test_write_results_json(tmp_path):
    out = tmp_path / "results.json"
    write_results_json([_deal()], out)
    data = json.loads(out.read_text())
    assert len(data) == 1
    assert data[0]["store"] == "lidl"
    assert data[0]["price"] == 2.49


def test_write_results_json_empty(tmp_path):
    out = tmp_path / "results.json"
    write_results_json([], out)
    assert json.loads(out.read_text()) == []
