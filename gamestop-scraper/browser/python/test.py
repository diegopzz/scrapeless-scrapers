"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from gamestop import scrape_product, scrape_search, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


PRODUCT_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "name": {"type": "string", "required": True, "minlength": 1},
    "brand": {"type": "string", "nullable": True},
    "description": {"type": "string", "nullable": True},
    "platform": {"type": "string", "nullable": True},
    "category": {"type": "string", "nullable": True},
    "genre": {"type": "string", "nullable": True},
    "contentRating": {"type": "string", "nullable": True},
    "producer": {"type": "string", "nullable": True},
    "publisher": {"type": "string", "nullable": True},
    "image": {"type": "string", "nullable": True},
    "url": {"type": "string", "required": True, "minlength": 1},
    "price": {"type": "string", "nullable": True},
    "priceCurrency": {"type": "string", "nullable": True},
    "availability": {"type": "string", "nullable": True},
    "offers": {"type": "list", "required": True},
    "breadcrumb": {"type": "list", "required": True},
}

SEARCH_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "name": {"type": "string", "required": True, "minlength": 1},
    "url": {"type": "string", "required": True, "minlength": 1},
    "price": {"type": "string", "nullable": True},
    "salePrice": {"type": "string", "nullable": True},
    "platform": {"type": "string", "nullable": True},
    "image": {"type": "string", "nullable": True},
    "ratingPercent": {"type": "string", "nullable": True},
    "ratingCount": {"type": "string", "nullable": True},
    "available": {"type": "boolean", "nullable": True},
    "isDigital": {"type": "boolean", "nullable": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_product():
    sample = os.environ.get(
        "GAMESTOP_SAMPLE_PRODUCT_URL",
        "https://www.gamestop.com/video-games/nintendo-switch/products/tomodachi-life-living-the-dream---nintendo-switch/440814.html",
    )
    product = to_dict(await scrape_product(sample))
    _validate(product, PRODUCT_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    sample = os.environ.get("GAMESTOP_SAMPLE_QUERY", "zelda")
    results = [to_dict(r) for r in await scrape_search(sample, 1)]
    assert len(results) >= 1, "expected at least one search result"
    for r in results:
        _validate(r, SEARCH_SCHEMA)
