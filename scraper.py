#!/usr/bin/env python3
import os as _os, sys as _sys
_venv_py = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".venv", "bin", "python")
if not _os.path.exists(_venv_py):
    _sys.exit("Error: .venv not found. Run: python -m venv .venv && pip install -r requirements.txt")
if _os.path.realpath(_sys.executable) != _os.path.realpath(_venv_py):
    _os.execv(_venv_py, [_venv_py] + _sys.argv)
del _venv_py, _os, _sys

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import formatter
from cache import Cache
from config import load_exclusions, load_products, load_settings, load_supermarkets
from deal_loader import load_deals
from matcher import match_deals
from models import Deal
from price_db import PriceDB
from scrapers.aktionspreis import AktionsPreisScraper
from scrapers.marktguru import MarktguruScraper

_OUTPUT_DIR = Path(__file__).parent / "output"
_CACHE_FILE = _OUTPUT_DIR / "cache.json"
_RESULTS_FILE = _OUTPUT_DIR / "results.json"
_PRICE_DB_FILE = _OUTPUT_DIR / "price_history.db"
_DEALS_DIR = _OUTPUT_DIR / "deals"
_DEFAULT_MAX_AGE_DAYS = 7


def _parse_terms(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [t.strip().lower() for t in raw.split(",") if t.strip()]


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def main() -> None:
    parser = argparse.ArgumentParser(description="German supermarket bargain scraper")
    parser.add_argument("--force", action="store_true",
                        help="Reload all terms online and report all matches, ignore seen-cache")
    parser.add_argument("--all", action="store_true",
                        help="Report all matches, ignore seen-cache (uses text cache)")
    parser.add_argument("--terms", help="Extra comma-separated search terms, merged with products.txt")
    parser.add_argument("--json", action="store_true",
                        help="Print all deals per term as JSON (no matching, no seen-cache)")
    parser.add_argument("--dry-run", action="store_true", help="Print matches, skip cache/file writes")
    parser.add_argument("--deadline", type=float, default=None,
                        help="Stop fetching online after N seconds; remaining terms come from cache (0 = cache only)")
    args = parser.parse_args()

    settings = load_settings()
    products = load_products()
    exclusions = load_exclusions()
    supermarkets = load_supermarkets()
    net = settings["network"]
    scrape = settings["scraping"]
    max_age = settings.get("cache", {}).get("deals_max_age_days", _DEFAULT_MAX_AGE_DAYS)

    terms = _dedupe(products + _parse_terms(args.terms))
    scrapers = [
        cls(stores=supermarkets, products=[], timeout=net["timeout_seconds"],
            retries=net["retries"], zip_code=scrape["zip_code"])
        for cls in (MarktguruScraper, AktionsPreisScraper)
    ]
    now = datetime.now()
    result = load_deals(terms, scrapers, _DEALS_DIR, force=args.force, max_age_days=max_age,
                        write_cache=not args.dry_run, now=now, deadline=args.deadline)

    for w in result.warnings:
        print(f"Warnung: {w}", file=sys.stderr)
    if result.skipped:
        print(f"Warnung: Zeitlimit erreicht, nicht geladen: {', '.join(result.skipped)}", file=sys.stderr)
    if result.all_sources_failed:
        print("Fehler: Alle Quellen nicht erreichbar.", file=sys.stderr)
        sys.exit(1)

    if not args.dry_run and result.online_deals:
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        PriceDB(_PRICE_DB_FILE).save_all(result.online_deals)

    if args.json:
        payload = {
            "generated_at": now.replace(microsecond=0).isoformat(),
            "terms": {
                term: {
                    "fetched": tr.fetched.replace(microsecond=0).isoformat(),
                    "from_cache": tr.from_cache,
                    "deals": [d.to_dict() for d in tr.deals],
                }
                for term, tr in result.terms.items()
            },
            "warnings": result.warnings,
            "skipped": result.skipped,
        }
        json.dump(payload, sys.stdout, ensure_ascii=False)
        print()
        return

    all_deals: list[Deal] = list({d.id: d for tr in result.terms.values() for d in tr.deals}.values())
    matched = match_deals(all_deals, terms, threshold=settings["matching"]["threshold"], exclusions=exclusions)

    cache = Cache(cache_file=_CACHE_FILE, ttl_days=settings["cache"]["ttl_days"])
    cache.load()
    cache.expire()

    truly_new = [d for d in matched if not cache.contains(d.id)]
    display_deals = matched if (args.force or args.all) else truly_new

    for line in formatter.format_stdout_lines(display_deals, products):
        print(line)

    if not args.dry_run:
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        formatter.write_results_json(display_deals, _RESULTS_FILE)
        cache.add_all([d.id for d in display_deals])
        cache.save()


if __name__ == "__main__":
    main()
