# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
bash setup-venv.sh                              # .venv via uv, dev deps, seed config/ from config.example/

.venv/bin/python scraper.py                     # print deals not seen since last run
.venv/bin/python scraper.py --all               # print all matches from text cache, ignore seen-cache
.venv/bin/python scraper.py --force             # reload online + print all matches
.venv/bin/python scraper.py --terms "a,b" --json  # extra terms; JSON of all deals per term (used by todoist-cli)
.venv/bin/python scraper.py --dry-run           # don't write caches, results.json or price DB

.venv/bin/python -m pytest                                  # all tests
.venv/bin/python -m pytest tests/test_matcher.py::test_name # single test
LIVE_TESTS=1 .venv/bin/python -m pytest tests/test_scrapers.py  # include live network tests
```

`scraper.py` re-execs itself under `.venv/bin/python` if started with another interpreter, and exits if `.venv` is missing.

## Architecture

Pipeline in `scraper.py:main()`:

1. **Config** (`config.py`) — reads from `config/` (gitignored; templates in `config.example/`, copied in by `setup-venv.sh` without overwriting): `products.txt` (keywords), `supermarkets.txt` (store names), `settings.toml` (`scraping.zip_code`, `matching.threshold`, `network.timeout_seconds`/`retries`, `cache.ttl_days`), and optional `exclusions.txt` (`keyword: "term1", "term2"`). All keywords/stores are lowercased.
2. **Scrapers** (`scrapers/`) — each subclasses `BaseScraper` and implements `fetch() -> list[Deal]`. Both search per product keyword and filter to configured stores by substring-matching the lowercased store name against the site's store/advertiser name. Network failures raise `ScraperError`; main tolerates one source failing and exits 1 only if both fail.
   - `marktguru.py` — JSON API at `api.marktguru.de`: fetches an `x-clientkey` from `/configurations/web` using a static `X-ApiKey`, then calls `/offers/search`.
   - `aktionspreis.py` — HTML scraping: regex-extracts `/angebote/<slug>` links from search results, then parses JSON-LD (`Product` with `AggregateOffer` + `SaleEvent`s) on each offer page. One `Deal` per matching `SaleEvent`.
3. **Matching** (`matcher.py`) — a deal matches a keyword on substring or `rapidfuzz.partial_ratio >= threshold` over `product_name + brand`. Per-keyword exclusion terms (substring) veto that keyword only; the first non-excluded keyword wins.
3a. **Loading** (`deal_loader.py` + `deal_cache.py`) — terms = `products.txt` ∪ `--terms`. Per term: read `output/deals/<slug>.txt` if fresher than `cache.deals_max_age_days` (default 7), else fetch online (scrapers reused with `products=[term]`; marktguru client key memoized). File written only if both sources succeeded; on total failure an old file is used. Expired deals (`valid_to < today`) dropped on read. `--deadline N` stops online fetching after N seconds (0 = cache only): remaining terms use any cache file, terms without one go to `skipped`. `--json` stops here and prints `{generated_at, terms: {term: {fetched, from_cache, deals}}, warnings, skipped}`.
4. **Cache** (`cache.py`) — `output/cache.json` maps `Deal.id` → timestamp, expired after `ttl_days`. Only unseen deals are shown unless `--force` or `--all`.
5. **Output** — `formatter.py` prints German-formatted lines grouped by store plus a per-store keyword coverage summary (stdout text is German: "Keine neuen Angebote gefunden.", "Warnung:", etc.), and writes `output/results.json`. `price_db.py` upserts **all deals fetched online in this run** (not only matches) into SQLite `output/price_history.db`.

`Deal.id` (`models.py`) is a 12-char sha256 of `source + store + product_name + valid_from` — changing any of those fields' derivation invalidates the cache and the price DB primary key. `discount_pct` is computed from `original_price` when not given.

## Testing notes

- `tests/test_scraper.py` redirects `scraper._DEALS_DIR` to `tmp_path` via `_reload_and_main()`; use it for new CLI tests.
- Scraper tests use JSON fixtures in `tests/fixtures/`; network calls are mocked.
- `tests/test_scraper.py` patches scrapers, cache and file writes, then `importlib.reload(scraper)` and calls `main()`.
- `tests/test_config.py` partly reads the real `config/` files and asserts default values (stores lidl/aldi/netto, threshold 70, zip 10115, etc.), so it fails if `config/` is missing or customized; `config.example/` holds those defaults.

## Docs

Design specs and implementation plans live in `docs/superpowers/specs/` and `docs/superpowers/plans/`.
