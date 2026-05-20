"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from ebay import scrape_product, scrape_search, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


SEARCH_SCHEMA = {
    "url": {"type": "string", "nullable": True},
    "title": {"type": "string", "nullable": True},
    "price": {"type": "string", "nullable": True},
    "shipping": {"type": "string", "nullable": True},
    "location": {"type": "string", "nullable": True},
    "subtitles": {"type": "string", "nullable": True},
    "photo": {"type": "string", "nullable": True},
    "rating": {"type": "string", "nullable": True},
    "rating_count": {"type": "integer", "nullable": True},
}

PRODUCT_SCHEMA = {
    "url": {"type": "string", "required": True},
    "id": {"type": "string", "required": True},
    "price_original": {"type": "string", "nullable": True},
    "price_converted": {"type": "string", "nullable": True},
    "name": {"type": "string", "nullable": True},
    "seller_name": {"type": "string", "nullable": True},
    "seller_url": {"type": "string", "nullable": True},
    "photos": {"type": "list", "required": True, "schema": {"type": "string"}},
    "description_url": {"type": "string", "nullable": True},
    "features": {"type": "dict", "required": True},
    "variants": {"type": "list", "required": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    sample = os.environ.get(
        "EBAY_SAMPLE_SEARCH_URL",
        "https://www.ebay.com/sch/i.html?_from=R40&_nkw=iphone&_sacat=0&_ipg=60",
    )
    results = [to_dict(r) for r in await scrape_search(sample, max_pages=1)]
    assert len(results) >= 1
    for r in results:
        _validate(r, SEARCH_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_product():
    sample = os.environ.get("EBAY_SAMPLE_PRODUCT_URL", "https://www.ebay.com/itm/177439887865")
    product = to_dict(await scrape_product(sample))
    _validate(product, PRODUCT_SCHEMA)
