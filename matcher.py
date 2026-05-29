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
