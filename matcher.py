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
                    break  # first non-excluded match is authoritative
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
    return any(t.lower() in haystack for t in terms)
