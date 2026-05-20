"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from allegro import scrape_product, scrape_search, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


SEARCH_SCHEMA = {
    "products": {"type": "list", "required": True},
    "scraped_pages": {"type": "integer", "required": True},
    "products_count": {"type": "integer", "required": True},
    "total_pages": {"type": "integer", "nullable": True, "required": False},
    "total_count": {"type": "integer", "nullable": True, "required": False},
}

SEARCH_ITEM_SCHEMA = {
    "product_id": {"type": "string", "required": False, "nullable": True},
    "offer_id": {"type": "string", "required": False, "nullable": True},
    "title": {"type": "string", "required": True},
    "url": {"type": "string", "required": True},
}

PRODUCT_SCHEMA = {
    "title": {"type": "string", "required": True, "minlength": 1},
    "price": {"type": "dict", "required": True},
    "images": {"type": "list", "required": False},
    "rating": {"type": "string", "nullable": True, "required": False},
    "specifications": {"type": "list", "required": False},
    "seller": {"type": "dict", "required": False},
    "reviews": {"type": "list", "required": False},
    "allegro_smart_badge": {"type": "boolean", "required": False},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    query = os.environ.get("ALLEGRO_QUERY", "iphone")
    result = to_dict(await scrape_search(query, max_pages=1))
    _validate(result, SEARCH_SCHEMA)
    assert result["products_count"] >= 1
    for item in result["products"]:
        _validate(item, SEARCH_ITEM_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_product():
    urls = (os.environ.get("ALLEGRO_PRODUCT_URLS")
            or "https://allegro.pl/oferta/iphone-15-pro-256gb-natural-titanium-14488061197").split(",")
    products = [to_dict(p) for p in await scrape_product(urls)]
    assert len(products) == len(urls)
    for p in products:
        _validate(p, PRODUCT_SCHEMA)
