# Supermarket Bargain Scraper — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI that scrapes marktguru.de and aktionspreis.de for German supermarket bargains, fuzzy-matches against a product watchlist, caches seen deals, and outputs German summaries + JSON for Home Assistant automation.

**Architecture:** Two isolated scrapers (one per site) each return `list[Deal]`; a matcher filters by fuzzy keyword; a cache skips already-reported deals; a formatter writes German stdout + results.json. The orchestrator `scraper.py` ties them together with `--force` / `--dry-run` flags.

**Tech Stack:** Python 3.10+, uv, requests, rapidfuzz, tomli (3.10 compat), pytest

---

## File Map

| File | Responsibility |
|------|----------------|
| `models.py` | `Deal` dataclass + `to_dict()` |
| `config.py` | Load products.txt, supermarkets.txt, settings.toml |
| `scrapers/__init__.py` | Empty package marker |
| `scrapers/base.py` | Abstract `BaseScraper`, `ScraperError` |
| `scrapers/marktguru.py` | Fetch + parse marktguru.de API |
| `scrapers/aktionspreis.py` | Fetch + parse aktionspreis.de API |
| `matcher.py` | Fuzzy match `list[Deal]` against keyword list |
| `cache.py` | Load/save/expire seen deal IDs (`output/cache.json`) |
| `formatter.py` | German stdout lines + write `output/results.json` |
| `scraper.py` | CLI entry point, orchestration |
| `tests/test_models.py` | Deal ID determinism, to_dict |
| `tests/test_config.py` | Config file loading |
| `tests/test_matcher.py` | Fuzzy logic, umlaut, threshold |
| `tests/test_cache.py` | Load/save/expire/dedup |
| `tests/test_formatter.py` | German format strings, JSON output |
| `tests/test_scrapers.py` | Fixture-based parse tests + live integration |
| `tests/test_scraper.py` | Orchestrator behaviour |

---

## Task 1: Project Scaffolding

**Files:**
- Create: `.gitignore`
- Create: `setup-venv.sh`
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `config/products.txt`
- Create: `config/supermarkets.txt`
- Create: `config/settings.toml`
- Create: `output/.gitkeep`
- Create: `tests/__init__.py`
- Create: `tests/fixtures/.gitkeep`
- Create: `scrapers/__init__.py`

- [ ] **Step 1: Create .gitignore**

```
.venv/
output/
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
dist/
.coverage
```

- [ ] **Step 2: Create setup-venv.sh**

```bash
#!/usr/bin/env bash
set -e
uv venv .venv
uv pip install -r requirements.txt
```

Then: `chmod +x setup-venv.sh`

- [ ] **Step 3: Create requirements.txt**

```
requests
rapidfuzz
tomli; python_version < "3.11"
```

- [ ] **Step 4: Create requirements-dev.txt**

```
-r requirements.txt
pytest
pytest-cov
```

- [ ] **Step 5: Create config/products.txt**

```
butter
hähnchen
milch
joghurt
käse
```

- [ ] **Step 6: Create config/supermarkets.txt**

```
lidl
aldi
netto
```

- [ ] **Step 7: Create config/settings.toml**

```toml
[scraping]
zip_code = "10115"

[matching]
threshold = 70

[network]
timeout_seconds = 10
retries = 2

[cache]
ttl_days = 14
```

- [ ] **Step 8: Create directories and empty init files**

```bash
mkdir -p output tests/fixtures scrapers
touch output/.gitkeep tests/__init__.py tests/fixtures/.gitkeep scrapers/__init__.py
```

- [ ] **Step 9: Bootstrap venv**

```bash
./setup-venv.sh
```

Expected: `.venv/` created, packages installed without error.

- [ ] **Step 10: Commit**

```bash
git add .gitignore setup-venv.sh requirements.txt requirements-dev.txt \
  config/ output/.gitkeep tests/__init__.py tests/fixtures/.gitkeep scrapers/__init__.py
git commit -m "chore: project scaffolding"
```

---

## Task 2: Data Model + Config Loader

**Files:**
- Create: `models.py`
- Create: `config.py`
- Create: `tests/test_models.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing model tests**

```python
# tests/test_models.py
from datetime import date
from models import Deal


def test_deal_id_is_deterministic():
    d1 = Deal("lidl", "Hähnchenfilet 500g", 2.49, date(2026, 6, 2), date(2026, 6, 7), "marktguru")
    d2 = Deal("lidl", "Hähnchenfilet 500g", 2.49, date(2026, 6, 2), date(2026, 6, 7), "marktguru")
    assert d1.id == d2.id


def test_deal_id_differs_for_different_products():
    d1 = Deal("lidl", "Hähnchenfilet 500g", 2.49, date(2026, 6, 2), date(2026, 6, 7), "marktguru")
    d2 = Deal("lidl", "Margarine 500g", 0.99, date(2026, 6, 2), date(2026, 6, 7), "marktguru")
    assert d1.id != d2.id


def test_deal_id_is_12_chars():
    d = Deal("lidl", "Butter 250g", 1.29, date(2026, 6, 2), date(2026, 6, 7), "marktguru")
    assert len(d.id) == 12


def test_deal_to_dict_structure():
    d = Deal(
        "lidl", "Hähnchenfilet 500g", 2.49, date(2026, 6, 2), date(2026, 6, 7), "marktguru",
        brand="Metzgerfrisch", original_price=3.99, discount_pct=38.0,
    )
    result = d.to_dict()
    assert result["store"] == "lidl"
    assert result["brand"] == "Metzgerfrisch"
    assert result["price"] == 2.49
    assert result["original_price"] == 3.99
    assert result["discount_pct"] == 38.0
    assert result["valid_from"] == "2026-06-02"
    assert result["valid_to"] == "2026-06-07"
    assert result["source"] == "marktguru"
    assert len(result["id"]) == 12


def test_deal_optional_fields_default_none():
    d = Deal("aldi", "Milch 1L", 0.89, date(2026, 6, 2), date(2026, 6, 7), "aktionspreis")
    assert d.brand is None
    assert d.original_price is None
    assert d.discount_pct is None
```

- [ ] **Step 2: Run to confirm failure**

```bash
.venv/bin/pytest tests/test_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'models'`

- [ ] **Step 3: Implement models.py**

```python
# models.py
from dataclasses import dataclass, field
from datetime import date
from hashlib import sha256


@dataclass
class Deal:
    store: str
    product_name: str
    price: float
    valid_from: date
    valid_to: date
    source: str
    brand: str | None = None
    original_price: float | None = None
    discount_pct: float | None = None
    id: str = field(init=False)

    def __post_init__(self):
        raw = f"{self.source}{self.store}{self.product_name}{self.valid_from}"
        self.id = sha256(raw.encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "store": self.store,
            "brand": self.brand,
            "product_name": self.product_name,
            "price": self.price,
            "original_price": self.original_price,
            "discount_pct": self.discount_pct,
            "valid_from": self.valid_from.isoformat(),
            "valid_to": self.valid_to.isoformat(),
            "source": self.source,
        }
```

- [ ] **Step 4: Run model tests**

```bash
.venv/bin/pytest tests/test_models.py -v
```

Expected: 5 PASSED

- [ ] **Step 5: Write failing config tests**

```python
# tests/test_config.py
from config import load_products, load_supermarkets, load_settings


def test_load_products_returns_lowercase_list():
    products = load_products()
    assert isinstance(products, list)
    assert len(products) > 0
    assert all(p == p.lower() for p in products)


def test_load_supermarkets_contains_defaults():
    stores = load_supermarkets()
    assert "lidl" in stores
    assert "aldi" in stores
    assert "netto" in stores


def test_load_settings_has_required_keys():
    settings = load_settings()
    assert settings["matching"]["threshold"] == 70
    assert settings["network"]["timeout_seconds"] == 10
    assert settings["network"]["retries"] == 2
    assert settings["cache"]["ttl_days"] == 14
    assert settings["scraping"]["zip_code"] == "10115"
```

- [ ] **Step 6: Run to confirm failure**

```bash
.venv/bin/pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 7: Implement config.py**

```python
# config.py
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

_CONFIG_DIR = Path(__file__).parent / "config"


def load_products() -> list[str]:
    text = (_CONFIG_DIR / "products.txt").read_text("utf-8")
    return [line.strip().lower() for line in text.splitlines() if line.strip()]


def load_supermarkets() -> list[str]:
    text = (_CONFIG_DIR / "supermarkets.txt").read_text("utf-8")
    return [line.strip().lower() for line in text.splitlines() if line.strip()]


def load_settings() -> dict:
    with open(_CONFIG_DIR / "settings.toml", "rb") as f:
        return tomllib.load(f)
```

- [ ] **Step 8: Run config tests**

```bash
.venv/bin/pytest tests/test_config.py -v
```

Expected: 3 PASSED

- [ ] **Step 9: Commit**

```bash
git add models.py config.py tests/test_models.py tests/test_config.py
git commit -m "feat: data model and config loader"
```

---

## Task 3: API Discovery (marktguru.de + aktionspreis.de)

This task produces the fixture files used in scraper tests. Inspect live network traffic — no code is written here, only fixture JSON files.

**Files:**
- Create: `tests/fixtures/marktguru_response.json`
- Create: `tests/fixtures/aktionspreis_response.json`

- [ ] **Step 1: Discover marktguru.de API**

1. Open Chrome/Firefox → DevTools (F12) → **Network** tab → filter **Fetch/XHR**
2. Navigate to `https://www.marktguru.de`
3. Browse or search for any product (e.g. "butter")
4. Find the XHR response that contains deal/offer data with price fields
5. Record: full URL, query params, any required request headers (e.g. `Authorization`, `X-Api-Key`)
6. Right-click the request → **Copy** → **Copy response**
7. Paste 2–3 representative offer objects into `tests/fixtures/marktguru_response.json`

Key fields to identify in the response:
- Array key containing offers (e.g. `results`, `offers`, `data`)
- Offer title / product name field
- Brand field (may be nested object or flat string)
- Current price field (may be nested `{"amount": 2.49}` or flat `2.49`)
- Original / regular price field
- Discount percent field
- Validity date fields (`from`/`to`, `validFrom`/`validUntil`, etc.)
- Store / retailer / company field

- [ ] **Step 2: Discover aktionspreis.de API**

Same process for `https://www.aktionspreis.de`. Save to `tests/fixtures/aktionspreis_response.json`.

- [ ] **Step 3: Create placeholder fixtures if discovery deferred**

If you want to run tests before doing live discovery, use these starter fixtures (update field names after real discovery):

`tests/fixtures/marktguru_response.json`:
```json
{
  "results": [
    {
      "title": "Hähnchenfilet 500g",
      "brand": {"name": "Metzgerfrisch"},
      "price": {"amount": 2.49, "currency": "EUR"},
      "priceNormal": {"amount": 3.99},
      "discount": 38,
      "validity": {
        "from": "2026-06-02T00:00:00",
        "to": "2026-06-07T23:59:59"
      },
      "company": {"name": "Lidl"}
    },
    {
      "title": "Süßrahmbutter 250g",
      "brand": {"name": "Milsani"},
      "price": {"amount": 1.29, "currency": "EUR"},
      "priceNormal": {"amount": 1.79},
      "discount": 28,
      "validity": {
        "from": "2026-06-02T00:00:00",
        "to": "2026-06-07T23:59:59"
      },
      "company": {"name": "Lidl"}
    }
  ]
}
```

`tests/fixtures/aktionspreis_response.json`:
```json
{
  "offers": [
    {
      "id": "ap_001",
      "name": "Grillhähnchen",
      "brand": "GutBio",
      "price": 4.99,
      "regularPrice": 6.99,
      "discount": 29,
      "validFrom": "2026-06-02",
      "validUntil": "2026-06-07",
      "retailer": "Netto"
    },
    {
      "id": "ap_002",
      "name": "Frische Vollmilch 1L",
      "brand": null,
      "price": 0.89,
      "regularPrice": null,
      "discount": null,
      "validFrom": "2026-06-02",
      "validUntil": "2026-06-07",
      "retailer": "Netto"
    }
  ]
}
```

- [ ] **Step 4: Commit fixtures**

```bash
git add tests/fixtures/marktguru_response.json tests/fixtures/aktionspreis_response.json
git commit -m "test: API response fixtures"
```

---

## Task 4: Scraper Base Class + Marktguru Scraper

**Files:**
- Create: `scrapers/base.py`
- Create: `scrapers/marktguru.py`
- Create: `tests/test_scrapers.py`

- [ ] **Step 1: Create scrapers/base.py**

```python
# scrapers/base.py
from abc import ABC, abstractmethod
from models import Deal


class ScraperError(Exception):
    pass


class BaseScraper(ABC):
    def __init__(
        self,
        stores: list[str],
        timeout: int = 10,
        retries: int = 2,
        zip_code: str = "10115",
    ):
        self.stores = stores
        self.timeout = timeout
        self.retries = retries
        self.zip_code = zip_code

    @abstractmethod
    def fetch(self) -> list[Deal]:
        ...
```

- [ ] **Step 2: Write failing marktguru tests**

```python
# tests/test_scrapers.py
import json
import os
import pytest
from pathlib import Path
from datetime import date
from unittest.mock import patch, MagicMock
from scrapers.marktguru import MarktguruScraper


_FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _marktguru_fixture() -> dict:
    return json.loads((_FIXTURE_DIR / "marktguru_response.json").read_text())


def test_marktguru_parse_returns_deals():
    scraper = MarktguruScraper(stores=["lidl"], zip_code="10115")
    deals = scraper._parse(_marktguru_fixture(), "lidl")
    assert len(deals) > 0


def test_marktguru_deal_fields():
    scraper = MarktguruScraper(stores=["lidl"], zip_code="10115")
    deal = scraper._parse(_marktguru_fixture(), "lidl")[0]
    assert isinstance(deal.product_name, str) and deal.product_name
    assert isinstance(deal.price, float) and deal.price > 0
    assert isinstance(deal.valid_from, date)
    assert isinstance(deal.valid_to, date)
    assert deal.source == "marktguru"
    assert deal.store == "lidl"


def test_marktguru_fetch_calls_api():
    scraper = MarktguruScraper(stores=["lidl"], zip_code="10115")
    mock_resp = MagicMock()
    mock_resp.json.return_value = _marktguru_fixture()
    mock_resp.raise_for_status = MagicMock()
    with patch("scrapers.marktguru.requests.get", return_value=mock_resp) as mock_get:
        deals = scraper.fetch()
    mock_get.assert_called_once()
    assert isinstance(deals, list)


@pytest.mark.skipif(not os.getenv("LIVE_TESTS"), reason="live network — set LIVE_TESTS=1 to run")
def test_marktguru_live():
    scraper = MarktguruScraper(stores=["lidl"], zip_code="10115")
    deals = scraper.fetch()
    assert isinstance(deals, list)
```

- [ ] **Step 3: Run to confirm failure**

```bash
.venv/bin/pytest tests/test_scrapers.py -v -k marktguru
```

Expected: `ModuleNotFoundError: No module named 'scrapers.marktguru'`

- [ ] **Step 4: Implement scrapers/marktguru.py**

Update the constant block at the top after completing Task 3 discovery.

```python
# scrapers/marktguru.py
import time
import requests
from datetime import date
from .base import BaseScraper, ScraperError
from models import Deal

# ── Update these after Task 3 API discovery ───────────────────────────────────
_BASE_URL = "https://api.marktguru.de/api/v1"
_SEARCH_PATH = "/offers/search"
_HEADERS: dict[str, str] = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0",
}
_STORE_MAP = {
    "lidl": "Lidl",
    "aldi": "ALDI",
    "netto": "Netto",
    "rewe": "REWE",
    "edeka": "EDEKA",
    "penny": "Penny",
}
_F_RESULTS = "results"
_F_TITLE = "title"
_F_BRAND = "brand"
_F_BRAND_NAME = "name"
_F_PRICE = "price"
_F_PRICE_AMT = "amount"
_F_ORIG_PRICE = "priceNormal"
_F_DISCOUNT = "discount"
_F_VALIDITY = "validity"
_F_VALID_FROM = "from"
_F_VALID_TO = "to"
# ─────────────────────────────────────────────────────────────────────────────


class MarktguruScraper(BaseScraper):
    def fetch(self) -> list[Deal]:
        deals: list[Deal] = []
        for store in self.stores:
            api_store = _STORE_MAP.get(store.lower())
            if api_store is None:
                continue
            data = self._request(api_store)
            deals.extend(self._parse(data, store))
        return deals

    def _request(self, api_store: str) -> dict:
        params = {
            "as": "web",
            "zipCode": self.zip_code,
            "companyName": api_store,
            "limit": 100,
        }
        last_exc: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                resp = requests.get(
                    f"{_BASE_URL}{_SEARCH_PATH}",
                    params=params,
                    headers=_HEADERS,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < self.retries:
                    time.sleep(2 ** attempt)
        raise ScraperError(f"marktguru request failed: {last_exc}") from last_exc

    def _parse(self, data: dict, store: str) -> list[Deal]:
        deals = []
        for item in data.get(_F_RESULTS, []):
            try:
                deals.append(self._item_to_deal(item, store))
            except (KeyError, ValueError, TypeError):
                continue
        return deals

    def _item_to_deal(self, item: dict, store: str) -> Deal:
        price = float(item[_F_PRICE][_F_PRICE_AMT])

        orig_raw = item.get(_F_ORIG_PRICE)
        original_price = float(orig_raw[_F_PRICE_AMT]) if orig_raw else None

        discount_raw = item.get(_F_DISCOUNT)
        discount_pct = float(discount_raw) if discount_raw is not None else None

        validity = item[_F_VALIDITY]
        valid_from = date.fromisoformat(validity[_F_VALID_FROM][:10])
        valid_to = date.fromisoformat(validity[_F_VALID_TO][:10])

        brand_raw = item.get(_F_BRAND)
        if isinstance(brand_raw, dict):
            brand = brand_raw.get(_F_BRAND_NAME) or None
        elif isinstance(brand_raw, str):
            brand = brand_raw or None
        else:
            brand = None

        return Deal(
            store=store,
            product_name=item[_F_TITLE],
            price=price,
            original_price=original_price,
            discount_pct=discount_pct,
            valid_from=valid_from,
            valid_to=valid_to,
            source="marktguru",
            brand=brand,
        )
```

- [ ] **Step 5: Run marktguru tests**

```bash
.venv/bin/pytest tests/test_scrapers.py -v -k marktguru
```

Expected: 3 PASSED, 1 SKIPPED (live)

- [ ] **Step 6: Commit**

```bash
git add scrapers/base.py scrapers/marktguru.py tests/test_scrapers.py
git commit -m "feat: scraper base class and marktguru scraper"
```

---

## Task 5: Aktionspreis Scraper

**Files:**
- Create: `scrapers/aktionspreis.py`
- Modify: `tests/test_scrapers.py`

- [ ] **Step 1: Append failing aktionspreis tests to tests/test_scrapers.py**

```python
from scrapers.aktionspreis import AktionsPreisScraper


def _aktionspreis_fixture() -> dict:
    return json.loads((_FIXTURE_DIR / "aktionspreis_response.json").read_text())


def test_aktionspreis_parse_returns_deals():
    scraper = AktionsPreisScraper(stores=["netto"], zip_code="10115")
    deals = scraper._parse(_aktionspreis_fixture(), "netto")
    assert len(deals) > 0


def test_aktionspreis_deal_fields():
    scraper = AktionsPreisScraper(stores=["netto"], zip_code="10115")
    deal = scraper._parse(_aktionspreis_fixture(), "netto")[0]
    assert isinstance(deal.product_name, str) and deal.product_name
    assert isinstance(deal.price, float) and deal.price > 0
    assert deal.source == "aktionspreis"
    assert deal.store == "netto"


def test_aktionspreis_fetch_calls_api():
    scraper = AktionsPreisScraper(stores=["netto"], zip_code="10115")
    mock_resp = MagicMock()
    mock_resp.json.return_value = _aktionspreis_fixture()
    mock_resp.raise_for_status = MagicMock()
    with patch("scrapers.aktionspreis.requests.get", return_value=mock_resp) as mock_get:
        deals = scraper.fetch()
    mock_get.assert_called_once()
    assert isinstance(deals, list)


@pytest.mark.skipif(not os.getenv("LIVE_TESTS"), reason="live network — set LIVE_TESTS=1 to run")
def test_aktionspreis_live():
    scraper = AktionsPreisScraper(stores=["netto"], zip_code="10115")
    deals = scraper.fetch()
    assert isinstance(deals, list)
```

- [ ] **Step 2: Run to confirm failure**

```bash
.venv/bin/pytest tests/test_scrapers.py -v -k aktionspreis
```

Expected: `ModuleNotFoundError: No module named 'scrapers.aktionspreis'`

- [ ] **Step 3: Implement scrapers/aktionspreis.py**

Update the constant block after Task 3 discovery.

```python
# scrapers/aktionspreis.py
import time
import requests
from datetime import date
from .base import BaseScraper, ScraperError
from models import Deal

# ── Update these after Task 3 API discovery ───────────────────────────────────
_BASE_URL = "https://www.aktionspreis.de"
_SEARCH_PATH = "/api/v1/offers"
_HEADERS: dict[str, str] = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0",
}
_STORE_MAP = {
    "lidl": "Lidl",
    "aldi": "Aldi",
    "netto": "Netto",
    "rewe": "Rewe",
    "edeka": "Edeka",
    "penny": "Penny",
}
_F_RESULTS = "offers"
_F_TITLE = "name"
_F_BRAND = "brand"
_F_PRICE = "price"
_F_ORIG_PRICE = "regularPrice"
_F_DISCOUNT = "discount"
_F_VALID_FROM = "validFrom"
_F_VALID_TO = "validUntil"
_F_RETAILER = "retailer"
# ─────────────────────────────────────────────────────────────────────────────


class AktionsPreisScraper(BaseScraper):
    def fetch(self) -> list[Deal]:
        deals: list[Deal] = []
        for store in self.stores:
            api_store = _STORE_MAP.get(store.lower())
            if api_store is None:
                continue
            data = self._request(api_store)
            deals.extend(self._parse(data, store))
        return deals

    def _request(self, api_store: str) -> dict:
        params = {
            "retailer": api_store,
            "zipCode": self.zip_code,
            "limit": 100,
        }
        last_exc: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                resp = requests.get(
                    f"{_BASE_URL}{_SEARCH_PATH}",
                    params=params,
                    headers=_HEADERS,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < self.retries:
                    time.sleep(2 ** attempt)
        raise ScraperError(f"aktionspreis request failed: {last_exc}") from last_exc

    def _parse(self, data: dict, store: str) -> list[Deal]:
        deals = []
        for item in data.get(_F_RESULTS, []):
            try:
                deals.append(self._item_to_deal(item, store))
            except (KeyError, ValueError, TypeError):
                continue
        return deals

    def _item_to_deal(self, item: dict, store: str) -> Deal:
        price = float(item[_F_PRICE])

        orig_raw = item.get(_F_ORIG_PRICE)
        original_price = float(orig_raw) if orig_raw is not None else None

        discount_raw = item.get(_F_DISCOUNT)
        discount_pct = float(discount_raw) if discount_raw is not None else None

        valid_from = date.fromisoformat(item[_F_VALID_FROM][:10])
        valid_to = date.fromisoformat(item[_F_VALID_TO][:10])

        brand_raw = item.get(_F_BRAND)
        brand = brand_raw if isinstance(brand_raw, str) and brand_raw else None

        return Deal(
            store=store,
            product_name=item[_F_TITLE],
            price=price,
            original_price=original_price,
            discount_pct=discount_pct,
            valid_from=valid_from,
            valid_to=valid_to,
            source="aktionspreis",
            brand=brand,
        )
```

- [ ] **Step 4: Run all scraper tests**

```bash
.venv/bin/pytest tests/test_scrapers.py -v
```

Expected: 6 PASSED, 2 SKIPPED (live)

- [ ] **Step 5: Commit**

```bash
git add scrapers/aktionspreis.py tests/test_scrapers.py
git commit -m "feat: aktionspreis scraper"
```

---

## Task 6: Fuzzy Matcher

**Files:**
- Create: `matcher.py`
- Create: `tests/test_matcher.py`

- [ ] **Step 1: Write failing matcher tests**

```python
# tests/test_matcher.py
from datetime import date
from models import Deal
from matcher import match_deals


def _deal(name: str, brand: str | None = None, store: str = "lidl") -> Deal:
    return Deal(store, name, 1.99, date(2026, 6, 2), date(2026, 6, 7), "marktguru", brand=brand)


def test_exact_keyword_match():
    assert len(match_deals([_deal("Butter 250g")], ["butter"], threshold=70)) == 1


def test_keyword_substring_in_product_name():
    assert len(match_deals([_deal("Hähnchenfilet 500g")], ["hähnchen"], threshold=70)) == 1


def test_keyword_matches_brand():
    assert len(match_deals([_deal("Hähnchenfilet 500g", brand="Metzgerfrisch")], ["metzgerfrisch"], threshold=70)) == 1


def test_no_match_below_threshold():
    assert len(match_deals([_deal("Orangensaft 1L")], ["butter"], threshold=70)) == 0


def test_case_insensitive():
    assert len(match_deals([_deal("BUTTER 250g")], ["butter"], threshold=70)) == 1


def test_multiple_keywords_one_match():
    deals = [_deal("Hähnchenfilet 500g")]
    assert len(match_deals(deals, ["butter", "hähnchen", "milch"], threshold=70)) == 1


def test_no_duplicates_when_multiple_keywords_match_same_deal():
    deals = [_deal("Hähnchenbutter")]
    assert len(match_deals(deals, ["hähnchen", "butter"], threshold=70)) == 1


def test_umlaut_variant_matches():
    assert len(match_deals([_deal("Grillhähnchen ganz")], ["hähnchen"], threshold=70)) == 1


def test_empty_watchlist_returns_empty():
    assert match_deals([_deal("Butter 250g")], [], threshold=70) == []


def test_empty_deals_returns_empty():
    assert match_deals([], ["butter"], threshold=70) == []
```

- [ ] **Step 2: Run to confirm failure**

```bash
.venv/bin/pytest tests/test_matcher.py -v
```

Expected: `ModuleNotFoundError: No module named 'matcher'`

- [ ] **Step 3: Implement matcher.py**

```python
# matcher.py
from rapidfuzz import fuzz
from models import Deal


def match_deals(deals: list[Deal], keywords: list[str], threshold: int = 70) -> list[Deal]:
    if not keywords or not deals:
        return []
    seen_ids: set[str] = set()
    matched: list[Deal] = []
    for deal in deals:
        if deal.id in seen_ids:
            continue
        if _matches(deal, keywords, threshold):
            matched.append(deal)
            seen_ids.add(deal.id)
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
```

- [ ] **Step 4: Run matcher tests**

```bash
.venv/bin/pytest tests/test_matcher.py -v
```

Expected: 10 PASSED

- [ ] **Step 5: Commit**

```bash
git add matcher.py tests/test_matcher.py
git commit -m "feat: fuzzy deal matcher"
```

---

## Task 7: Cache

**Files:**
- Create: `cache.py`
- Create: `tests/test_cache.py`

- [ ] **Step 1: Write failing cache tests**

```python
# tests/test_cache.py
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from cache import Cache


@pytest.fixture
def tmp_cache(tmp_path) -> Cache:
    return Cache(cache_file=tmp_path / "cache.json", ttl_days=14)


def test_new_cache_is_empty(tmp_cache):
    tmp_cache.load()
    assert not tmp_cache.contains("abc123")


def test_add_and_contains(tmp_cache):
    tmp_cache.load()
    tmp_cache.add("abc123")
    assert tmp_cache.contains("abc123")


def test_unknown_id_not_contained(tmp_cache):
    tmp_cache.load()
    tmp_cache.add("abc123")
    assert not tmp_cache.contains("xyz999")


def test_save_and_reload(tmp_cache):
    tmp_cache.load()
    tmp_cache.add("abc123")
    tmp_cache.save()
    cache2 = Cache(cache_file=tmp_cache.cache_file, ttl_days=14)
    cache2.load()
    assert cache2.contains("abc123")


def test_expire_removes_old_entries(tmp_cache):
    tmp_cache.load()
    old_ts = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
    tmp_cache._data["old_deal"] = old_ts
    tmp_cache.expire()
    assert not tmp_cache.contains("old_deal")


def test_expire_keeps_recent_entries(tmp_cache):
    tmp_cache.load()
    tmp_cache.add("new_deal")
    tmp_cache.expire()
    assert tmp_cache.contains("new_deal")


def test_add_all(tmp_cache):
    tmp_cache.load()
    tmp_cache.add_all(["a1", "b2", "c3"])
    assert all(tmp_cache.contains(x) for x in ["a1", "b2", "c3"])


def test_missing_cache_file_loads_empty(tmp_path):
    cache = Cache(cache_file=tmp_path / "nonexistent.json", ttl_days=14)
    cache.load()
    assert not cache.contains("anything")
```

- [ ] **Step 2: Run to confirm failure**

```bash
.venv/bin/pytest tests/test_cache.py -v
```

Expected: `ModuleNotFoundError: No module named 'cache'`

- [ ] **Step 3: Implement cache.py**

```python
# cache.py
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path


class Cache:
    def __init__(self, cache_file: Path, ttl_days: int = 14):
        self.cache_file = cache_file
        self.ttl_days = ttl_days
        self._data: dict[str, str] = {}

    def load(self) -> None:
        if not self.cache_file.exists():
            self._data = {}
            return
        with open(self.cache_file, "r", encoding="utf-8") as f:
            self._data = json.load(f)

    def save(self) -> None:
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def contains(self, deal_id: str) -> bool:
        return deal_id in self._data

    def add(self, deal_id: str) -> None:
        self._data[deal_id] = datetime.now(timezone.utc).isoformat()

    def add_all(self, deal_ids: list[str]) -> None:
        for deal_id in deal_ids:
            self.add(deal_id)

    def expire(self) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.ttl_days)
        self._data = {
            k: v for k, v in self._data.items()
            if datetime.fromisoformat(v) > cutoff
        }
```

- [ ] **Step 4: Run cache tests**

```bash
.venv/bin/pytest tests/test_cache.py -v
```

Expected: 8 PASSED

- [ ] **Step 5: Commit**

```bash
git add cache.py tests/test_cache.py
git commit -m "feat: deal cache with TTL expiry"
```

---

## Task 8: Formatter

**Files:**
- Create: `formatter.py`
- Create: `tests/test_formatter.py`

- [ ] **Step 1: Write failing formatter tests**

```python
# tests/test_formatter.py
import json
from datetime import date
from pathlib import Path
from models import Deal
from formatter import format_stdout_lines, write_results_json


def _deal(
    store="lidl", name="Hähnchenfilet 500g", price=2.49, brand="Metzgerfrisch",
    original_price=3.99, discount_pct=38.0,
    valid_from=date(2026, 6, 2), valid_to=date(2026, 6, 7), source="marktguru",
) -> Deal:
    return Deal(store, name, price, valid_from, valid_to, source,
                brand=brand, original_price=original_price, discount_pct=discount_pct)


def test_line_contains_store_uppercase():
    assert "[LIDL]" in format_stdout_lines([_deal()])[0]


def test_line_contains_brand_and_product_name():
    line = format_stdout_lines([_deal()])[0]
    assert "Metzgerfrisch" in line
    assert "Hähnchenfilet 500g" in line


def test_line_german_price_format():
    line = format_stdout_lines([_deal(price=2.49, original_price=3.99)])[0]
    assert "2,49€" in line
    assert "3,99€" in line


def test_line_discount_percent():
    assert "-38%" in format_stdout_lines([_deal(discount_pct=38.0)])[0]


def test_line_german_date_range():
    line = format_stdout_lines([_deal(valid_from=date(2026, 6, 2), valid_to=date(2026, 6, 7))])[0]
    assert "02.06" in line
    assert "07.06" in line


def test_line_no_brand_omits_brand_prefix():
    deal = Deal("aldi", "Butter 250g", 1.29, date(2026, 6, 2), date(2026, 6, 7), "marktguru")
    line = format_stdout_lines([deal])[0]
    assert "Butter 250g" in line


def test_line_no_original_price_omits_statt():
    deal = Deal("aldi", "Butter 250g", 1.29, date(2026, 6, 2), date(2026, 6, 7), "marktguru")
    assert "statt" not in format_stdout_lines([deal])[0]


def test_empty_deals_returns_no_results_message():
    assert format_stdout_lines([]) == ["Keine neuen Angebote gefunden."]


def test_write_results_json(tmp_path):
    out = tmp_path / "results.json"
    write_results_json([_deal()], out)
    data = json.loads(out.read_text())
    assert len(data) == 1
    assert data[0]["store"] == "lidl"
    assert data[0]["price"] == 2.49


def test_write_results_json_empty(tmp_path):
    out = tmp_path / "results.json"
    write_results_json([], out)
    assert json.loads(out.read_text()) == []
```

- [ ] **Step 2: Run to confirm failure**

```bash
.venv/bin/pytest tests/test_formatter.py -v
```

Expected: `ModuleNotFoundError: No module named 'formatter'`

- [ ] **Step 3: Implement formatter.py**

```python
# formatter.py
import json
from datetime import date
from pathlib import Path
from models import Deal


def _fmt_price(value: float) -> str:
    return f"{value:.2f}".replace(".", ",") + "€"


def _fmt_date(d: date) -> str:
    return d.strftime("%d.%m")


def format_stdout_lines(deals: list[Deal]) -> list[str]:
    if not deals:
        return ["Keine neuen Angebote gefunden."]
    lines = []
    for deal in deals:
        name = f"{deal.brand} {deal.product_name}" if deal.brand else deal.product_name
        price_str = _fmt_price(deal.price)
        if deal.original_price is not None and deal.discount_pct is not None:
            discount_part = f" (statt {_fmt_price(deal.original_price)}, -{deal.discount_pct:.0f}%)"
        else:
            discount_part = ""
        date_range = f"{_fmt_date(deal.valid_from)}–{_fmt_date(deal.valid_to)}"
        lines.append(f"[{deal.store.upper()}] {name} — {price_str}{discount_part} | gültig {date_range}")
    return lines


def write_results_json(deals: list[Deal], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump([d.to_dict() for d in deals], f, ensure_ascii=False, indent=2)
```

- [ ] **Step 4: Run formatter tests**

```bash
.venv/bin/pytest tests/test_formatter.py -v
```

Expected: 10 PASSED

- [ ] **Step 5: Commit**

```bash
git add formatter.py tests/test_formatter.py
git commit -m "feat: German formatter and JSON output"
```

---

## Task 9: Orchestrator (scraper.py)

**Files:**
- Create: `scraper.py`
- Create: `tests/test_scraper.py`

- [ ] **Step 1: Write failing orchestrator tests**

```python
# tests/test_scraper.py
import importlib
import sys
import pytest
from datetime import date
from unittest.mock import MagicMock, patch
from models import Deal
from scrapers.base import ScraperError


def _fake_deals() -> list[Deal]:
    return [
        Deal("lidl", "Hähnchenfilet 500g", 2.49, date(2026, 6, 2), date(2026, 6, 7), "marktguru",
             brand="Metzgerfrisch", original_price=3.99, discount_pct=38.0),
    ]


def _run(extra_argv: list[str] | None = None, marktguru_deals=None, cached=False):
    if marktguru_deals is None:
        marktguru_deals = _fake_deals()
    with (
        patch("scrapers.marktguru.MarktguruScraper.fetch", return_value=marktguru_deals),
        patch("scrapers.aktionspreis.AktionsPreisScraper.fetch", return_value=[]),
        patch("cache.Cache.load"),
        patch("cache.Cache.expire"),
        patch("cache.Cache.contains", return_value=cached),
        patch("cache.Cache.save"),
        patch("cache.Cache.add_all"),
        patch("formatter.write_results_json"),
        patch("pathlib.Path.mkdir"),
        patch("sys.argv", ["scraper.py"] + (extra_argv or [])),
    ):
        import scraper
        importlib.reload(scraper)
        scraper.main()


def test_new_deal_is_printed(capsys):
    _run(cached=False)
    assert "LIDL" in capsys.readouterr().out


def test_cached_deal_is_skipped(capsys):
    _run(cached=True)
    assert "Keine neuen Angebote gefunden." in capsys.readouterr().out


def test_force_flag_reports_cached_deal(capsys):
    _run(extra_argv=["--force"], cached=True)
    assert "LIDL" in capsys.readouterr().out


def test_both_scrapers_fail_exits_1():
    with (
        patch("scrapers.marktguru.MarktguruScraper.fetch", side_effect=ScraperError("down")),
        patch("scrapers.aktionspreis.AktionsPreisScraper.fetch", side_effect=ScraperError("down")),
        patch("sys.argv", ["scraper.py"]),
    ):
        import scraper
        importlib.reload(scraper)
        with pytest.raises(SystemExit) as exc_info:
            scraper.main()
    assert exc_info.value.code == 1


def test_dry_run_skips_json_write_and_cache_save(capsys):
    mock_write = MagicMock()
    mock_save = MagicMock()
    with (
        patch("scrapers.marktguru.MarktguruScraper.fetch", return_value=_fake_deals()),
        patch("scrapers.aktionspreis.AktionsPreisScraper.fetch", return_value=[]),
        patch("cache.Cache.load"),
        patch("cache.Cache.expire"),
        patch("cache.Cache.contains", return_value=False),
        patch("cache.Cache.save", mock_save),
        patch("cache.Cache.add_all"),
        patch("formatter.write_results_json", mock_write),
        patch("pathlib.Path.mkdir"),
        patch("sys.argv", ["scraper.py", "--dry-run"]),
    ):
        import scraper
        importlib.reload(scraper)
        scraper.main()
    mock_write.assert_not_called()
    mock_save.assert_not_called()
```

- [ ] **Step 2: Run to confirm failure**

```bash
.venv/bin/pytest tests/test_scraper.py -v
```

Expected: `ModuleNotFoundError: No module named 'scraper'`

- [ ] **Step 3: Implement scraper.py**

```python
# scraper.py
import argparse
import sys
from pathlib import Path

import formatter
from cache import Cache
from config import load_products, load_settings, load_supermarkets
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
    supermarkets = load_supermarkets()
    net = settings["network"]
    scrape = settings["scraping"]

    all_deals: list[Deal] = []
    errors = 0

    for cls in (MarktguruScraper, AktionsPreisScraper):
        try:
            s = cls(
                stores=supermarkets,
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

    matched = match_deals(all_deals, products, threshold=settings["matching"]["threshold"])

    cache = Cache(cache_file=_CACHE_FILE, ttl_days=settings["cache"]["ttl_days"])
    cache.load()
    cache.expire()

    new_deals = matched if args.force else [d for d in matched if not cache.contains(d.id)]

    for line in formatter.format_stdout_lines(new_deals):
        print(line)

    if not args.dry_run:
        _OUTPUT_DIR.mkdir(exist_ok=True)
        formatter.write_results_json(new_deals, _RESULTS_FILE)
        cache.add_all([d.id for d in new_deals])
        cache.save()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run full test suite**

```bash
.venv/bin/pytest -v
```

Expected: all PASSED, 2 SKIPPED (live network tests)

- [ ] **Step 5: Smoke test**

```bash
.venv/bin/python scraper.py --dry-run
```

Expected: either deal lines or `Keine neuen Angebote gefunden.`

If both scrapers fail with connection errors, the API endpoints need updating (Task 3 discovery). Check `scrapers/marktguru.py` and `scrapers/aktionspreis.py` constant blocks.

- [ ] **Step 6: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: orchestrator and CLI entry point"
```

---

## Post-Discovery: Update Scrapers After Task 3

After live API discovery, update these files if the actual response structures differ from the placeholders:

1. `scrapers/marktguru.py` — update `_BASE_URL`, `_SEARCH_PATH`, `_HEADERS`, `_STORE_MAP`, field name constants
2. `scrapers/aktionspreis.py` — same
3. `tests/fixtures/marktguru_response.json` — replace with real API response (2–3 offers)
4. `tests/fixtures/aktionspreis_response.json` — replace with real API response

Then verify:
```bash
.venv/bin/pytest -v
LIVE_TESTS=1 .venv/bin/pytest tests/test_scrapers.py -v
.venv/bin/python scraper.py --dry-run
```

HA invocation: `.venv/bin/python /path/to/supermarket-scraper/scraper.py`
