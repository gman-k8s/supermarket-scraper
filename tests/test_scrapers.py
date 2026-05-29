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


def test_marktguru_parse_returns_deals():
    scraper = MarktguruScraper(stores=["lidl"], zip_code="10115")
    deals = scraper._parse(_marktguru_fixture(), "lidl")
    assert len(deals) > 0


def test_marktguru_deal_fields():
    scraper = MarktguruScraper(stores=["lidl"], zip_code="10115")
    deal = scraper._parse(_marktguru_fixture(), "lidl")[0]
    assert isinstance(deal.product_name, str) and deal.product_name
    assert isinstance(deal.price, float) and deal.price > 0
    assert isinstance(deal.valid_from, date)
    assert isinstance(deal.valid_to, date)
    assert deal.source == "marktguru"
    assert deal.store == "lidl"


def test_marktguru_fetch_calls_api():
    scraper = MarktguruScraper(stores=["lidl"], zip_code="10115")
    mock_resp = MagicMock()
    mock_resp.json.return_value = _marktguru_fixture()
    mock_resp.raise_for_status = MagicMock()
    with patch("scrapers.marktguru.requests.get", return_value=mock_resp) as mock_get:
        deals = scraper.fetch()
    mock_get.assert_called_once()
    assert isinstance(deals, list)


@pytest.mark.skipif(not os.getenv("LIVE_TESTS"), reason="live network — set LIVE_TESTS=1 to run")
def test_marktguru_live():
    scraper = MarktguruScraper(stores=["lidl"], zip_code="10115")
    deals = scraper.fetch()
    assert isinstance(deals, list)


def _aktionspreis_fixture() -> dict:
    return json.loads((_FIXTURE_DIR / "aktionspreis_response.json").read_text())


def test_aktionspreis_parse_returns_deals():
    scraper = AktionsPreisScraper(stores=["netto"], zip_code="10115")
    deals = scraper._parse(_aktionspreis_fixture(), "netto")
    assert len(deals) > 0


def test_aktionspreis_deal_fields():
    scraper = AktionsPreisScraper(stores=["netto"], zip_code="10115")
    deal = scraper._parse(_aktionspreis_fixture(), "netto")[0]
    assert isinstance(deal.product_name, str) and deal.product_name
    assert isinstance(deal.price, float) and deal.price > 0
    assert deal.source == "aktionspreis"
    assert deal.store == "netto"
    assert isinstance(deal.valid_from, date)
    assert isinstance(deal.valid_to, date)


def test_aktionspreis_fetch_calls_api():
    scraper = AktionsPreisScraper(stores=["netto"], zip_code="10115")
    mock_resp = MagicMock()
    mock_resp.json.return_value = _aktionspreis_fixture()
    mock_resp.raise_for_status = MagicMock()
    with patch("scrapers.aktionspreis.requests.get", return_value=mock_resp) as mock_get:
        deals = scraper.fetch()
    mock_get.assert_called_once()
    assert isinstance(deals, list)


@pytest.mark.skipif(not os.getenv("LIVE_TESTS"), reason="live network — set LIVE_TESTS=1 to run")
def test_aktionspreis_live():
    scraper = AktionsPreisScraper(stores=["netto"], zip_code="10115")
    deals = scraper.fetch()
    assert isinstance(deals, list)
