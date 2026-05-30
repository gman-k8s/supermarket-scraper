import re
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

_CONFIG_DIR = Path(__file__).parent / "config"


def load_products() -> list[str]:
    text = (_CONFIG_DIR / "products.txt").read_text("utf-8")
    return [line.strip().lower() for line in text.splitlines() if line.strip()]


def load_supermarkets() -> list[str]:
    text = (_CONFIG_DIR / "supermarkets.txt").read_text("utf-8")
    return [line.strip().lower() for line in text.splitlines() if line.strip()]


def load_settings() -> dict:
    with open(_CONFIG_DIR / "settings.toml", "rb") as f:
        return tomllib.load(f)


def load_exclusions() -> dict[str, list[str]]:
    path = _CONFIG_DIR / "exclusions.txt"
    if not path.exists():
        return {}
    result: dict[str, list[str]] = {}
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        keyword, _, rest = line.partition(":")
        result[keyword.strip().lower()] = [t.lower() for t in re.findall(r'"([^"]+)"', rest)]
    return result
