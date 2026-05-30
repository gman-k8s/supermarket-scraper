# scrapers/marktguru.py
import time
import requests
from datetime import date
from .base import BaseScraper, ScraperError
from models import Deal

_BASE_URL = "https://api.marktguru.de/api/v1"
_API_KEY = "8Kk+pmbf7TgJ9nVj2cXeA7P5zBGv8iuutVVMRfOfvNE="
_HEADERS: dict[str, str] = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0",
    "X-ApiKey": _API_KEY,
}


class MarktguruScraper(BaseScraper):
    def fetch(self) -> list[Deal]:
        client_key = self._get_client_key()
        headers = {**_HEADERS, "X-ClientKey": client_key}
        deals: list[Deal] = []
        for product in self.products:
            results = self._request(product, headers)
            for item in results:
                store = self._match_store(item)
                if store is None:
                    continue
                try:
                    deals.append(self._item_to_deal(item, store))
                except (KeyError, ValueError, TypeError):
                    continue
        return deals

    def _get_client_key(self) -> str:
        last_exc: Exception | None = None
        for attempt in range(max(1, self.retries + 1)):
            try:
                resp = requests.get(
                    f"{_BASE_URL}/configurations/web",
                    headers={"x-apikey": _API_KEY, "Accept": "application/json"},
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                key = resp.headers.get("x-clientkey", "")
                if not key:
                    raise ScraperError("marktguru configurations returned no x-clientkey")
                return key
            except ScraperError:
                raise
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < self.retries:
                    time.sleep(2 ** attempt)
        raise ScraperError(f"marktguru config request failed: {last_exc}") from last_exc

    def _request(self, product: str, headers: dict) -> list:
        params = {
            "as": "web",
            "zipCode": self.zip_code,
            "q": product,
            "limit": 100,
        }
        last_exc: Exception | None = None
        for attempt in range(max(1, self.retries + 1)):
            try:
                resp = requests.get(
                    f"{_BASE_URL}/offers/search",
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                if not isinstance(data, dict):
                    raise ScraperError(f"marktguru API returned unexpected type: {type(data).__name__}")
                return data.get("results") or []
            except ScraperError:
                raise
            except ValueError as exc:
                raise ScraperError(f"marktguru response is not valid JSON: {exc}") from exc
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < self.retries:
                    time.sleep(2 ** attempt)
        raise ScraperError(f"marktguru request failed: {last_exc}") from last_exc

    def _match_store(self, item: dict) -> str | None:
        advertisers = item.get("advertisers") or []
        if not advertisers:
            return None
        api_name = advertisers[0].get("name", "").lower()
        for store in self.stores:
            if store in api_name:
                return store
        return None

    def _item_to_deal(self, item: dict, store: str) -> Deal:
        price = float(item["price"])

        old_price_raw = item.get("oldPrice")
        original_price = float(old_price_raw) if old_price_raw is not None else None

        dates = item.get("validityDates") or []
        if not dates:
            raise ValueError("no validityDates")
        valid_from = date.fromisoformat(dates[0]["from"][:10])
        valid_to = date.fromisoformat(dates[0]["to"][:10])

        brand_raw = item.get("brand")
        brand_name = brand_raw.get("name") if isinstance(brand_raw, dict) else (brand_raw or None)
        brand = brand_name if brand_name and brand_name != "thisisnobrand123" else None

        product_info = item.get("product") or {}
        categories = item.get("categories") or []
        category_name = categories[0].get("name", "") if categories else ""
        product_name = f"{category_name} {product_info.get('name', '')}".strip() or item.get("description", "")

        return Deal(
            store=store,
            product_name=product_name,
            price=price,
            original_price=original_price,
            discount_pct=None,
            valid_from=valid_from,
            valid_to=valid_to,
            source="marktguru",
            brand=brand,
        )
