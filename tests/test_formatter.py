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


def _all_lines(deals, products=None):
    return format_stdout_lines(deals, products)


def test_store_header_uppercase():
    lines = _all_lines([_deal()])
    assert "=== LIDL ===" in lines


def test_deal_line_contains_brand_and_product_name():
    lines = _all_lines([_deal()])
    deal_line = next(l for l in lines if "Hähnchenfilet" in l)
    assert "Metzgerfrisch" in deal_line
    assert "Hähnchenfilet 500g" in deal_line


def test_deal_line_german_price_format():
    lines = _all_lines([_deal(price=2.49, original_price=3.99)])
    deal_line = next(l for l in lines if "2,49€" in l)
    assert "3,99€" in deal_line


def test_deal_line_discount_percent():
    lines = _all_lines([_deal(discount_pct=38.0)])
    assert any("-38%" in l for l in lines)


def test_deal_line_german_date_range():
    lines = _all_lines([_deal(valid_from=date(2026, 6, 2), valid_to=date(2026, 6, 7))])
    deal_line = next(l for l in lines if "02.06" in l)
    assert "07.06" in deal_line


def test_deal_line_no_gultig():
    lines = _all_lines([_deal()])
    assert not any("gültig" in l for l in lines)


def test_deal_line_no_brand_omits_brand_prefix():
    deal = Deal("aldi", "Butter 250g", 1.29, date(2026, 6, 2), date(2026, 6, 7), "marktguru")
    lines = _all_lines([deal])
    deal_line = next(l for l in lines if "Butter 250g" in l)
    assert "Butter 250g" in deal_line


def test_deal_line_no_original_price_omits_statt():
    deal = Deal("aldi", "Butter 250g", 1.29, date(2026, 6, 2), date(2026, 6, 7), "marktguru")
    assert not any("statt" in l for l in _all_lines([deal]))


def test_empty_deals_returns_no_results_message():
    assert format_stdout_lines([]) == ["Keine neuen Angebote gefunden."]


def test_groups_by_store():
    deals = [
        _deal(store="aldi", name="Butter"),
        _deal(store="lidl", name="Gouda"),
        _deal(store="aldi", name="Quark"),
    ]
    lines = _all_lines(deals)
    aldi_idx = lines.index("=== ALDI ===")
    lidl_idx = lines.index("=== LIDL ===")
    # ALDI comes before LIDL alphabetically
    assert aldi_idx < lidl_idx
    # Both ALDI deals appear before LIDL header
    aldi_deals = [l for l in lines[aldi_idx:lidl_idx] if l.strip() and "===" not in l]
    assert len(aldi_deals) == 2


def test_coverage_section_with_products():
    deals = [
        _deal(store="lidl", name="Hähnchenfilet", brand=None),
        _deal(store="aldi", name="Butter 250g", brand=None),
    ]
    products = ["hähnchen", "butter", "gouda"]
    lines = _all_lines(deals, products)
    assert "--- Abdeckung ---" in lines
    lidl_cov = next(l for l in lines if l.strip().startswith("LIDL:"))
    assert "1/3" in lidl_cov
    assert "hähnchen" in lidl_cov
    aldi_cov = next(l for l in lines if l.strip().startswith("ALDI:"))
    assert "1/3" in aldi_cov
    assert "butter" in aldi_cov


def test_no_coverage_section_without_products():
    lines = _all_lines([_deal()])
    assert not any("Abdeckung" in l for l in lines)


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
