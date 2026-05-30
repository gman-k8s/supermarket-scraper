import importlib
import sys
import pytest
from datetime import date
from unittest.mock import MagicMock, patch
from models import Deal
from scrapers.base import ScraperError


def _fake_deals() -> list[Deal]:
    return [
        Deal("lidl", "Hähnchenfilet 500g", 2.49, date(2026, 6, 2), date(2026, 6, 7), "marktguru",
             brand="Metzgerfrisch", original_price=3.99, discount_pct=38.0),
    ]


def _run(extra_argv: list[str] | None = None, marktguru_deals=None, cached=False):
    if marktguru_deals is None:
        marktguru_deals = _fake_deals()
    with (
        patch("scrapers.marktguru.MarktguruScraper.fetch", return_value=marktguru_deals),
        patch("scrapers.aktionspreis.AktionsPreisScraper.fetch", return_value=[]),
        patch("cache.Cache.load"),
        patch("cache.Cache.expire"),
        patch("cache.Cache.contains", return_value=cached),
        patch("cache.Cache.save"),
        patch("cache.Cache.add_all"),
        patch("formatter.write_results_json"),
        patch("pathlib.Path.mkdir"),
        patch("sys.argv", ["scraper.py"] + (extra_argv or [])),
    ):
        import scraper
        importlib.reload(scraper)
        scraper.main()


def test_new_deal_is_printed(capsys):
    _run(cached=False)
    assert "LIDL" in capsys.readouterr().out


def test_cached_deal_is_skipped(capsys):
    _run(cached=True)
    assert "Keine neuen Angebote gefunden." in capsys.readouterr().out


def test_force_flag_reports_cached_deal(capsys):
    mock_add_all = MagicMock()
    deals = _fake_deals()
    with (
        patch("scrapers.marktguru.MarktguruScraper.fetch", return_value=deals),
        patch("scrapers.aktionspreis.AktionsPreisScraper.fetch", return_value=[]),
        patch("cache.Cache.load"),
        patch("cache.Cache.expire"),
        patch("cache.Cache.contains", return_value=True),
        patch("cache.Cache.save"),
        patch("cache.Cache.add_all", mock_add_all),
        patch("formatter.write_results_json"),
        patch("pathlib.Path.mkdir"),
        patch("sys.argv", ["scraper.py", "--force"]),
    ):
        import scraper
        importlib.reload(scraper)
        scraper.main()
    assert "LIDL" in capsys.readouterr().out
    mock_add_all.assert_called_once_with([deals[0].id])


def test_both_scrapers_fail_exits_1():
    with (
        patch("scrapers.marktguru.MarktguruScraper.fetch", side_effect=ScraperError("down")),
        patch("scrapers.aktionspreis.AktionsPreisScraper.fetch", side_effect=ScraperError("down")),
        patch("sys.argv", ["scraper.py"]),
    ):
        import scraper
        importlib.reload(scraper)
        with pytest.raises(SystemExit) as exc_info:
            scraper.main()
    assert exc_info.value.code == 1


def test_dry_run_skips_writes(capsys):
    mock_write = MagicMock()
    mock_save = MagicMock()
    with (
        patch("scrapers.marktguru.MarktguruScraper.fetch", return_value=_fake_deals()),
        patch("scrapers.aktionspreis.AktionsPreisScraper.fetch", return_value=[]),
        patch("cache.Cache.load"),
        patch("cache.Cache.expire"),
        patch("cache.Cache.contains", return_value=False),
        patch("cache.Cache.save", mock_save),
        patch("cache.Cache.add_all"),
        patch("formatter.write_results_json", mock_write),
        patch("pathlib.Path.mkdir"),
        patch("sys.argv", ["scraper.py", "--dry-run"]),
    ):
        import scraper
        importlib.reload(scraper)
        scraper.main()
    mock_write.assert_not_called()
    mock_save.assert_not_called()
