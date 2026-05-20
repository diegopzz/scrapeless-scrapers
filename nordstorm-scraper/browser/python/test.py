"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from nordstorm import scrape_products, scrape_search

pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)

PRODUCT_SCHEMA = {
    "id": {"required": True},
    "title": {"type": "string", "required": True, "minlength": 1},
    "type": {"type": "string", "nullable": True},
    "typeParent": {"type": "string", "nullable": True},
    "ageGroups": {"type": "list", "nullable": True},
    "reviewAverageRating": {"nullable": True},
    "numberOfReviews": {"nullable": True},
    "brand": {"type": "dict", "nullable": True},
    "description": {"type": "string", "nullable": True},
    "features": {"type": "list", "nullable": True},
    "gender": {"type": "string", "nullable": True},
    "isAvailable": {"type": "boolean", "nullable": True},
    "media": {"type": "list", "required": True},
    "variants": {"type": "dict", "required": True},
}

# Search products are raw `productsById` entries — same key namespace but
# `parse_product` is NOT applied (the upstream reference upstream emits them raw).
SEARCH_PRODUCT_SCHEMA = {
    "id": {"required": True},
}

def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_products():
    urls = [
        os.environ.get(
            "NORDSTORM_SAMPLE_URL",
            "https://www.nordstrom.com/s/nike-air-max-90-sneaker-men/6549520",
        )
    ]
    products = await scrape_products(urls)
    assert len(products) >= 1, "expected at least one product"
    for p in products:
        _validate(p, PRODUCT_SCHEMA)

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    url = os.environ.get(
        "NORDSTORM_SAMPLE_SEARCH",
        "https://www.nordstrom.com/sr?origin=keywordsearch&keyword=indigo",
    )
    results = await scrape_search(url, max_pages=1)
    assert len(results) >= 1, "expected at least one search result"
    for r in results:
        _validate(r, SEARCH_PRODUCT_SCHEMA)
