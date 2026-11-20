from datetime import date, datetime, timedelta

from deal_cache import read_term, write_term
from deal_loader import LoadResult, load_deals
from models import Deal
from scrapers.base import ScraperError

NOW = datetime(2026, 11, 20, 8, 0)


def _deal(name: str, source: str = "marktguru") -> Deal:
    return Deal("lidl", name, 1.0, date(2026, 11, 18), date(2026, 11, 25), source)


class FakeScraper:
    def __init__(self, name: str, results: dict[str, list[Deal]] | None = None, fail: bool = False):
        self.name = name
        self.results = results or {}
        self.fail = fail
        self.products: list[str] = []
        self.calls: list[list[str]] = []

    def fetch(self) -> list[Deal]:
        self.calls.append(list(self.products))
        if self.fail:
            raise ScraperError(f"{self.name} kaputt")
        return [d for p in self.products for d in self.results.get(p, [])]


def _load(tmp_path, terms, scrapers, **kw) -> LoadResult:
    args = dict(force=False, max_age_days=7, write_cache=True, now=NOW)
    args.update(kw)
    return load_deals(terms, scrapers, tmp_path, **args)


def test_fresh_cache_is_used_without_fetch(tmp_path):
    write_term(tmp_path, "milch", [_deal("Cached Milch")], ["marktguru", "aktionspreis"], NOW - timedelta(days=1))
    a = FakeScraper("marktguru")
    r = _load(tmp_path, ["milch"], [a])
    assert a.calls == []
    assert r.terms["milch"].from_cache is True
    assert [d.product_name for d in r.terms["milch"].deals] == ["Cached Milch"]


def test_stale_cache_triggers_fetch_and_rewrite(tmp_path):
    write_term(tmp_path, "milch", [_deal("Old")], ["marktguru"], NOW - timedelta(days=8))
    a = FakeScraper("marktguru", {"milch": [_deal("New")]})
    r = _load(tmp_path, ["milch"], [a])
    assert a.calls == [["milch"]]
    assert r.terms["milch"].from_cache is False
    assert [d.product_name for d in read_term(tmp_path, "milch", NOW.date()).deals] == ["New"]


def test_missing_term_fetched_and_written(tmp_path):
    a = FakeScraper("marktguru", {"eier": [_deal("Eier")]})
    b = FakeScraper("aktionspreis", {"eier": [_deal("Eier AP", "aktionspreis")]})
    r = _load(tmp_path, ["eier"], [a, b])
    assert len(r.terms["eier"].deals) == 2
    cached = read_term(tmp_path, "eier", NOW.date())
    assert cached.sources == ["marktguru", "aktionspreis"]
    assert r.terms["eier"].fetched == NOW


def test_force_refetches_fresh_cache(tmp_path):
    write_term(tmp_path, "milch", [_deal("Cached")], ["marktguru"], NOW - timedelta(hours=1))
    a = FakeScraper("marktguru", {"milch": [_deal("Fresh")]})
    r = _load(tmp_path, ["milch"], [a], force=True)
    assert a.calls == [["milch"]]
    assert [d.product_name for d in r.terms["milch"].deals] == ["Fresh"]


def test_partial_failure_not_written(tmp_path):
    a = FakeScraper("marktguru", {"milch": [_deal("A")]})
    b = FakeScraper("aktionspreis", fail=True)
    r = _load(tmp_path, ["milch"], [a, b])
    assert [d.product_name for d in r.terms["milch"].deals] == ["A"]
    assert read_term(tmp_path, "milch", NOW.date()) is None
    assert len(r.warnings) == 1
    assert "aktionspreis" in r.warnings[0]
    assert r.all_sources_failed is False


def test_total_failure_falls_back_to_old_file(tmp_path):
    write_term(tmp_path, "milch", [_deal("Old")], ["marktguru"], NOW - timedelta(days=10))
    r = _load(tmp_path, ["milch"], [FakeScraper("marktguru", fail=True), FakeScraper("aktionspreis", fail=True)])
    assert r.terms["milch"].from_cache is True
    assert [d.product_name for d in r.terms["milch"].deals] == ["Old"]


def test_all_sources_failed_flag(tmp_path):
    r = _load(tmp_path, ["milch", "eier"], [FakeScraper("marktguru", fail=True), FakeScraper("aktionspreis", fail=True)])
    assert r.all_sources_failed is True
    assert r.terms["milch"].deals == []


def test_all_sources_failed_false_when_nothing_fetched(tmp_path):
    write_term(tmp_path, "milch", [], ["marktguru"], NOW)
    r = _load(tmp_path, ["milch"], [FakeScraper("marktguru", fail=True)])
    assert r.all_sources_failed is False


def test_write_cache_false_writes_nothing(tmp_path):
    a = FakeScraper("marktguru", {"milch": [_deal("A")]})
    _load(tmp_path, ["milch"], [a], write_cache=False)
    assert list(tmp_path.iterdir()) == []


def test_online_deals_collected(tmp_path):
    write_term(tmp_path, "milch", [_deal("Cached")], ["marktguru"], NOW)
    a = FakeScraper("marktguru", {"eier": [_deal("Eier")]})
    r = _load(tmp_path, ["milch", "eier"], [a])
    assert [d.product_name for d in r.online_deals] == ["Eier"]


def test_partial_failure_merges_cached_deals_of_failed_source(tmp_path):
    write_term(tmp_path, "milch", [_deal("Old MG"), _deal("Old AP", "aktionspreis")], ["marktguru", "aktionspreis"],
               NOW - timedelta(days=8))
    a = FakeScraper("marktguru", {"milch": [_deal("New MG")]})
    b = FakeScraper("aktionspreis", fail=True)
    r = _load(tmp_path, ["milch"], [a, b])
    assert sorted(d.product_name for d in r.terms["milch"].deals) == ["New MG", "Old AP"]
    cached = read_term(tmp_path, "milch", NOW.date())
    assert sorted(d.product_name for d in cached.deals) == ["New MG", "Old AP"]
    assert cached.fetched == NOW


def test_total_failure_with_cache_fallback_is_not_all_failed(tmp_path):
    write_term(tmp_path, "milch", [_deal("Old")], ["marktguru"], NOW - timedelta(days=10))
    r = _load(tmp_path, ["milch"], [FakeScraper("marktguru", fail=True), FakeScraper("aktionspreis", fail=True)])
    assert r.all_sources_failed is False


def test_expired_online_deals_dropped(tmp_path):
    expired = Deal("lidl", "Vorbei", 1.0, date(2026, 11, 1), date(2026, 11, 19), "aktionspreis")
    a = FakeScraper("marktguru", {"milch": [_deal("Aktuell"), expired]})
    r = _load(tmp_path, ["milch"], [a])
    assert [d.product_name for d in r.terms["milch"].deals] == ["Aktuell"]
    assert [d.product_name for d in r.online_deals] == ["Aktuell"]
