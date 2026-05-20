"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from walmart import scrape_products, scrape_search, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


PRODUCT_WRAPPER_SCHEMA = {
    "product": {"type": "dict", "required": True},
    "reviews": {"type": "dict", "nullable": True},
}

SEARCH_ITEM_SCHEMA = {
    "id": {"type": "string", "nullable": True},
    "name": {"type": "string", "nullable": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_products():
    urls_env = os.environ.get("WALMART_SAMPLE_PRODUCT_URLS")
    urls = (
        [u.strip() for u in urls_env.split(",") if u.strip()]
        if urls_env
        else ["https://www.walmart.com/ip/1736740710"]
    )
    products = [to_dict(p) for p in await scrape_products(urls)]
    assert len(products) >= 1
    for p in products:
        if "error" in p:
            continue
        _validate(p, PRODUCT_WRAPPER_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    sample_query = os.environ.get("WALMART_SAMPLE_QUERY", "laptop")
    results = [to_dict(r) for r in await scrape_search(query=sample_query, sort="best_seller", max_pages=1)]
    assert len(results) >= 1
    for r in results:
        _validate(r, SEARCH_ITEM_SCHEMA)
