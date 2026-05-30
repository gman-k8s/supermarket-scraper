from datetime import date
from models import Deal
from matcher import match_deals


def _deal(name: str, brand: str | None = None, store: str = "lidl") -> Deal:
    return Deal(store, name, 1.99, date(2026, 6, 2), date(2026, 6, 7), "marktguru", brand=brand)


def test_exact_keyword_match():
    assert len(match_deals([_deal("Butter 250g")], ["butter"], threshold=70)) == 1


def test_keyword_substring_in_product_name():
    assert len(match_deals([_deal("Hähnchenfilet 500g")], ["hähnchen"], threshold=70)) == 1


def test_keyword_matches_brand():
    assert len(match_deals([_deal("Hähnchenfilet 500g", brand="Metzgerfrisch")], ["metzgerfrisch"], threshold=70)) == 1


def test_no_match_below_threshold():
    assert len(match_deals([_deal("Orangensaft 1L")], ["butter"], threshold=70)) == 0


def test_case_insensitive():
    assert len(match_deals([_deal("BUTTER 250g")], ["butter"], threshold=70)) == 1


def test_multiple_keywords_one_match():
    deals = [_deal("Hähnchenfilet 500g")]
    assert len(match_deals(deals, ["butter", "hähnchen", "milch"], threshold=70)) == 1


def test_no_duplicates_when_multiple_keywords_match_same_deal():
    deals = [_deal("Hähnchenbutter")]
    assert len(match_deals(deals, ["hähnchen", "butter"], threshold=70)) == 1


def test_umlaut_variant_matches():
    assert len(match_deals([_deal("Grillhähnchen ganz")], ["hähnchen"], threshold=70)) == 1


def test_empty_watchlist_returns_empty():
    assert match_deals([_deal("Butter 250g")], [], threshold=70) == []


def test_empty_deals_returns_empty():
    assert match_deals([], ["butter"], threshold=70) == []


def test_exclusion_removes_buttermilch():
    deals = [_deal("Buttermilch 500ml"), _deal("Butter 250g")]
    result = match_deals(deals, ["butter"], threshold=70, exclusions={"butter": ["buttermilch"]})
    assert len(result) == 1
    assert result[0].product_name == "Butter 250g"


def test_multiword_exclusion():
    deals = [_deal("Butter Milch 1L"), _deal("Butter 250g")]
    result = match_deals(deals, ["butter"], threshold=70, exclusions={"butter": ["butter milch"]})
    assert len(result) == 1
    assert result[0].product_name == "Butter 250g"


def test_exclusion_on_brand():
    deals = [_deal("Frischeprodukt 500ml", brand="Buttermilch Brand")]
    result = match_deals(deals, ["butter"], threshold=70, exclusions={"butter": ["buttermilch"]})
    assert len(result) == 0


def test_exclusion_only_applies_to_its_keyword():
    deals = [_deal("Buttermilch 500ml")]
    result = match_deals(deals, ["milch"], threshold=70, exclusions={"butter": ["buttermilch"]})
    assert len(result) == 1


def test_no_exclusions_no_change():
    deals = [_deal("Buttermilch 500ml")]
    result = match_deals(deals, ["butter"], threshold=70)
    assert len(result) == 1
