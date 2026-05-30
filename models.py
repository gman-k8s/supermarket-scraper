from dataclasses import dataclass, field
from datetime import date
from hashlib import sha256


@dataclass
class Deal:
    store: str
    product_name: str
    price: float
    valid_from: date
    valid_to: date
    source: str
    brand: str | None = None
    original_price: float | None = None
    discount_pct: float | None = None
    id: str = field(init=False)

    def __post_init__(self):
        raw = f"{self.source}{self.store}{self.product_name}{self.valid_from}"
        self.id = sha256(raw.encode()).hexdigest()[:12]
        if self.discount_pct is None and self.original_price and self.original_price > self.price:
            self.discount_pct = (1 - self.price / self.original_price) * 100

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "store": self.store,
            "brand": self.brand,
            "product_name": self.product_name,
            "price": self.price,
            "original_price": self.original_price,
            "discount_pct": self.discount_pct,
            "valid_from": self.valid_from.isoformat(),
            "valid_to": self.valid_to.isoformat(),
            "source": self.source,
        }
