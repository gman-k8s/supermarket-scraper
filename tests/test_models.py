from datetime import date
from models import Deal


def test_deal_id_is_deterministic():
    d1 = Deal("lidl", "Hähnchenfilet 500g", 2.49, date(2026, 6, 2), date(2026, 6, 7), "marktguru")
    d2 = Deal("lidl", "Hähnchenfilet 500g", 2.49, date(2026, 6, 2), date(2026, 6, 7), "marktguru")
    assert d1.id == d2.id


def test_deal_id_differs_for_different_products():
    d1 = Deal("lidl", "Hähnchenfilet 500g", 2.49, date(2026, 6, 2), date(2026, 6, 7), "marktguru")
    d2 = Deal("lidl", "Margarine 500g", 0.99, date(2026, 6, 2), date(2026, 6, 7), "marktguru")
    assert d1.id != d2.id


def test_deal_id_is_12_chars():
    d = Deal("lidl", "Butter 250g", 1.29, date(2026, 6, 2), date(2026, 6, 7), "marktguru")
    assert len(d.id) == 12


def test_deal_to_dict_structure():
    d = Deal(
        "lidl", "Hähnchenfilet 500g", 2.49, date(2026, 6, 2), date(2026, 6, 7), "marktguru",
        brand="Metzgerfrisch", original_price=3.99, discount_pct=38.0,
    )
    result = d.to_dict()
    assert result["store"] == "lidl"
    assert result["brand"] == "Metzgerfrisch"
    assert result["price"] == 2.49
    assert result["original_price"] == 3.99
    assert result["discount_pct"] == 38.0
    assert result["valid_from"] == "2026-06-02"
    assert result["valid_to"] == "2026-06-07"
    assert result["source"] == "marktguru"
    assert len(result["id"]) == 12


def test_deal_optional_fields_default_none():
    d = Deal("aldi", "Milch 1L", 0.89, date(2026, 6, 2), date(2026, 6, 7), "aktionspreis")
    assert d.brand is None
    assert d.original_price is None
    assert d.discount_pct is None
