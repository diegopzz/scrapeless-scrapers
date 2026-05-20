"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from lazada import scrape_product, scrape_search, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


PRODUCT_SCHEMA = {
    "id": {"type": "string", "required": True},
    "url": {"type": "string", "required": True},
    "title": {"type": "string", "required": True},
    "brand": {"type": "string", "nullable": True},
    "price": {"type": "string", "nullable": True},
    "originalPrice": {"type": "string", "nullable": True},
    "discount": {"type": "string", "nullable": True},
    "currency": {"type": "string", "nullable": True},
    "rating": {"type": "float", "nullable": True},
    "reviews": {"type": "integer", "nullable": True},
    "images": {"type": "list", "required": True, "schema": {"type": "string"}},
    "seller": {"type": "string", "nullable": True},
    "sellerUrl": {"type": "string", "nullable": True},
    "availability": {"type": "string", "nullable": True},
    "description": {"type": "string", "nullable": True},
    "categories": {"type": "list", "required": True, "schema": {"type": "string"}},
}

SEARCH_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "title": {"type": "string", "required": True},
    "url": {"type": "string", "required": True},
    "image": {"type": "string", "nullable": True},
    "price": {"type": "string", "nullable": True},
    "originalPrice": {"type": "string", "nullable": True},
    "discount": {"type": "string", "nullable": True},
    "rating": {"type": "float", "nullable": True},
    "reviews": {"type": "integer", "nullable": True},
    "location": {"type": "string", "nullable": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_product():
    sample = os.environ.get(
        "LAZADA_SAMPLE_PRODUCT_URL",
        "https://www.lazada.sg/products/pdp-i3529149697.html",
    )
    product = to_dict(await scrape_product(sample))
    _validate(product, PRODUCT_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    sample_query = os.environ.get("LAZADA_SAMPLE_QUERY", "iphone case")
    results = [to_dict(r) for r in await scrape_search(sample_query, 1)]
    assert isinstance(results, list)
    for r in results:
        _validate(r, SEARCH_SCHEMA)
