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
