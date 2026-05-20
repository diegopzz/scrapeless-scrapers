"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from zara import scrape_product, scrape_search, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


PRODUCT_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "url": {"type": "string", "required": True, "minlength": 1},
    "name": {"type": "string", "required": True},
    "brand": {"type": "string", "required": True},
    "description": {"type": "string", "nullable": True},
    "price": {"type": "float", "nullable": True},
    "priceCurrency": {"type": "string", "nullable": True},
    "availability": {"type": "string", "nullable": True},
    "images": {"type": "list", "required": True, "schema": {"type": "string"}},
    "color": {"type": "string", "nullable": True},
    "category": {"type": "string", "nullable": True},
}

SEARCH_SCHEMA = {
    "id": {"type": "string", "required": True},
    "url": {"type": "string", "required": True},
    "name": {"type": "string", "required": True},
    "image": {"type": "string", "nullable": True},
    "price": {"type": "float", "nullable": True},
    "priceCurrency": {"type": "string", "nullable": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_product():
    urls_env = os.environ.get("ZARA_SAMPLE_PRODUCT_URLS")
    urls = [u.strip() for u in urls_env.split(",")] if urls_env else [
        "https://www.zara.com/us/en/zw-collection-fitted-plaid-jacket-p02784381.html",
    ]
    products = [to_dict(p) for p in await scrape_product(urls)]
    assert len(products) >= 1
    for p in products:
        _validate(p, PRODUCT_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    sample = os.environ.get("ZARA_SAMPLE_SEARCH_URL", "https://www.zara.com/us/en/woman-blazers-l1055.html")
    results = [to_dict(r) for r in await scrape_search(sample, max_pages=1)]
    assert isinstance(results, list)
    for r in results:
        _validate(r, SEARCH_SCHEMA)
