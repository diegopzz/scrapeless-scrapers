"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from aliexpress import (
    find_aliexpress_products,
    scrape_product,
    scrape_product_reviews,
    scrape_search,
    to_dict,
)


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


PRODUCT_SCHEMA = {
    "info": {"type": "dict", "required": True},
    "pricing": {"type": "dict", "required": True},
    "specifications": {"type": "list", "required": True},
    "delivery": {"type": "string", "nullable": True},
    "faqs": {"type": "list", "required": True},
}

INFO_SCHEMA = {
    "name": {"type": "string", "nullable": True},
    "productId": {"required": True},
    "link": {"type": "string", "required": True},
    "media": {"type": "list", "required": True, "schema": {"type": "string"}},
    "rate": {"type": "integer", "nullable": True},
    "reviews": {"type": "integer", "nullable": True},
    "soldCount": {"type": "integer", "required": True},
    "availableCount": {"type": "integer", "required": True},
}

PRICING_SCHEMA = {
    "priceCurrency": {"type": "string", "required": True},
    "price": {"type": "float", "nullable": True},
    "originalPrice": {"required": True},
    "discount": {"type": "string", "required": True},
}

REVIEWS_SCHEMA = {
    "reviews": {"type": "list", "required": True},
    "evaluation_stats": {"type": "dict", "required": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    sample = os.environ.get(
        "ALIEXPRESS_SAMPLE_SEARCH_URL",
        "https://www.aliexpress.com/w/wholesale-drills.html?catId=0&SearchText=drills",
    )
    results = [to_dict(r) for r in await scrape_search(sample, max_pages=1)]
    assert len(results) >= 1
    for r in results:
        assert isinstance(r, dict)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_product():
    sample = os.environ.get(
        "ALIEXPRESS_SAMPLE_PRODUCT_URL", "https://www.aliexpress.com/item/3256807619226115.html"
    )
    product = to_dict(await scrape_product(sample))
    _validate(product, PRODUCT_SCHEMA)
    _validate(product["info"], INFO_SCHEMA)
    _validate(product["pricing"], PRICING_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_reviews():
    pid = os.environ.get("ALIEXPRESS_SAMPLE_REVIEW_PRODUCT_ID", "1005006717259012")
    data = to_dict(await scrape_product_reviews(pid, max_scrape_pages=1))
    _validate(data, REVIEWS_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_category():
    sample = os.environ.get(
        "ALIEXPRESS_SAMPLE_CATEGORY_URL",
        "https://www.aliexpress.com/category/5090301/cellphones.html",
    )
    products = [to_dict(p) for p in await find_aliexpress_products(sample, max_pages=1)]
    assert isinstance(products, list)
