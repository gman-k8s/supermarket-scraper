"""Load deals per search term, using the text cache when fresh."""
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

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
    skipped: list[str] = field(default_factory=list)  # deadline hit, no cache file


def load_deals(
    terms: list[str],
    scrapers: list[BaseScraper],
    cache_dir: Path,
    *,
    force: bool,
    max_age_days: int,
    write_cache: bool,
    now: datetime,
    deadline: float | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> LoadResult:
    """deadline: seconds after which no further term is fetched online (0 = cache only)."""
    result = LoadResult(terms={}, warnings=[], online_deals=[], all_sources_failed=False)
    succeeded_sources: set[str] = set()
    fetched_any = False
    unrecovered_terms = 0  # online fetch fully failed and no cache file to fall back on
    start = clock()

    for term in terms:
        cached = read_term(cache_dir, term, now.date())
        if not force and cached is not None and is_fresh(cached, now, max_age_days):
            result.terms[term] = TermResult(cached.deals, cached.fetched, from_cache=True)
            continue

        if deadline is not None and clock() - start >= deadline:
            if cached is not None:
                result.terms[term] = TermResult(cached.deals, cached.fetched, from_cache=True)
            else:
                result.skipped.append(term)
            continue

        fetched_any = True
        deals: list[Deal] = []
        ok_sources: list[str] = []
        failed_sources: list[str] = []
        for s in scrapers:
            s.products = [term]
            try:
                deals.extend(d for d in s.fetch() if d.valid_to >= now.date())
                ok_sources.append(s.name)
                succeeded_sources.add(s.name)
            except ScraperError as exc:
                failed_sources.append(s.name)
                result.warnings.append(f"{s.name} ({term}): {exc}")

        if not ok_sources:
            if cached is not None:
                result.warnings.append(f"{term}: verwende zwischengespeicherte Angebote vom {cached.fetched:%d.%m.}")
                result.terms[term] = TermResult(cached.deals, cached.fetched, from_cache=True)
            else:
                unrecovered_terms += 1
                result.terms[term] = TermResult([], now, from_cache=False)
            continue

        result.online_deals.extend(deals)
        if failed_sources and cached is not None:
            # keep the failed sources' still-valid deals from the old file
            merged = deals + [d for d in cached.deals if d.source in failed_sources]
            result.terms[term] = TermResult(merged, now, from_cache=False)
            if write_cache:
                write_term(cache_dir, term, merged, ok_sources + failed_sources, now)
            continue

        result.terms[term] = TermResult(deals, now, from_cache=False)
        if write_cache and not failed_sources:
            write_term(cache_dir, term, deals, ok_sources, now)

    result.all_sources_failed = fetched_any and not succeeded_sources and unrecovered_terms > 0
    return result
