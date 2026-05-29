import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from cache import Cache


@pytest.fixture
def tmp_cache(tmp_path) -> Cache:
    return Cache(cache_file=tmp_path / "cache.json", ttl_days=14)


def test_new_cache_is_empty(tmp_cache):
    tmp_cache.load()
    assert not tmp_cache.contains("abc123")


def test_add_and_contains(tmp_cache):
    tmp_cache.load()
    tmp_cache.add("abc123")
    assert tmp_cache.contains("abc123")


def test_unknown_id_not_contained(tmp_cache):
    tmp_cache.load()
    tmp_cache.add("abc123")
    assert not tmp_cache.contains("xyz999")


def test_save_and_reload(tmp_cache):
    tmp_cache.load()
    tmp_cache.add("abc123")
    tmp_cache.save()
    cache2 = Cache(cache_file=tmp_cache.cache_file, ttl_days=14)
    cache2.load()
    assert cache2.contains("abc123")


def test_expire_removes_old_entries(tmp_cache):
    tmp_cache.load()
    old_ts = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
    tmp_cache._data["old_deal"] = old_ts
    tmp_cache.expire()
    assert not tmp_cache.contains("old_deal")


def test_expire_keeps_recent_entries(tmp_cache):
    tmp_cache.load()
    tmp_cache.add("new_deal")
    tmp_cache.expire()
    assert tmp_cache.contains("new_deal")


def test_add_all(tmp_cache):
    tmp_cache.load()
    tmp_cache.add_all(["a1", "b2", "c3"])
    assert all(tmp_cache.contains(x) for x in ["a1", "b2", "c3"])


def test_missing_cache_file_loads_empty(tmp_path):
    cache = Cache(cache_file=tmp_path / "nonexistent.json", ttl_days=14)
    cache.load()
    assert not cache.contains("anything")
