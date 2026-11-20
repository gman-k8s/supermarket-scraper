import importlib
import sys
import pytest
import json
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch
from models import Deal
from scrapers.base import ScraperError


_DEALS_DIR = None


@pytest.fixture(autouse=True)
def _isolated_deals_dir(tmp_path):
    global _DEALS_DIR
    _DEALS_DIR = tmp_path / "deals"
    yield
    _DEALS_DIR = None


def _reload_and_main():
    import scraper
    importlib.reload(scraper)
    with patch.object(scraper, "_DEALS_DIR", _DEALS_DIR):
        scraper.main()


def _fake_deals() -> list[Deal]:
    return [
        Deal("lidl", "Hähnchenfilet 500g", 2.49, date.today(), date.today() + timedelta(days=5), "marktguru",
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
        patch("price_db.PriceDB.save_all"),
        patch("sys.argv", ["scraper.py"] + (extra_argv or [])),
    ):
        _reload_and_main()


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
        patch("price_db.PriceDB.save_all"),
        patch("sys.argv", ["scraper.py", "--force"]),
    ):
        _reload_and_main()
    assert "LIDL" in capsys.readouterr().out
    mock_add_all.assert_called_once_with([deals[0].id])


def test_both_scrapers_fail_exits_1():
    with (
        patch("scrapers.marktguru.MarktguruScraper.fetch", side_effect=ScraperError("down")),
        patch("scrapers.aktionspreis.AktionsPreisScraper.fetch", side_effect=ScraperError("down")),
        patch("sys.argv", ["scraper.py"]),
    ):
        with pytest.raises(SystemExit) as exc_info:
            _reload_and_main()
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
        patch("price_db.PriceDB.save_all"),
        patch("sys.argv", ["scraper.py", "--dry-run"]),
    ):
        _reload_and_main()
    mock_write.assert_not_called()
    mock_save.assert_not_called()


def _std_patches(argv, fetch=None, cached=False, write_results=None, add_all=None):
    return [
        patch("scrapers.marktguru.MarktguruScraper.fetch", fetch or MagicMock(return_value=_fake_deals())),
        patch("scrapers.aktionspreis.AktionsPreisScraper.fetch", return_value=[]),
        patch("cache.Cache.load"),
        patch("cache.Cache.expire"),
        patch("cache.Cache.contains", return_value=cached),
        patch("cache.Cache.save"),
        patch("cache.Cache.add_all", add_all or MagicMock()),
        patch("formatter.write_results_json", write_results or MagicMock()),
        patch("price_db.PriceDB.save_all"),
        patch("sys.argv", ["scraper.py"] + argv),
    ]


def _run_with(patches):
    from contextlib import ExitStack
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        _reload_and_main()


def test_terms_are_searched():
    import scrapers.marktguru as mg
    seen: list[list[str]] = []

    def fake_fetch(self):
        seen.append(list(self.products))
        return []

    with patch.object(mg.MarktguruScraper, "fetch", fake_fetch):
        _run_with(_std_patches(["--terms", "Kaffee, eier", "--dry-run"])[1:])
    assert ["kaffee"] in seen
    assert ["eier"] in seen
    assert ["butter"] in seen


def test_json_output_shape(capsys):
    _run_with(_std_patches(["--json"]))
    data = json.loads(capsys.readouterr().out)
    assert data["terms"]["butter"]["deals"][0]["store"] == "lidl"
    assert data["terms"]["butter"]["from_cache"] is False
    assert "generated_at" in data and data["warnings"] == []


def test_json_skips_results_and_seen_cache():
    write_results, add_all = MagicMock(), MagicMock()
    _run_with(_std_patches(["--json"], write_results=write_results, add_all=add_all))
    write_results.assert_not_called()
    add_all.assert_not_called()


def test_all_flag_shows_seen_without_fetch(capsys):
    from config import load_products
    from deal_cache import write_term
    for term in load_products():
        write_term(_DEALS_DIR, term, _fake_deals_current(), ["marktguru", "aktionspreis"], datetime.now())
    fetch = MagicMock(return_value=[])
    _run_with(_std_patches(["--all"], fetch=fetch, cached=True))
    assert "LIDL" in capsys.readouterr().out
    fetch.assert_not_called()


def test_missing_max_age_defaults_to_7():
    import deal_loader
    settings = {"scraping": {"zip_code": "10115"}, "matching": {"threshold": 70},
                "network": {"timeout_seconds": 10, "retries": 2}, "cache": {"ttl_days": 14}}
    real = deal_loader.load_deals
    with patch("config.load_settings", return_value=settings), \
         patch("deal_loader.load_deals", side_effect=real) as spy:
        _run_with(_std_patches(["--dry-run"]))
    assert spy.call_args.kwargs["max_age_days"] == 7


def test_dry_run_writes_no_text_cache():
    _run_with(_std_patches(["--dry-run"]))
    assert not _DEALS_DIR.exists() or list(_DEALS_DIR.iterdir()) == []


def _fake_deals_current() -> list[Deal]:
    today = date.today()
    return [Deal("lidl", "Hähnchenfilet 500g", 2.49, today, today, "marktguru", brand="Metzgerfrisch")]


def test_deadline_zero_json_lists_skipped(capsys):
    fetch = MagicMock(return_value=[])
    _run_with(_std_patches(["--json", "--deadline", "0", "--terms", "kaffee"], fetch=fetch))
    data = json.loads(capsys.readouterr().out)
    fetch.assert_not_called()
    assert "kaffee" in data["skipped"]
    assert "kaffee" not in data["terms"]
