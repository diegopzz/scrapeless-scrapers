"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from xbox import scrape_product, scrape_search, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


PRODUCT_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "name": {"type": "string", "required": True, "minlength": 1},
    "description": {"type": "string", "nullable": True},
    "url": {"type": "string", "required": True, "minlength": 1},
    "image": {"type": "string", "nullable": True},
    "publisher": {"type": "string", "nullable": True},
    "developer": {"type": "string", "nullable": True},
    "brand": {"type": "string", "nullable": True},
    "genre": {"type": "list", "required": True},
    "platforms": {"type": "list", "required": True},
    "contentRating": {"type": "string", "nullable": True},
    "releaseDate": {"type": "string", "nullable": True},
    "ratingValue": {"type": "float", "nullable": True},
    "ratingCount": {"type": "integer", "nullable": True},
    "price": {"type": "string", "nullable": True},
    "priceCurrency": {"type": "string", "nullable": True},
    "availability": {"type": "string", "nullable": True},
    "isFree": {"type": "boolean", "nullable": True},
    "featureList": {"type": "string", "nullable": True},
    "videos": {"type": "list", "required": True},
}

SEARCH_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "slug": {"type": "string", "required": True, "minlength": 1},
    "name": {"type": "string", "required": True, "minlength": 1},
    "url": {"type": "string", "required": True, "minlength": 1},
    "image": {"type": "string", "nullable": True},
    "badge": {"type": "string", "nullable": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_product():
    sample = os.environ.get(
        "XBOX_SAMPLE_PRODUCT_URL",
        "https://www.xbox.com/en-us/games/store/marvel-rivals/9N8PMW7QMD3D",
    )
    product = to_dict(await scrape_product(sample))
    _validate(product, PRODUCT_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    sample = os.environ.get("XBOX_SAMPLE_QUERY", "all")
    results = [to_dict(r) for r in await scrape_search(sample, 1)]
    assert len(results) >= 1, "expected at least one search result"
    for r in results:
        _validate(r, SEARCH_SCHEMA)
