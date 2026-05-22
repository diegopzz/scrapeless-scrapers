"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from flipkart import scrape_product, scrape_search, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


PRODUCT_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "name": {"type": "string", "required": True, "minlength": 1},
    "brand": {"type": "string", "nullable": True},
    "description": {"type": "string", "nullable": True},
    "image": {"type": "string", "nullable": True},
    "price": {"type": "float", "nullable": True},
    "priceCurrency": {"type": "string", "nullable": True},
    "availability": {"type": "string", "nullable": True},
    "ratingValue": {"type": "float", "nullable": True},
    "reviewCount": {"type": "integer", "nullable": True},
    "url": {"type": "string", "required": True, "minlength": 1},
    "breadcrumb": {"type": "list", "required": True},
}

SEARCH_RESULT_SCHEMA = {
    "id": {"type": "string", "nullable": True},
    "name": {"type": "string", "required": True, "minlength": 1},
    "url": {"type": "string", "nullable": True},
    "image": {"type": "string", "nullable": True},
    "price": {"type": "float", "nullable": True},
    "priceCurrency": {"type": "string", "nullable": True},
    "ratingValue": {"type": "float", "nullable": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_product():
    sample = os.environ.get(
        "FK_SAMPLE_PRODUCT_URL",
        "https://www.flipkart.com/apple-iphone-16-white-128-gb/p/itm7c0281cd247be",
    )
    product = to_dict(await scrape_product(sample))
    _validate(product, PRODUCT_SCHEMA)
    assert product["id"], "id must be non-empty"
    assert product["name"], "name must be non-empty"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    sample = os.environ.get(
        "FK_SAMPLE_SEARCH_URL",
        "https://www.flipkart.com/search?q=iphone+16&marketplace=FLIPKART",
    )
    results = to_dict(await scrape_search(sample))
    assert isinstance(results, list), "search must return a list"
    assert len(results) > 0, "search must return at least one result"
    _validate(results[0], SEARCH_RESULT_SCHEMA)
