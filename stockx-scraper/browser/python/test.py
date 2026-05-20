"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from stockx import scrape_product, scrape_search

pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)

# Reusable nested fragment matching the upstream reference's _market_schema
_market_schema = {
    "type": "dict",
    "schema": {
        "bidAskData": {
            "type": "dict",
            "schema": {
                "lowestAsk": {"type": "integer", "nullable": True},
                "numberOfAsks": {"type": "integer", "nullable": True},
                "highestBid": {"type": "integer", "nullable": True},
                "numberOfBids": {"type": "integer", "nullable": True},
            },
        },
        "salesInformation": {
            "type": "dict",
            "schema": {
                "lastSale": {"type": "integer"},
                "salesLast72Hours": {"type": "integer"},
            },
        },
        "statistics": {
            "type": "dict",
            "schema": {
                "lastSale": {
                    "type": "dict",
                    "schema": {
                        "amount": {"type": "integer"},
                        "changePercentage": {"type": "float"},
                        "changeValue": {"type": "integer"},
                        "sameFees": {"type": "boolean"},
                    },
                },
            },
        },
    },
}

product_schema = {
    "id": {"type": "string"},
    "listingType": {"type": "string"},
    "deleted": {"type": "boolean"},
    "gender": {"type": "string"},
    "title": {"type": "string"},
    "brand": {"type": "string"},
    "description": {"type": "string"},
    "model": {"type": "string"},
    "variants": {
        "type": "list",
        "schema": {
            "type": "dict",
            "schema": {
                "id": {"type": "string"},
                "market": _market_schema,
            },
        },
    },
    "market": _market_schema,
    "pricing": {
        "type": "dict",
        "schema": {
            "minimumBid": {"type": "float"},
            "market": {
                "type": "dict",
                "schema": {
                    "state": {
                        "type": "dict",
                        "schema": {
                            "lowestAsk": {
                                "type": "dict",
                                "schema": {
                                    "amount": {"type": "float"},
                                    "currency": {"type": "string"},
                                },
                            },
                            "highestBid": {
                                "type": "dict",
                                "schema": {"amount": {"type": "float"}},
                            },
                            "numberOfAsks": {"type": "integer"},
                            "numberOfBids": {"type": "integer"},
                        },
                    },
                },
            },
            "variants": {
                "type": "list",
                "schema": {
                    "type": "dict",
                    "schema": {"id": {"type": "string"}},
                },
            },
        },
    },
}

search_schema = {
    "id": {"type": "string"},
    "name": {"type": "string"},
    "urlKey": {"type": "string"},
    "title": {"type": "string"},
    "brand": {"type": "string"},
    "description": {"type": "string"},
    "model": {"type": "string"},
}

def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_product():
    url = os.environ.get(
        "STOCKX_SAMPLE_PRODUCT_URL", "https://stockx.com/nike-x-stussy-bucket-hat-black"
    )
    product = await scrape_product(url)
    _validate(product, product_schema)

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    url = os.environ.get("STOCKX_SAMPLE_SEARCH_URL", "https://stockx.com/search?s=nike")
    results = await scrape_search(url, max_pages=1)
    assert len(results) >= 1
    for r in results:
        _validate(r, search_schema)
