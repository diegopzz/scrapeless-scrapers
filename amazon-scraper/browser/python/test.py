"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from amazon import scrape_product, scrape_reviews, scrape_search, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


SEARCH_SCHEMA = {
    "url": {"type": "string", "required": True, "minlength": 1},
    "title": {"type": "string", "required": True, "minlength": 1},
    "price": {"type": "string", "nullable": True},
    "real_price": {"type": "string", "nullable": True},
    "rating": {"type": "float", "nullable": True},
    "rating_count": {"type": "integer", "nullable": True},
}

PRODUCT_SCHEMA = {
    "name": {"type": "string", "required": True, "minlength": 1},
    "asin": {"type": "string", "required": True, "minlength": 1},
    "style": {"type": "string", "nullable": True},
    "description": {"type": "string", "nullable": True},
    "stars": {"type": "string", "nullable": True},
    "rating_count": {"type": "string", "nullable": True},
    "features": {"type": "list", "required": True, "schema": {"type": "string"}},
    "images": {"type": "list", "required": True, "schema": {"type": "string"}},
    "info_table": {"type": "dict", "required": True},
}

REVIEW_SCHEMA = {
    "title": {"type": "string", "nullable": True},
    "text": {"type": "string", "nullable": True},
    "location_and_date": {"type": "string", "nullable": True},
    "verified": {"type": "boolean", "required": True},
    "rating": {"type": "float", "nullable": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    sample = os.environ.get("AMAZON_SAMPLE_SEARCH_URL", "https://www.amazon.com/s?k=kindle")
    results = [to_dict(r) for r in await scrape_search(sample, max_pages=1)]
    assert len(results) >= 1, "expected at least one search result"
    for r in results:
        _validate(r, SEARCH_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_product():
    sample = os.environ.get(
        "AMAZON_SAMPLE_PRODUCT_URL",
        "https://www.amazon.com/PlayStation-5-Console-CFI-1215A01X/dp/B0BCNKKZ91/",
    )
    variants = [to_dict(v) for v in await scrape_product(sample)]
    assert len(variants) >= 1
    for v in variants:
        _validate(v, PRODUCT_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_reviews():
    sample = os.environ.get(
        "AMAZON_SAMPLE_PRODUCT_URL",
        "https://www.amazon.com/PlayStation-5-Console-CFI-1215A01X/dp/B0BCNKKZ91/",
    )
    reviews = [to_dict(r) for r in await scrape_reviews(sample)]
    for r in reviews:
        _validate(r, REVIEW_SCHEMA)
