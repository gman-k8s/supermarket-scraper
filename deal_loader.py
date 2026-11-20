"""Load deals per search term, using the text cache when fresh."""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from deal_cache import is_fresh, read_term, write_term
from models import Deal
from scrapers.base import BaseScraper, ScraperError


@dataclass
class TermResult:
    deals: list[Deal]
    fetched: datetime
    from_cache: bool


@dataclass
class LoadResult:
    terms: dict[str, TermResult]
    warnings: list[str]
    online_deals: list[Deal]
    all_sources_failed: bool


def load_deals(
    terms: list[str],
    scrapers: list[BaseScraper],
    cache_dir: Path,
    *,
    force: bool,
    max_age_days: int,
    write_cache: bool,
    now: datetime,
) -> LoadResult:
    result = LoadResult(terms={}, warnings=[], online_deals=[], all_sources_failed=False)
    succeeded_sources: set[str] = set()
    fetched_any = False

    for term in terms:
        cached = read_term(cache_dir, term, now.date())
        if not force and cached is not None and is_fresh(cached, now, max_age_days):
            result.terms[term] = TermResult(cached.deals, cached.fetched, from_cache=True)
            continue

        fetched_any = True
        deals: list[Deal] = []
        ok_sources: list[str] = []
        for s in scrapers:
            s.products = [term]
            try:
                deals.extend(s.fetch())
                ok_sources.append(s.name)
                succeeded_sources.add(s.name)
            except ScraperError as exc:
                result.warnings.append(f"{s.name} ({term}): {exc}")

        if not ok_sources and cached is not None:
            result.warnings.append(f"{term}: verwende zwischengespeicherte Angebote vom {cached.fetched:%d.%m.}")
            result.terms[term] = TermResult(cached.deals, cached.fetched, from_cache=True)
            continue

        result.terms[term] = TermResult(deals, now, from_cache=False)
        result.online_deals.extend(deals)
        if write_cache and len(ok_sources) == len(scrapers):
            write_term(cache_dir, term, deals, ok_sources, now)

    result.all_sources_failed = fetched_any and not succeeded_sources
    return result
