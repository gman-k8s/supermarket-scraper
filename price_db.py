import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from models import Deal

_SCHEMA = """
CREATE TABLE IF NOT EXISTS price_history (
    id              TEXT PRIMARY KEY,
    ean             TEXT,
    store           TEXT NOT NULL,
    product_name    TEXT NOT NULL,
    brand           TEXT,
    price           REAL NOT NULL,
    original_price  REAL,
    discount_pct    REAL,
    valid_from      TEXT NOT NULL,
    valid_to        TEXT NOT NULL,
    source          TEXT NOT NULL,
    scraped_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ean ON price_history(ean);
CREATE INDEX IF NOT EXISTS idx_store_valid ON price_history(store, valid_from);
"""


class PriceDB:
    def __init__(self, db_path: Path) -> None:
        self._path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def save_all(self, deals: list[Deal]) -> None:
        scraped_at = datetime.now(timezone.utc).isoformat()
        rows = [
            (
                d.id,
                d.ean,
                d.store,
                d.product_name,
                d.brand,
                d.price,
                d.original_price,
                d.discount_pct,
                d.valid_from.isoformat(),
                d.valid_to.isoformat(),
                d.source,
                scraped_at,
            )
            for d in deals
        ]
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO price_history
                    (id, ean, store, product_name, brand, price,
                     original_price, discount_pct, valid_from, valid_to, source, scraped_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    ean          = excluded.ean,
                    scraped_at   = excluded.scraped_at
                """,
                rows,
            )
