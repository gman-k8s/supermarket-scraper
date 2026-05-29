from config import load_products, load_supermarkets, load_settings


def test_load_products_returns_lowercase_list():
    products = load_products()
    assert isinstance(products, list)
    assert len(products) > 0
    assert all(p == p.lower() for p in products)


def test_load_supermarkets_contains_defaults():
    stores = load_supermarkets()
    assert "lidl" in stores
    assert "aldi" in stores
    assert "netto" in stores


def test_load_settings_has_required_keys():
    settings = load_settings()
    assert settings["matching"]["threshold"] == 70
    assert settings["network"]["timeout_seconds"] == 10
    assert settings["network"]["retries"] == 2
    assert settings["cache"]["ttl_days"] == 14
    assert settings["scraping"]["zip_code"] == "10115"
