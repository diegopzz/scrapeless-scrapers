"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from etsy import scrape_product, scrape_search, scrape_shop

pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)

# Field names mirror the upstream reference/etsy-scraper test.py verbatim.
search_schema = {
    "productLink": {"type": "string"},
    "productTitle": {"type": "string"},
    "productImage": {"type": "string"},
    "seller": {"type": "string", "nullable": True},
    "listingType": {"type": "string"},
    "productRate": {"type": "float", "nullable": True},
    "numberOfReviews": {"type": "integer", "nullable": True},
    "freeShipping": {"type": "string"},
    "productPrice": {"type": "float"},
    "priceCurrency": {"type": "string"},
    "originalPrice": {"type": "string", "nullable": True},
    "discount": {"type": "string"},
}

product_schema = {
    "@type": {"type": "string"},
    "@context": {"type": "string"},
    "url": {"type": "string"},
    "name": {"type": "string"},
    "sku": {"type": "string"},
    "gtin": {"type": "string"},
    "description": {"type": "string"},
    "category": {"type": "string"},
    "logo": {"type": "string"},
    "material": {"type": "string"},
    "reviews": {
        "type": "list",
        "schema": {
            "type": "dict",
            "schema": {
                "@type": {"type": "string"},
                "datePublished": {"type": "string"},
                "reviewBody": {"type": "string"},
            },
        },
    },
}

shop_schema = {
    "@type": {"type": "string"},
    "@context": {"type": "string"},
    "url": {"type": "string"},
    "itemListElement": {
        "type": "list",
        "schema": {
            "type": "dict",
            "schema": {
                "@context": {"type": "string"},
                "@type": {"type": "string"},
                "image": {"type": "string"},
                "name": {"type": "string"},
                "url": {"type": "string"},
                "brand": {
                    "type": "dict",
                    "schema": {
                        "@type": {"type": "string"},
                        "name": {"type": "string"},
                    },
                },
                "offers": {
                    "type": "dict",
                    "schema": {
                        "@type": {"type": "string"},
                        "price": {"type": "string"},
                        "priceCurrency": {"type": "string"},
                    },
                },
                "position": {"type": "integer"},
            },
        },
    },
}

def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    url = os.environ.get(
        "ETSY_SAMPLE_SEARCH_URL", "https://www.etsy.com/search?q=wood+laptop+stand"
    )
    results = await scrape_search(url, max_pages=1)
    assert len(results) >= 1, "expected at least one search result"
    for r in results:
        _validate(r, search_schema)

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_product():
    urls = os.environ.get(
        "ETSY_SAMPLE_PRODUCT_URLS", "https://www.etsy.com/listing/1552627931"
    ).split(",")
    products = await scrape_product([u.strip() for u in urls if u.strip()])
    assert len(products) >= 1
    for p in products:
        _validate(p, product_schema)

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_shop():
    urls = os.environ.get(
        "ETSY_SAMPLE_SHOP_URLS", "https://www.etsy.com/shop/FalkelDesign"
    ).split(",")
    shops = await scrape_shop([u.strip() for u in urls if u.strip()])
    assert len(shops) >= 1
    for s in shops:
        _validate(s, shop_schema)
