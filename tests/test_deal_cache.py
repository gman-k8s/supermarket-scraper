from datetime import date, datetime

from deal_cache import CachedTerm, is_fresh, read_term, slugify, write_term
from models import Deal

FETCHED = datetime(2026, 11, 20, 8, 0, 12)
TODAY = date(2026, 11, 20)


def _deals() -> list[Deal]:
    return [
        Deal("lidl", "Frische Vollmilch 1l", 0.99, date(2026, 11, 18), date(2026, 11, 23), "marktguru",
             brand="Milsani", ean="4001234", original_price=1.29),
        Deal("aldi", "H-Milch", 0.89, date(2026, 11, 20), date(2026, 11, 22), "aktionspreis"),
    ]


def test_slugify():
    assert slugify("Äpfel, rot!") == "äpfel-rot"
    assert slugify("  Milch  ") == "milch"


def test_roundtrip(tmp_path):
    deals = _deals()
    write_term(tmp_path, "milch", deals, ["marktguru", "aktionspreis"], FETCHED)
    c = read_term(tmp_path, "milch", TODAY)
    assert isinstance(c, CachedTerm)
    assert [d.to_dict() for d in c.deals] == [d.to_dict() for d in deals]
    assert c.fetched == FETCHED
    assert c.sources == ["marktguru", "aktionspreis"]
    assert c.term == "milch"


def test_header_only_file_is_valid_empty(tmp_path):
    write_term(tmp_path, "safran", [], ["marktguru", "aktionspreis"], FETCHED)
    c = read_term(tmp_path, "safran", TODAY)
    assert c is not None
    assert c.deals == []


def test_expired_deals_dropped(tmp_path):
    old = Deal("lidl", "Alte Milch", 0.5, date(2026, 11, 10), date(2026, 11, 19), "marktguru")
    write_term(tmp_path, "milch", [old] + _deals(), ["marktguru"], FETCHED)
    c = read_term(tmp_path, "milch", TODAY)
    assert "Alte Milch" not in [d.product_name for d in c.deals]
    assert len(c.deals) == 2


def test_tab_in_name_sanitized(tmp_path):
    d = Deal("lidl", "A\tB\nC", 1.0, date(2026, 11, 18), date(2026, 11, 23), "marktguru")
    write_term(tmp_path, "x", [d], ["marktguru"], FETCHED)
    c = read_term(tmp_path, "x", TODAY)
    assert c.deals[0].product_name == "A B C"


def test_missing_file_returns_none(tmp_path):
    assert read_term(tmp_path, "nichtda", TODAY) is None


def test_corrupt_file_without_header_returns_none(tmp_path):
    (tmp_path / "milch.txt").write_text("irgendwas\n", "utf-8")
    assert read_term(tmp_path, "milch", TODAY) is None


def test_corrupt_file_wrong_columns_returns_none(tmp_path):
    write_term(tmp_path, "milch", [], ["marktguru"], FETCHED)
    with open(tmp_path / "milch.txt", "a", encoding="utf-8") as f:
        f.write("a\tb\tc\n")
    assert read_term(tmp_path, "milch", TODAY) is None


def test_is_fresh():
    c = CachedTerm("milch", FETCHED, ["marktguru"], [])
    assert is_fresh(c, datetime(2026, 11, 26, 8, 0), 7)
    assert not is_fresh(c, datetime(2026, 11, 28, 9, 0), 7)
