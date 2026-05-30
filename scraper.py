#!/usr/bin/env python3
import os as _os, sys as _sys
_venv_py = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".venv", "bin", "python")
if not _os.path.exists(_venv_py):
    _sys.exit("Error: .venv not found. Run: python -m venv .venv && pip install -r requirements.txt")
if _os.path.realpath(_sys.executable) != _os.path.realpath(_venv_py):
    _os.execv(_venv_py, [_venv_py] + _sys.argv)
del _venv_py, _os, _sys

import argparse
import sys
from pathlib import Path

import formatter
from cache import Cache
from config import load_exclusions, load_products, load_settings, load_supermarkets
from matcher import match_deals
from models import Deal
from scrapers.aktionspreis import AktionsPreisScraper
from scrapers.base import ScraperError
from scrapers.marktguru import MarktguruScraper

_OUTPUT_DIR = Path(__file__).parent / "output"
_CACHE_FILE = _OUTPUT_DIR / "cache.json"
_RESULTS_FILE = _OUTPUT_DIR / "results.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="German supermarket bargain scraper")
    parser.add_argument("--force", action="store_true", help="Report all matches, ignore cache")
    parser.add_argument("--dry-run", action="store_true", help="Print matches, skip cache/file writes")
    args = parser.parse_args()

    settings = load_settings()
    products = load_products()
    exclusions = load_exclusions()
    supermarkets = load_supermarkets()
    net = settings["network"]
    scrape = settings["scraping"]

    all_deals: list[Deal] = []
    errors = 0

    for cls in (MarktguruScraper, AktionsPreisScraper):
        try:
            s = cls(
                stores=supermarkets,
                products=products,
                timeout=net["timeout_seconds"],
                retries=net["retries"],
                zip_code=scrape["zip_code"],
            )
            all_deals.extend(s.fetch())
        except ScraperError as exc:
            print(f"Warnung: {exc}", file=sys.stderr)
            errors += 1

    if errors >= 2:
        print("Fehler: Alle Quellen nicht erreichbar.", file=sys.stderr)
        sys.exit(1)

    matched = match_deals(all_deals, products, threshold=settings["matching"]["threshold"], exclusions=exclusions)

    cache = Cache(cache_file=_CACHE_FILE, ttl_days=settings["cache"]["ttl_days"])
    cache.load()
    cache.expire()

    truly_new = [d for d in matched if not cache.contains(d.id)]
    display_deals = matched if args.force else truly_new

    for line in formatter.format_stdout_lines(display_deals, products):
        print(line)

    if not args.dry_run:
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        formatter.write_results_json(display_deals, _RESULTS_FILE)
        cache.add_all([d.id for d in display_deals])
        cache.save()


if __name__ == "__main__":
    main()
