# Exclusion Filter for Fuzzy Search Results

## Problem

Fuzzy/substring matching on keywords like "butter" returns unrelated products such as "Buttermilch" or "Butter Milch". Users need per-keyword exclusion lists to suppress these false positives.

## Design

### Config file: `config/exclusions.txt`

New file, separate from `products.txt` (exclusions are stable; the product watchlist changes frequently).

Format: one line per keyword, colon-separated, exclusion terms as quoted strings.

```
butter: "buttermilch", "butter milch"
hähnchen: "hähnchensuppe"
```

Rules:
- Keyword must match a term in `products.txt` (case-insensitive)
- Quoted strings support multi-word exclusion terms
- Lines starting with `#` are comments
- Missing file or missing keyword entry = no exclusions (graceful degradation)

### `config.py` — `load_exclusions()`

New function returns `dict[str, list[str]]` mapping keyword → list of lowercase exclusion substrings.

```python
import re

def load_exclusions() -> dict[str, list[str]]:
    path = _CONFIG_DIR / "exclusions.txt"
    if not path.exists():
        return {}
    result: dict[str, list[str]] = {}
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        keyword, _, rest = line.partition(":")
        result[keyword.strip().lower()] = [t.lower() for t in re.findall(r'"([^"]+)"', rest)]
    return result
```

### `matcher.py` — exclusion logic

`match_deals` gains optional `exclusions: dict[str, list[str]] | None = None` parameter. New `_is_excluded` helper checks case-insensitive substring match against `product_name` and `brand`.

The match loop iterates keywords in order; the first keyword that matches AND does not exclude the deal wins. `break` after first winning keyword prevents double-counting.

```python
def match_deals(deals, keywords, threshold=70, exclusions=None):
    exclusions = exclusions or {}
    seen_ids: set[str] = set()
    matched: list[Deal] = []
    for deal in deals:
        if deal.id in seen_ids:
            continue
        for keyword in keywords:
            if _matches(deal, [keyword], threshold):
                if not _is_excluded(deal, exclusions.get(keyword, [])):
                    matched.append(deal)
                    seen_ids.add(deal.id)
                break  # first matching keyword is authoritative
    return matched

def _is_excluded(deal: Deal, terms: list[str]) -> bool:
    haystack = " ".join(filter(None, [deal.product_name, deal.brand])).lower()
    return any(t in haystack for t in terms)
```

Exclusion matching: case-insensitive substring (not fuzzy). Applies to both `product_name` and `brand`.

### `scraper.py`

Import `load_exclusions`, load it, pass to `match_deals`:

```python
exclusions = load_exclusions()
matched = match_deals(all_deals, products, threshold=settings["matching"]["threshold"], exclusions=exclusions)
```

## Files Changed

| File | Change |
|------|--------|
| `config/exclusions.txt` | New file (user-managed) |
| `config.py` | Add `load_exclusions()`, import `re` |
| `matcher.py` | Add `exclusions` param, `_is_excluded()`, restructure loop |
| `scraper.py` | Import and pass exclusions |
| `tests/test_matcher.py` | 5 new test cases |

## Tests

- `test_exclusion_removes_buttermilch` — excluded product filtered, non-excluded passes
- `test_multiword_exclusion` — quoted multi-word term matches correctly
- `test_exclusion_on_brand` — exclusion checks brand field
- `test_exclusion_only_applies_to_its_keyword` — exclusion scoped to keyword
- `test_no_exclusions_no_change` — backward-compatible default behavior
