# scrapers/base.py
from abc import ABC, abstractmethod
from models import Deal


class ScraperError(Exception):
    pass


class BaseScraper(ABC):
    def __init__(
        self,
        stores: list[str],
        timeout: int = 10,
        retries: int = 2,
        zip_code: str = "10115",
    ):
        self.stores = stores
        self.timeout = timeout
        self.retries = retries
        self.zip_code = zip_code

    @abstractmethod
    def fetch(self) -> list[Deal]:
        ...
