"""Per-search-term text cache: output/deals/<slug>.txt (3 header lines + TSV)."""
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from models import Deal

_COLUMNS = ["id", "store", "brand", "product_name", "price", "original_price",
            "discount_pct", "valid_from", "valid_to", "source", "ean"]


@dataclass
class CachedTerm:
    term: str
    fetched: datetime
    sources: list[str]
    deals: list[Deal]


def slugify(term: str) -> str:
    slug = re.sub(r"[^a-z0-9äöüß]+", "-", term.lower())
    return slug.strip("-")


def _path(cache_dir: Path, term: str) -> Path:
    return cache_dir / f"{slugify(term)}.txt"


def _clean(value) -> str:
    if value is None:
        return ""
    return re.sub(r"[\t\r\n]+", " ", str(value))


def write_term(cache_dir: Path, term: str, deals: list[Deal], sources: list[str], fetched: datetime) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# term: {_clean(term)}",
        f"# fetched: {fetched.replace(microsecond=0).isoformat()}",
        f"# sources: {','.join(sources)}",
    ]
    for d in deals:
        row = d.to_dict()
        lines.append("\t".join(_clean(row[c]) for c in _COLUMNS))
    _path(cache_dir, term).write_text("\n".join(lines) + "\n", "utf-8")


def _opt_float(s: str) -> float | None:
    return float(s) if s else None


def read_term(cache_dir: Path, term: str, today: date) -> CachedTerm | None:
    path = _path(cache_dir, term)
    try:
        lines = path.read_text("utf-8").splitlines()
        if len(lines) < 3 or not lines[0].startswith("# term: ") \
                or not lines[1].startswith("# fetched: ") or not lines[2].startswith("# sources: "):
            return None
        fetched = datetime.fromisoformat(lines[1][len("# fetched: "):].strip())
        sources_raw = lines[2][len("# sources: "):].strip()
        sources = [s for s in sources_raw.split(",") if s]
        deals: list[Deal] = []
        for line in lines[3:]:
            if not line.strip():
                continue
            cells = line.split("\t")
            if len(cells) != len(_COLUMNS):
                return None
            f = dict(zip(_COLUMNS, cells))
            deal = Deal(
                store=f["store"],
                product_name=f["product_name"],
                price=float(f["price"]),
                valid_from=date.fromisoformat(f["valid_from"]),
                valid_to=date.fromisoformat(f["valid_to"]),
                source=f["source"],
                brand=f["brand"] or None,
                ean=f["ean"] or None,
                original_price=_opt_float(f["original_price"]),
                discount_pct=_opt_float(f["discount_pct"]),
            )
            if deal.valid_to >= today:
                deals.append(deal)
    except (OSError, ValueError, KeyError):
        return None
    return CachedTerm(term=term, fetched=fetched, sources=sources, deals=deals)


def is_fresh(cached: CachedTerm, now: datetime, max_age_days: int) -> bool:
    return now - cached.fetched < timedelta(days=max_age_days)
