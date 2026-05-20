"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from goat import scrape_products, scrape_search

pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)

# Mirrors the upstream reference/goat-scraper test.py verbatim.
product_schema = {
    "brandName": {"type": "string"},
    "color": {"type": "string"},
    "designer": {"type": "string"},
    "details": {"type": "string"},
    "forAuction": {"type": "boolean", "nullable": True},
    "id": {"type": "integer"},
    "internalShot": {"type": "string"},
    "maximumOfferCents": {"type": "integer"},
    "midsole": {"type": "string"},
    "minimumOfferCents": {"type": "integer"},
    "name": {"type": "string"},
    "productCategory": {"type": "string"},
    "productType": {"type": "string"},
    "silhouette": {"type": "string"},
    "sizeBrand": {"type": "string"},
    "sizeRange": {"type": "list", "schema": {"type": "float"}},
    "sku": {"type": "string"},
    "slug": {"type": "string"},
    "specialDisplayPriceCents": {"type": "integer"},
    "specialType": {"type": "string"},
    "status": {"type": "string"},
    "upperMaterial": {"type": "string"},
}

search_schema = {
    "id": {"type": "string", "required": True},
    "status": {"type": "string"},
    "slug": {"type": "string"},
    "title": {"type": "string"},
    "pictureUrl": {"type": "string"},
    "inStock": {"type": "boolean"},
    "category": {"type": "string"},
    "productType": {"type": "string"},
    "brandName": {"type": "string"},
    "gender": {"type": "string"},
    "releaseDate": {
        "type": "dict",
        "nullable": True,
        "schema": {"seconds": {"type": "integer"}, "nanos": {"type": "integer"}},
    },
    "localizedRetailPriceCents": {
        "type": "dict",
        "nullable": True,
        "schema": {"amountCents": {"type": "integer"}, "currency": {"type": "string"}},
    },
    "variantsList": {
        "type": "list",
        "schema": {
            "type": "dict",
            "schema": {
                "productCondition": {"type": "integer"},
                "boxCondition": {"type": "integer"},
                "size": {
                    "type": "dict",
                    "schema": {
                        "gender": {"type": "integer"},
                        "sizeUnit": {"type": "integer"},
                        "size": {"type": "string"},
                        "displayName": {"type": "string"},
                    },
                },
                "localizedLowestPriceCents": {
                    "type": "dict",
                    "schema": {"amountCents": {"type": "integer"}, "currency": {"type": "string"}},
                },
            },
        },
    },
}

def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_products():
    urls = os.environ.get(
        "GOAT_SAMPLE_PRODUCT_URLS",
        "https://www.goat.com/sneakers/air-jordan-3-retro-white-cement-reimagined-dn3707-100",
    ).split(",")
    products = await scrape_products([u.strip() for u in urls if u.strip()])
    assert len(products) >= 1
    for p in products:
        _validate(p, product_schema)

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    query = os.environ.get("GOAT_SAMPLE_QUERY", "pumar dark")
    results = await scrape_search(query, max_pages=1)
    assert len(results) >= 1
    for r in results:
        _validate(r, search_schema)
