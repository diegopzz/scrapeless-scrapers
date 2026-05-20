"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from bunnings import scrape_product, scrape_search, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


PRODUCT_SCHEMA = {
    "sku": {"type": "string", "required": True, "minlength": 1},
    "name": {"type": "string", "required": True, "minlength": 1},
    "brand": {"type": "string", "nullable": True},
    "brandLogo": {"type": "string", "nullable": True},
    "description": {"type": "string", "nullable": True},
    "category": {"type": "string", "nullable": True},
    "image": {"type": "string", "nullable": True},
    "price": {"type": "string", "nullable": True},
    "priceCurrency": {"type": "string", "nullable": True},
    "url": {"type": "string", "required": True, "minlength": 1},
    "warranty": {"type": "string", "nullable": True},
    "breadcrumb": {"type": "list", "required": True},
}

SEARCH_SCHEMA = {
    "sku": {"type": "string", "required": True},
    "title": {"type": "string", "required": True, "minlength": 1},
    "url": {"type": "string", "required": True, "minlength": 1},
    "price": {"type": "string", "nullable": True},
    "image": {"type": "string", "nullable": True},
    "rating": {"type": "string", "nullable": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_product():
    sample = os.environ.get(
        "BUNNINGS_SAMPLE_PRODUCT_URL",
        "https://www.bunnings.com.au/ozito-pxc-18v-cordless-drill-driver-kit-pxddk-250c_p0299323",
    )
    product = to_dict(await scrape_product(sample))
    _validate(product, PRODUCT_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    sample = os.environ.get("BUNNINGS_SAMPLE_QUERY", "cordless drill")
    results = [to_dict(r) for r in await scrape_search(sample, 1)]
    assert len(results) >= 1, "expected at least one search result"
    for r in results:
        _validate(r, SEARCH_SCHEMA)
