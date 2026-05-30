# scrapers/aktionspreis.py
import json
import re
import time
from datetime import date

import requests

from .base import BaseScraper, ScraperError
from models import Deal

_BASE_URL = "https://www.aktionspreis.de"
_HEADERS: dict[str, str] = {
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Encoding": "gzip, deflate, br",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}
_MAX_OFFERS_PER_PRODUCT = 20


class AktionsPreisScraper(BaseScraper):
    def fetch(self) -> list[Deal]:
        deals: list[Deal] = []
        seen_slugs: set[str] = set()
        for product in self.products:
            slugs = self._search(product)
            for slug in slugs[:_MAX_OFFERS_PER_PRODUCT]:
                if slug in seen_slugs:
                    continue
                seen_slugs.add(slug)
                try:
                    offer_data = self._fetch_offer(slug)
                    deals.extend(self._parse_offer(offer_data))
                except ScraperError:
                    continue
        return deals

    def _search(self, product: str) -> list[str]:
        html = self._get(_BASE_URL, params={"search": product})
        slugs: list[str] = []
        seen: set[str] = set()
        for m in re.finditer(r'href="(/angebote/[a-z0-9-]+)"', html):
            slug = m.group(1)
            if slug not in seen:
                seen.add(slug)
                slugs.append(slug)
        return slugs

    def _fetch_offer(self, slug: str) -> dict:
        html = self._get(f"{_BASE_URL}{slug}")
        return self._parse_jsonld(html)

    def _parse_jsonld(self, html: str) -> dict:
        blocks = re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html,
            re.DOTALL,
        )
        product = None
        sale_events: list[dict] = []
        for block in blocks:
            try:
                data = json.loads(block)
            except json.JSONDecodeError:
                continue
            t = data.get("@type")
            if t == "Product":
                offers = data.get("offers", {})
                if offers.get("@type") == "AggregateOffer" and "lowPrice" in offers:
                    product = data
            elif t == "SaleEvent":
                sale_events.append(data)
        return {"product": product, "sale_events": sale_events}

    def _parse_offer(self, offer_data: dict) -> list[Deal]:
        product = offer_data.get("product")
        sale_events = offer_data.get("sale_events", [])
        if not product or not sale_events:
            return []

        product_name = product.get("name", "")
        offers = product.get("offers", {})
        try:
            price = float(offers["lowPrice"])
        except (KeyError, ValueError, TypeError):
            return []
        if price <= 0:
            return []

        manufacturer = product.get("manufacturer") or {}
        brand = manufacturer.get("name") if isinstance(manufacturer, dict) else None

        deals: list[Deal] = []
        for event in sale_events:
            organizer = event.get("organizer") or {}
            store_name = organizer.get("name", "")
            matched_store = self._match_store(store_name)
            if matched_store is None:
                continue
            try:
                valid_from = date.fromisoformat(event["startDate"])
                valid_to = date.fromisoformat(event["endDate"])
            except (KeyError, ValueError):
                continue
            deals.append(Deal(
                store=matched_store,
                product_name=product_name,
                price=price,
                original_price=None,
                discount_pct=None,
                valid_from=valid_from,
                valid_to=valid_to,
                source="aktionspreis",
                brand=brand,
            ))
        return deals

    def _match_store(self, api_name: str) -> str | None:
        api_lower = api_name.lower()
        for store in self.stores:
            if store in api_lower:
                return store
        return None

    def _get(self, url: str, params: dict | None = None) -> str:
        last_exc: Exception | None = None
        for attempt in range(max(1, self.retries + 1)):
            try:
                resp = requests.get(url, params=params, headers=_HEADERS, timeout=self.timeout)
                resp.raise_for_status()
                return resp.content.decode("utf-8", errors="replace")
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < self.retries:
                    time.sleep(2 ** attempt)
        raise ScraperError(f"aktionspreis request failed: {last_exc}") from last_exc
