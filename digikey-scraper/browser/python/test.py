"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from digikey import scrape_product, scrape_search, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


PRODUCT_SCHEMA = {
    "digikeyPartNumber": {"type": "string", "required": True, "minlength": 1},
    "manufacturerPartNumber": {"type": "string", "required": True, "minlength": 1},
    "manufacturer": {"type": "string", "required": True, "minlength": 1},
    "title": {"type": "string", "required": True, "minlength": 1},
    "description": {"type": "string", "nullable": True},
    "detailedDescription": {"type": "string", "nullable": True},
    "datasheetUrl": {"type": "string", "nullable": True},
    "productUrl": {"type": "string", "required": True},
    "imageUrl": {"type": "string", "nullable": True},
    "media": {"type": "list", "required": True},
    "breadcrumb": {"type": "list", "required": True},
    "attributes": {"type": "list", "required": True},
    "pricing": {"type": "list", "required": True},
    "stock": {"type": "dict", "required": True},
    "isActive": {"type": "boolean", "required": True},
    "isUnavailable": {"type": "boolean", "required": True},
}

SEARCH_SCHEMA = {
    "id": {"type": "string", "required": True},
    "categoryName": {"type": "string", "required": True, "minlength": 1},
    "parentCategory": {"type": "string", "nullable": True},
    "productCount": {"type": "string", "required": True},
    "categoryUrl": {"type": "string", "required": True, "minlength": 1},
    "imageUrl": {"type": "string", "nullable": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_product():
    sample = os.environ.get(
        "DIGIKEY_SAMPLE_PRODUCT_URL",
        "https://www.digikey.com/en/products/detail/texas-instruments/LM358N/277042",
    )
    product = to_dict(await scrape_product(sample))
    _validate(product, PRODUCT_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    sample = os.environ.get("DIGIKEY_SAMPLE_QUERY", "LM358")
    results = [to_dict(r) for r in await scrape_search(sample, 1)]
    assert len(results) >= 1, "expected at least one search result"
    for r in results:
        _validate(r, SEARCH_SCHEMA)
