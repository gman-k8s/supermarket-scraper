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
