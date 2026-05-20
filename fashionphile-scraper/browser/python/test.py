"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from fashionphile import scrape_products, scrape_search

pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)

# Mirrors the upstream reference/fashionphile-scraper test.py verbatim.
product_schema = {
    "id": {"type": "integer"},
    "sku": {"type": "string"},
    "title": {"type": "string"},
    "slug": {"type": "string"},
    "price": {"type": "integer"},
    "renewDays": {"type": "integer"},
    "discountedPrice": {"type": "integer"},
    "discountEnabled": {"type": "integer"},
    "discountedTier": {"type": "integer"},
    "madeAvailableAt": {"type": "string"},
    "approvedAt": {"type": "string"},
    "madeAvailableAtUTC": {"type": "string"},
    "year": {"type": "integer", "nullable": True},
    "condition": {"type": "string"},
    "authenticCta": {"type": "string"},
    "brand": {
        "type": "list",
        "schema": {
            "type": "dict",
            "schema": {
                "id": {"type": "integer"},
                "name": {"type": "string"},
                "slug": {"type": "string"},
                "type": {"type": "string"},
                "description": {"type": "string"},
                "title": {"type": "string"},
            },
        },
    },
}

search_schema = {
    "brand_name": {"type": "string"},
    "product_name": {"type": "string"},
    "condition": {"type": "string"},
    "discounted_price": {"type": "integer"},
    "price": {"type": "integer"},
    "id": {"type": "integer"},
}

def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_products():
    urls = os.environ.get(
        "FASHIONPHILE_SAMPLE_PRODUCT_URLS",
        "https://www.fashionphile.com/p/bottega-veneta-nappa-twisted-padded-intrecciato-curve-slide-sandals-36-black-1048096",
    ).split(",")
    products = await scrape_products([u.strip() for u in urls if u.strip()])
    assert len(products) >= 1
    for p in products:
        _validate(p, product_schema)

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    url = os.environ.get(
        "FASHIONPHILE_SAMPLE_SEARCH_URL", "https://www.fashionphile.com/shop/discounted/all"
    )
    results = await scrape_search(url, max_pages=1)
    assert len(results) >= 1
    for r in results:
        _validate(r, search_schema)
