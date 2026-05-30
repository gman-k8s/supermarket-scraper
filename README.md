# supermarket-scraper

Scrapes German supermarket deal sites (marktguru.de, aktionspreis.de) for products on your watchlist and prints new offers to stdout. Skips already-seen deals via a local cache with TTL.

## Setup

```bash
bash setup-venv.sh
```

Requires Python 3.10+ and [uv](https://github.com/astral-sh/uv).

## Usage

```bash
.venv/bin/python scraper.py            # print new deals since last run
.venv/bin/python scraper.py --force    # print all matching deals, ignore cache
.venv/bin/python scraper.py --dry-run  # print without writing cache or results.json
```

Output is German-formatted to stdout. Results are also written to `output/results.json`.

## Configuration

| File | Purpose |
|------|---------|
| `config/products.txt` | One keyword per line — deals are matched against these (fuzzy, case-insensitive) |
| `config/supermarkets.txt` | One store name per line — filters results to these chains |
| `config/settings.toml` | Zip code, match threshold, network timeouts, cache TTL |

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
```

## API Discovery (required before first run)

The scrapers use placeholder API endpoints. Before running against live data, discover the real endpoints:

1. Open marktguru.de in a browser, open DevTools → Network tab
2. Filter for XHR/Fetch requests, find the search API call
3. Update `_BASE_URL` and `_SEARCH_PATH` constants at the top of `scrapers/marktguru.py`
4. Repeat for aktionspreis.de → `scrapers/aktionspreis.py`
5. Replace `tests/fixtures/` files with real API response samples

## Testing

```bash
.venv/bin/python -m pytest
```

47 tests, 2 skipped (live network — run with `-m live` when real endpoints are configured).
