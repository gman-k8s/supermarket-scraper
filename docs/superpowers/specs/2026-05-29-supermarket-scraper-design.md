# Supermarket Bargain Scraper — Design Spec

**Date:** 2026-05-29  
**Status:** Approved

## Overview

Python CLI tool that scrapes weekly bargain prospects from German supermarket deal aggregator sites (marktguru.de, aktionspreis.de), matches results against a configurable product watchlist using fuzzy matching, and outputs German-language summaries + structured JSON for Home Assistant automation.

## Goals

- Monitor configurable supermarkets (default: Lidl, Aldi, Netto) for bargains on watchlisted products
- Run unattended via HA cron (Mondays + Thursdays when new prospects publish)
- Output German-language stdout for logging + JSON for HA Telegram automation
- Skip already-reported deals via cache; override with `--force`

## Non-Goals

- No web UI
- No direct Telegram integration (HA handles that)
- No price history or trend tracking

## File Structure

```
scraper.py              # entry point, CLI args, orchestration
setup-venv.sh           # creates .venv, installs deps via uv
requirements.txt        # runtime deps
requirements-dev.txt    # pytest etc.
config/
  products.txt          # one keyword per line: butter, hähnchen, ...
  supermarkets.txt      # one store per line: lidl, aldi, netto, ...
  settings.toml         # fuzzy match threshold, request timeouts, cache TTL
scrapers/
  __init__.py
  base.py               # abstract BaseScraper → list[Deal]
  marktguru.py          # marktguru.de internal JSON API
  aktionspreis.py       # aktionspreis.de internal JSON API
matcher.py              # rapidfuzz keyword → deal matching
cache.py                # seen-deal IDs, 14-day expiry, output/cache.json
formatter.py            # German stdout + output/results.json
tests/
  fixtures/             # mock API response JSON files
  test_matcher.py
  test_cache.py
  test_formatter.py
  test_scrapers.py      # live network tests, skipped by default
output/                 # runtime dir, gitignored
  results.json
  cache.json
.gitignore
```

## Data Model

```python
@dataclass
class Deal:
    id: str               # sha256(source+store+product_name+valid_from)[:12]
    store: str            # "lidl" | "aldi" | "netto" | ...
    brand: str | None     # brand name if available from API
    product_name: str     # product title from API
    price: float          # current sale price
    original_price: float | None
    discount_pct: float | None
    valid_from: date
    valid_to: date
    source: str           # "marktguru" | "aktionspreis"
```

## Scraping Strategy

**Primary:** Reverse-engineered internal JSON APIs on both sites (XHR endpoints). Each scraper queries by supermarket + (optionally) keyword and returns `list[Deal]`.

**Fallback:** If an API endpoint breaks, the relevant scraper raises `ScraperError` which is caught by the orchestrator — the other scraper continues. Both failing → exit code 1.

**Network:** 10s timeout, 2 retries with exponential backoff (1s, 2s). `requests` library.

## Fuzzy Matching

Library: `rapidfuzz`

For each deal, check `f"{brand} {product_name}"` against every keyword in `products.txt`:
- Substring match (keyword inside product string): always matches
- `rapidfuzz.fuzz.partial_ratio` ≥ threshold (default 70, configurable in `settings.toml`)
- Case-insensitive, umlaut-aware

## Cache

File: `output/cache.json` — dict of `{deal_id: iso_timestamp_first_seen}`

On each run:
1. Load cache, drop entries older than 14 days
2. New deals = matched deals whose ID not in cache
3. Report new deals only
4. Write new IDs into cache

`--force` skips step 2 and 3 filter (reports all matches, still updates cache).

## CLI

```
python scraper.py              # normal run
python scraper.py --force      # ignore cache, report all current matches
python scraper.py --dry-run    # print matches, skip cache update + skip results.json write
```

No other args. Config lives in `config/`.

**settings.toml** (with defaults):
```toml
[matching]
threshold = 70          # rapidfuzz partial_ratio minimum score

[network]
timeout_seconds = 10
retries = 2

[cache]
ttl_days = 14
```

## Output

**stdout (German, human-readable):**
```
[LIDL] Metzgerfrisch Hähnchenfilet 500g — 2,49€ (statt 3,99€, -38%) | gültig 02.06–07.06
[ALDI] Milsani Süßrahmbutter 250g — 1,29€ (statt 1,79€, -28%) | gültig 02.06–07.06
```
If no new deals: `Keine neuen Angebote gefunden.`

**output/results.json** (locale-neutral, HA consumes):
```json
[
  {
    "id": "a1b2c3d4e5f6",
    "store": "lidl",
    "brand": "Metzgerfrisch",
    "product_name": "Hähnchenfilet 500g",
    "price": 2.49,
    "original_price": 3.99,
    "discount_pct": 38.0,
    "valid_from": "2026-06-02",
    "valid_to": "2026-06-07",
    "source": "marktguru"
  }
]
```

`results.json` always reflects the current run (all new matches). Empty array `[]` if none.

## Setup

`setup-venv.sh`:
```bash
#!/usr/bin/env bash
set -e
uv venv .venv
uv pip install -r requirements.txt
```

HA invokes: `.venv/bin/python scraper.py`

## Dependencies

**Runtime (`requirements.txt`):**
```
requests
rapidfuzz
```

**Dev (`requirements-dev.txt`):**
```
pytest
pytest-cov
```

Python 3.10+ required.

## Error Handling

| Scenario | Behavior |
|---|---|
| One scraper fails | Log to stderr, continue with other scraper, exit 0 |
| Both scrapers fail | Log to stderr, exit 1 (HA detects failure) |
| Network timeout | 2 retries, then raise `ScraperError` |
| Malformed API response | Log warning, skip that source |
| Missing config files | Exit 1 with clear error message |

## Testing

- Unit tests: matcher (fuzzy logic edge cases), cache (expiry, dedup), formatter (German string output)
- Fixture JSONs mock real API responses — no live network in unit tests
- Integration tests: one per scraper, live network, skipped unless `LIVE_TESTS=1` env var set

## .gitignore

```
.venv/
output/
__pycache__/
*.pyc
.pytest_cache/
```
