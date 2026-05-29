# scrapers/aktionspreis.py
import sys
import time
import requests
from datetime import date
from .base import BaseScraper, ScraperError
from models import Deal

# ── Update these after live API discovery ────────────────────────────────────
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
# ─────────────────────────────────────────────────────────────────────────────


class AktionsPreisScraper(BaseScraper):
    def fetch(self) -> list[Deal]:
        deals: list[Deal] = []
        for store in self.stores:
            api_store = _STORE_MAP.get(store.lower())
            if api_store is None:
                print(f"Warnung: Supermarkt '{store}' wird von aktionspreis nicht unterstützt.", file=sys.stderr)
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
        for attempt in range(max(1, self.retries + 1)):
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
        # discount is integer 0-100 (e.g. 29 means 29%) — verify against live API
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
