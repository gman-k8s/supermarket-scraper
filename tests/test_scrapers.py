# tests/test_scrapers.py
import json
import os
import pytest
from pathlib import Path
from datetime import date
from unittest.mock import patch, MagicMock
from scrapers.marktguru import MarktguruScraper
from scrapers.aktionspreis import AktionsPreisScraper


_FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _marktguru_fixture() -> dict:
    return json.loads((_FIXTURE_DIR / "marktguru_response.json").read_text())


def _make_marktguru(stores=None, products=None):
    return MarktguruScraper(stores=stores or ["lidl"], products=products or ["butter"], zip_code="10115")


def _make_aktionspreis(stores=None, products=None):
    return AktionsPreisScraper(stores=stores or ["netto"], products=products or ["butter"], zip_code="10115")


# ── marktguru ─────────────────────────────────────────────────────────────────

def test_marktguru_item_to_deal():
    scraper = _make_marktguru()
    item = _marktguru_fixture()["results"][0]
    deal = scraper._item_to_deal(item, "lidl")
    assert isinstance(deal.product_name, str) and deal.product_name
    assert isinstance(deal.price, float) and deal.price > 0
    assert isinstance(deal.valid_from, date)
    assert isinstance(deal.valid_to, date)
    assert deal.source == "marktguru"
    assert deal.store == "lidl"


def test_marktguru_product_name_includes_category():
    scraper = _make_marktguru()
    item = _marktguru_fixture()["results"][0]
    deal = scraper._item_to_deal(item, "lidl")
    assert "Butter" in deal.product_name


def test_marktguru_match_store():
    scraper = _make_marktguru(stores=["lidl", "aldi"])
    item = _marktguru_fixture()["results"][0]
    assert scraper._match_store(item) == "lidl"


def test_marktguru_match_store_aldi_variants():
    scraper = _make_marktguru(stores=["aldi"])
    for aldi_name in ["ALDI SÜD", "Aldi Nord", "ALDI"]:
        item = {"advertisers": [{"name": aldi_name}]}
        assert scraper._match_store(item) == "aldi"


def test_marktguru_match_store_netto():
    scraper = _make_marktguru(stores=["netto"])
    item = {"advertisers": [{"name": "Netto Marken-Discount"}]}
    assert scraper._match_store(item) == "netto"


def test_marktguru_match_store_no_match():
    scraper = _make_marktguru(stores=["lidl"])
    item = {"advertisers": [{"name": "REWE"}]}
    assert scraper._match_store(item) is None


def test_marktguru_fetch_calls_api():
    scraper = _make_marktguru()
    mock_config = MagicMock()
    mock_config.headers = {"x-clientkey": "testkey123"}
    mock_config.raise_for_status = MagicMock()
    mock_search = MagicMock()
    mock_search.json.return_value = _marktguru_fixture()
    mock_search.raise_for_status = MagicMock()
    with patch("scrapers.marktguru.requests.get", side_effect=[mock_config, mock_search]) as mock_get:
        deals = scraper.fetch()
    assert mock_get.call_count == 2
    assert isinstance(deals, list)
    assert len(deals) == 2


@pytest.mark.skipif(not os.getenv("LIVE_TESTS"), reason="live network — set LIVE_TESTS=1 to run")
def test_marktguru_live():
    scraper = MarktguruScraper(stores=["lidl"], products=["butter"], zip_code="56073")
    deals = scraper.fetch()
    assert isinstance(deals, list)
    assert len(deals) > 0


# ── aktionspreis ──────────────────────────────────────────────────────────────

_OFFER_DATA_NETTO = {
    "product": {
        "@type": "Product",
        "name": "Meggle Butter",
        "offers": {"@type": "AggregateOffer", "lowPrice": "1.19", "priceCurrency": "EUR"},
        "manufacturer": {"@type": "Organization", "name": "Meggle"},
    },
    "sale_events": [
        {
            "@type": "SaleEvent",
            "startDate": "2026-05-26",
            "endDate": "2026-05-30",
            "organizer": {"name": "Netto Marken-Discount"},
        },
        {
            "@type": "SaleEvent",
            "startDate": "2026-05-26",
            "endDate": "2026-05-30",
            "organizer": {"name": "Penny"},
        },
    ],
}


def test_aktionspreis_parse_offer_filters_store():
    scraper = _make_aktionspreis(stores=["netto"])
    deals = scraper._parse_offer(_OFFER_DATA_NETTO)
    assert len(deals) == 1
    assert deals[0].store == "netto"


def test_aktionspreis_parse_offer_fields():
    scraper = _make_aktionspreis(stores=["netto"])
    deal = scraper._parse_offer(_OFFER_DATA_NETTO)[0]
    assert deal.product_name == "Meggle Butter"
    assert deal.price == 1.19
    assert deal.brand == "Meggle"
    assert deal.source == "aktionspreis"
    assert deal.valid_from == date(2026, 5, 26)
    assert deal.valid_to == date(2026, 5, 30)


def test_aktionspreis_parse_offer_no_matching_store():
    scraper = _make_aktionspreis(stores=["lidl"])
    deals = scraper._parse_offer(_OFFER_DATA_NETTO)
    assert len(deals) == 0


def test_aktionspreis_parse_offer_empty():
    scraper = _make_aktionspreis()
    assert scraper._parse_offer({}) == []
    assert scraper._parse_offer({"product": None, "sale_events": []}) == []


def test_aktionspreis_match_store():
    scraper = _make_aktionspreis(stores=["aldi", "netto"])
    assert scraper._match_store("Aldi Nord") == "aldi"
    assert scraper._match_store("Netto Marken-Discount") == "netto"
    assert scraper._match_store("REWE") is None


def test_aktionspreis_parse_jsonld():
    scraper = _make_aktionspreis()
    html = """
    <script type="application/ld+json">
    {"@type":"Product","name":"Butter Test","offers":{"@type":"AggregateOffer","lowPrice":"1.29"},"manufacturer":{"name":"Brand"}}
    </script>
    <script type="application/ld+json">
    {"@type":"SaleEvent","startDate":"2026-06-01","endDate":"2026-06-07","organizer":{"name":"Netto"}}
    </script>
    """
    result = scraper._parse_jsonld(html)
    assert result["product"]["name"] == "Butter Test"
    assert len(result["sale_events"]) == 1


def test_aktionspreis_fetch_makes_requests():
    scraper = _make_aktionspreis(stores=["netto"], products=["butter"])
    search_html = '<a href="/angebote/meggle-butter-250g">Butter</a>'
    offer_html = """
    <script type="application/ld+json">
    {"@type":"Product","name":"Meggle Butter","offers":{"@type":"AggregateOffer","lowPrice":"1.19"},"manufacturer":{"name":"Meggle"}}
    </script>
    <script type="application/ld+json">
    {"@type":"SaleEvent","startDate":"2026-05-26","endDate":"2026-05-30","organizer":{"name":"Netto Marken-Discount"}}
    </script>
    """
    mock_search = MagicMock()
    mock_search.content = search_html.encode()
    mock_search.raise_for_status = MagicMock()
    mock_offer = MagicMock()
    mock_offer.content = offer_html.encode()
    mock_offer.raise_for_status = MagicMock()
    with patch("scrapers.aktionspreis.requests.get", side_effect=[mock_search, mock_offer]):
        deals = scraper.fetch()
    assert len(deals) == 1
    assert deals[0].store == "netto"


@pytest.mark.skipif(not os.getenv("LIVE_TESTS"), reason="live network — set LIVE_TESTS=1 to run")
def test_aktionspreis_live():
    scraper = AktionsPreisScraper(stores=["netto"], products=["butter"], zip_code="56073")
    deals = scraper.fetch()
    assert isinstance(deals, list)
