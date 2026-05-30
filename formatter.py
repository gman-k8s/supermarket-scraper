import json
from datetime import date
from pathlib import Path
from models import Deal


def _fmt_price(value: float) -> str:
    return f"{value:.2f}".replace(".", ",") + "€"


def _fmt_date(d: date) -> str:
    return d.strftime("%d.%m")


def _fmt_deal_line(deal: Deal) -> str:
    if deal.brand and not deal.product_name.lower().startswith(deal.brand.lower()):
        name = f"{deal.brand} {deal.product_name}"
    else:
        name = deal.product_name
    price_str = _fmt_price(deal.price)
    if deal.original_price is not None and deal.discount_pct is not None:
        discount_part = f" (statt {_fmt_price(deal.original_price)}, -{deal.discount_pct:.0f}%)"
    else:
        discount_part = ""
    date_range = f"{_fmt_date(deal.valid_from)}–{_fmt_date(deal.valid_to)}"
    return f"  {name} — {price_str}{discount_part} | {date_range}"


def _store_covered_keywords(store_deals: list[Deal], products: list[str]) -> list[str]:
    covered = []
    for keyword in products:
        needle = keyword.lower()
        for deal in store_deals:
            haystack = f"{deal.product_name} {deal.brand or ''}".lower()
            if needle in haystack:
                covered.append(keyword)
                break
    return covered


def format_stdout_lines(deals: list[Deal], products: list[str] | None = None) -> list[str]:
    if not deals:
        return ["Keine neuen Angebote gefunden."]

    by_store: dict[str, list[Deal]] = {}
    for deal in deals:
        by_store.setdefault(deal.store, []).append(deal)

    lines: list[str] = []
    for store in sorted(by_store):
        lines.append(f"=== {store.upper()} ===")
        for deal in by_store[store]:
            lines.append(_fmt_deal_line(deal))
        lines.append("")

    if products:
        total = len(products)
        lines.append("--- Abdeckung ---")
        for store in sorted(by_store):
            covered = _store_covered_keywords(by_store[store], products)
            count = len(covered)
            label = f"{store.upper()}:"
            items_str = ", ".join(covered) if covered else "–"
            lines.append(f"  {label:<8} {count}/{total}  {items_str}")

    return lines


def write_results_json(deals: list[Deal], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump([d.to_dict() for d in deals], f, ensure_ascii=False, indent=2)
