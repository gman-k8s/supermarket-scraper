# supermarket-scraper

Scrapes German supermarket deal sites (marktguru.de, aktionspreis.de) for products on your watchlist and prints new offers to stdout. Skips already-seen deals via a local cache with TTL.

## Setup

```bash
bash setup-venv.sh
```

Requires Python 3.10+ and [uv](https://github.com/astral-sh/uv). The script creates `.venv`, installs runtime and dev dependencies, and copies any missing config files from `config.example/` into `config/` (existing files are never overwritten).

## Usage

```bash
.venv/bin/python scraper.py                       # print new deals since last run
.venv/bin/python scraper.py --all                 # print all matching deals (from text cache)
.venv/bin/python scraper.py --force               # reload everything online, print all matching deals
.venv/bin/python scraper.py --terms "kaffee,eier" # search extra terms in addition to products.txt
.venv/bin/python scraper.py --json                # all deals per term as JSON (no matching, no seen-cache)
.venv/bin/python scraper.py --dry-run             # don't write any cache, results.json or price DB
.venv/bin/python scraper.py --deadline 30         # stop fetching online after 30 s, rest from cache (0 = cache only)
```

Deals are cached per search term in `output/deals/<term>.txt` (header + TSV). By default a term is read from
that file; it is reloaded online only if missing, older than `cache.deals_max_age_days` (default 7), or with
`--force`. A file is only written when both sources answered for that term.

Output is German-formatted to stdout. Results are also written to `output/results.json`, and every scraped deal is recorded in `output/price_history.db` (SQLite).

## Configuration

`config/` is gitignored so your watchlist stays local. Templates live in `config.example/`.

| File | Purpose |
|------|---------|
| `config/products.txt` | One keyword per line — deals are matched against these (fuzzy, case-insensitive) |
| `config/supermarkets.txt` | One store name per line — filters results to these chains |
| `config/settings.toml` | Zip code, match threshold, network timeouts, cache TTL |
| `config/exclusions.txt` | Optional per-keyword exclusion terms, e.g. `butter: "buttermilch", "vegane"` |

Example `products.txt`:
```
butter
hähnchen
milch
```

Example `settings.toml`:
```toml
[scraping]
zip_code = "10115"

[matching]
threshold = 70        # 0–100 fuzzy match score

[network]
timeout_seconds = 10
retries = 2

[cache]
ttl_days = 14
deals_max_age_days = 7
```

## Data sources

- **marktguru.de** — public JSON API (`scrapers/marktguru.py`)
- **aktionspreis.de** — HTML search pages plus JSON-LD on offer pages (`scrapers/aktionspreis.py`)

If a site changes its API or markup, update the scraper and refresh the matching sample in `tests/fixtures/`.

## Testing

```bash
.venv/bin/python -m pytest
```

Live network tests are skipped by default. Run them with:

```bash
LIVE_TESTS=1 .venv/bin/python -m pytest tests/test_scrapers.py
```
