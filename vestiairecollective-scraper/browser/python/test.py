"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from vestiairecollective import scrape_products, scrape_search

pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)

# Mirrors the upstream reference/vestiairecollective-scraper test.py verbatim.
product_schema = {
    "id": {"type": "string"},
    "type": {"type": "string"},
    "name": {"type": "string"},
    "price": {
        "type": "dict",
        "schema": {
            "currency": {"type": "string"},
            "cents": {"type": "integer"},
            "formatted": {"type": "string"},
        },
    },
    "description": {"type": "string"},
    "likeCount": {"type": "integer"},
    "path": {"type": "string"},
    "measurementFormatted": {"type": "string"},
    "unit": {"type": "string"},
    "metadata": {
        "type": "dict",
        "schema": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "keywords": {"type": "string"},
        },
    },
    "warehouse": {
        "type": "dict",
        "schema": {
            "name": {"type": "string"},
            "localizedName": {"type": "string"},
        },
    },
    "brand": {
        "type": "dict",
        "schema": {
            "id": {"type": "string"},
            "type": {"type": "string"},
            "name": {"type": "string"},
            "localizedName": {"type": "string"},
        },
    },
}

search_schema = {
    "id": {"type": "integer"},
    "name": {"type": "string"},
    "description": {"type": "string"},
    "country": {"type": "string"},
    "likes": {"type": "integer"},
    "link": {"type": "string"},
    "pictures": {"type": "list", "schema": {"type": "string"}},
    "price": {
        "type": "dict",
        "schema": {
            "cents": {"type": "integer"},
            "currency": {"type": "string"},
        },
    },
    "seller": {
        "type": "dict",
        "schema": {
            "id": {"type": "integer"},
            "firstname": {"type": "string"},
            "badge": {"type": "string"},
            "picture": {"type": "string"},
            "isOfficialStore": {"type": "boolean"},
        },
    },
    "sold": {"type": "boolean"},
    "stock": {"type": "boolean"},
    "shouldBeGone": {"type": "boolean"},
    "createdAt": {"type": "integer"},
    "universeId": {"type": "integer"},
    "dutyFree": {"type": "boolean"},
}

def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_products():
    urls = os.environ.get(
        "VESTIAIRE_SAMPLE_PRODUCT_URLS",
        "https://us.vestiairecollective.com/men-accessories/watches/patek-philippe/gold-yellow-gold-patek-philippe-watch-51820408.shtml",
    ).split(",")
    products = await scrape_products([u.strip() for u in urls if u.strip()])
    assert len(products) >= 1
    for p in products:
        _validate(p, product_schema)

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    url = os.environ.get(
        "VESTIAIRE_SAMPLE_SEARCH_URL", "https://www.vestiairecollective.com/search/?q=louis+vuitton"
    )
    results = await scrape_search(url, max_pages=1)
    assert len(results) >= 1
    for r in results:
        _validate(r, search_schema)
