"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from depop import scrape_product, scrape_search, scrape_shop, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


PRODUCT_SCHEMA = {
    "id": {"type": "string", "required": True},
    "url": {"type": "string", "required": True},
    "title": {"type": "string", "required": True},
    "price": {"type": "string", "nullable": True},
    "currency": {"type": "string", "nullable": True},
    "brand": {"type": "string", "nullable": True},
    "condition": {"type": "string", "nullable": True},
    "size": {"type": "string", "nullable": True},
    "color": {"type": "string", "nullable": True},
    "description": {"type": "string", "nullable": True},
    "images": {"type": "list", "required": True, "schema": {"type": "string"}},
    "seller": {"type": "string", "nullable": True},
    "sellerUrl": {"type": "string", "nullable": True},
    "hashtags": {"type": "list", "required": True, "schema": {"type": "string"}},
    "sold": {"type": "boolean", "required": True},
}

SEARCH_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "title": {"type": "string", "required": True},
    "url": {"type": "string", "required": True},
    "image": {"type": "string", "nullable": True},
    "price": {"type": "string", "nullable": True},
    "originalPrice": {"type": "string", "nullable": True},
    "seller": {"type": "string", "nullable": True},
    "size": {"type": "string", "nullable": True},
}

SHOP_SCHEMA = {
    "username": {"type": "string", "required": True, "minlength": 1},
    "url": {"type": "string", "required": True},
    "displayName": {"type": "string", "nullable": True},
    "bio": {"type": "string", "nullable": True},
    "avatar": {"type": "string", "nullable": True},
    "location": {"type": "string", "nullable": True},
    "followers": {"type": "integer", "nullable": True},
    "following": {"type": "integer", "nullable": True},
    "reviews": {"type": "integer", "nullable": True},
    "rating": {"type": "float", "nullable": True},
    "listings": {"type": "list", "required": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_product():
    sample = os.environ.get(
        "DEPOP_SAMPLE_PRODUCT_URL",
        "https://www.depop.com/products/gasbiegzr-levis-jeans-size-25-light-7515/",
    )
    product = to_dict(await scrape_product(sample))
    _validate(product, PRODUCT_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    sample_query = os.environ.get("DEPOP_SAMPLE_QUERY", "levi jeans")
    results = [to_dict(r) for r in await scrape_search(sample_query, 1)]
    assert isinstance(results, list)
    for r in results:
        _validate(r, SEARCH_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_shop():
    sample_shop = os.environ.get("DEPOP_SAMPLE_SHOP", "depopofficial")
    shop = to_dict(await scrape_shop(sample_shop))
    _validate(shop, SHOP_SCHEMA)
