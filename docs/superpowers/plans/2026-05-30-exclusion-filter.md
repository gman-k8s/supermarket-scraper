# Exclusion Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-keyword exclusion lists that strip false-positive fuzzy matches (e.g. "Buttermilch" when searching "butter") from results.

**Architecture:** New `config/exclusions.txt` maps keywords to quoted exclusion substrings. `config.py` parses it. `matcher.py` checks exclusions inside the keyword loop — first keyword that matches AND doesn't exclude the deal wins. `scraper.py` wires it together.

**Tech Stack:** Python 3.11+, rapidfuzz (existing), pytest (existing)

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `config/exclusions.txt` | Create | User-managed exclusion config |
| `config.py` | Modify | Parse exclusions.txt → dict |
| `matcher.py` | Modify | Apply exclusions inside match loop |
| `scraper.py` | Modify | Load exclusions, pass to match_deals |
| `tests/test_matcher.py` | Modify | 5 new exclusion test cases |

---

### Task 1: Create `config/exclusions.txt`

**Files:**
- Create: `config/exclusions.txt`

- [ ] **Step 1: Create the file with example content**

```
# Per-keyword exclusion list.
# Format: keyword: "term1", "term2"
# Matching is case-insensitive substring against product_name and brand.
butter: "buttermilch", "butter milch"
```

- [ ] **Step 2: Commit**

```bash
git add config/exclusions.txt
git commit -m "config: add exclusions.txt with butter example"
```

---

### Task 2: Add `load_exclusions()` to `config.py`

**Files:**
- Modify: `config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Open `tests/test_config.py` and add at the bottom:

```python
from config import load_exclusions

def test_load_exclusions_returns_dict(tmp_path, monkeypatch):
    excl = tmp_path / "exclusions.txt"
    excl.write_text('butter: "buttermilch", "butter milch"\n# comment\nhähnchen: "hähnchensuppe"\n', encoding="utf-8")
    import config as cfg
    monkeypatch.setattr(cfg, "_CONFIG_DIR", tmp_path)
    result = load_exclusions()
    assert result == {
        "butter": ["buttermilch", "butter milch"],
        "hähnchen": ["hähnchensuppe"],
    }

def test_load_exclusions_missing_file_returns_empty(tmp_path, monkeypatch):
    import config as cfg
    monkeypatch.setattr(cfg, "_CONFIG_DIR", tmp_path)
    assert load_exclusions() == {}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/agarbe/git/supermarket-scraper && .venv/bin/pytest tests/test_config.py::test_load_exclusions_returns_dict tests/test_config.py::test_load_exclusions_missing_file_returns_empty -v
```

Expected: FAIL with `ImportError: cannot import name 'load_exclusions'`

- [ ] **Step 3: Implement `load_exclusions()` in `config.py`**

Add `import re` at the top of `config.py` (after existing imports), then add this function at the bottom:

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

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_config.py::test_load_exclusions_returns_dict tests/test_config.py::test_load_exclusions_missing_file_returns_empty -v
```

Expected: 2 passed

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
.venv/bin/pytest tests/ -v
```

Expected: all existing tests pass

- [ ] **Step 6: Commit**

```bash
git add config.py tests/test_config.py
git commit -m "feat: add load_exclusions() to config.py"
```

---

### Task 3: Add exclusion logic to `matcher.py`

**Files:**
- Modify: `matcher.py`
- Test: `tests/test_matcher.py`

- [ ] **Step 1: Write the failing tests**

Open `tests/test_matcher.py` and add at the bottom:

```python
def test_exclusion_removes_buttermilch():
    deals = [_deal("Buttermilch 500ml"), _deal("Butter 250g")]
    result = match_deals(deals, ["butter"], threshold=70, exclusions={"butter": ["buttermilch"]})
    assert len(result) == 1
    assert result[0].product_name == "Butter 250g"


def test_multiword_exclusion():
    deals = [_deal("Butter Milch 1L"), _deal("Butter 250g")]
    result = match_deals(deals, ["butter"], threshold=70, exclusions={"butter": ["butter milch"]})
    assert len(result) == 1
    assert result[0].product_name == "Butter 250g"


def test_exclusion_on_brand():
    deals = [_deal("Frischeprodukt 500ml", brand="Buttermilch Brand")]
    result = match_deals(deals, ["butter"], threshold=70, exclusions={"butter": ["buttermilch"]})
    assert len(result) == 0


def test_exclusion_only_applies_to_its_keyword():
    deals = [_deal("Buttermilch 500ml")]
    result = match_deals(deals, ["milch"], threshold=70, exclusions={"butter": ["buttermilch"]})
    assert len(result) == 1


def test_no_exclusions_no_change():
    deals = [_deal("Buttermilch 500ml")]
    result = match_deals(deals, ["butter"], threshold=70)
    assert len(result) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_matcher.py::test_exclusion_removes_buttermilch tests/test_matcher.py::test_multiword_exclusion tests/test_matcher.py::test_exclusion_on_brand tests/test_matcher.py::test_exclusion_only_applies_to_its_keyword tests/test_matcher.py::test_no_exclusions_no_change -v
```

Expected: FAIL — `match_deals` does not accept `exclusions` kwarg yet

- [ ] **Step 3: Rewrite `matcher.py`**

Replace the full contents of `matcher.py` with:

```python
from rapidfuzz import fuzz
from models import Deal


def match_deals(
    deals: list[Deal],
    keywords: list[str],
    threshold: int = 70,
    exclusions: dict[str, list[str]] | None = None,
) -> list[Deal]:
    if not keywords or not deals:
        return []
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


def _matches(deal: Deal, keywords: list[str], threshold: int) -> bool:
    parts = [deal.product_name]
    if deal.brand:
        parts.append(deal.brand)
    haystack = " ".join(parts).lower()
    for keyword in keywords:
        needle = keyword.lower()
        if needle in haystack:
            return True
        if fuzz.partial_ratio(needle, haystack) >= threshold:
            return True
    return False


def _is_excluded(deal: Deal, terms: list[str]) -> bool:
    haystack = " ".join(filter(None, [deal.product_name, deal.brand])).lower()
    return any(t in haystack for t in terms)
```

- [ ] **Step 4: Run new tests to verify they pass**

```bash
.venv/bin/pytest tests/test_matcher.py::test_exclusion_removes_buttermilch tests/test_matcher.py::test_multiword_exclusion tests/test_matcher.py::test_exclusion_on_brand tests/test_matcher.py::test_exclusion_only_applies_to_its_keyword tests/test_matcher.py::test_no_exclusions_no_change -v
```

Expected: 5 passed

- [ ] **Step 5: Run full matcher test suite to check for regressions**

```bash
.venv/bin/pytest tests/test_matcher.py -v
```

Expected: all tests pass (existing + new)

- [ ] **Step 6: Commit**

```bash
git add matcher.py tests/test_matcher.py
git commit -m "feat: add per-keyword exclusion filter to match_deals"
```

---

### Task 4: Wire exclusions into `scraper.py`

**Files:**
- Modify: `scraper.py`

- [ ] **Step 1: Update import in `scraper.py`**

Find this line:
```python
from config import load_products, load_settings, load_supermarkets
```

Replace with:
```python
from config import load_exclusions, load_products, load_settings, load_supermarkets
```

- [ ] **Step 2: Load exclusions and pass to `match_deals`**

Find this block in `main()`:
```python
    products = load_products()
    supermarkets = load_supermarkets()
```

Replace with:
```python
    products = load_products()
    exclusions = load_exclusions()
    supermarkets = load_supermarkets()
```

Then find:
```python
    matched = match_deals(all_deals, products, threshold=settings["matching"]["threshold"])
```

Replace with:
```python
    matched = match_deals(all_deals, products, threshold=settings["matching"]["threshold"], exclusions=exclusions)
```

- [ ] **Step 3: Run full test suite**

```bash
.venv/bin/pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 4: Smoke test with dry-run**

```bash
.venv/bin/python scraper.py --dry-run
```

Expected: runs without error, output reflects exclusions from `config/exclusions.txt`

- [ ] **Step 5: Commit**

```bash
git add scraper.py
git commit -m "feat: wire exclusion filter into scraper CLI"
```
