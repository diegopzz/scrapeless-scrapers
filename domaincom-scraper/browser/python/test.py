"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from domaincom import scrape_properties, scrape_search


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


# Listed property pages emit componentProps; sold/property-profile pages emit
# the pageProps Apollo shape. Tests accept either via allow_unknown + minimal
# required fields.

PROPERTY_LISTED_SCHEMA = {
    "url": {"type": "string", "required": True},
    "listingId": {"nullable": True},
    "suburb": {"type": "string", "nullable": True},
    "postcode": {"type": "string", "nullable": True},
    "agents": {"type": "list", "nullable": True},
    "gallery": {"type": "list", "nullable": True},
}

SEARCH_ITEM_SCHEMA = {
    "id": {"required": True, "nullable": True},
    "listingType": {"type": "string", "nullable": True},
    "listingModel": {"type": "dict", "nullable": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_properties():
    urls = [
        os.environ.get(
            "DOMAINCOM_SAMPLE_URL",
            "https://www.domain.com.au/610-399-bourke-street-melbourne-vic-3000-2018835548",
        )
    ]
    properties = await scrape_properties(urls)
    assert len(properties) >= 1, "expected at least one property"
    for p in properties:
        _validate(p, PROPERTY_LISTED_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    url = os.environ.get(
        "DOMAINCOM_SAMPLE_SEARCH",
        "https://www.domain.com.au/sale/melbourne-vic-3000/",
    )
    results = await scrape_search(url, max_scrape_pages=1)
    assert len(results) >= 1, "expected at least one search result"
    for r in results:
        _validate(r, SEARCH_ITEM_SCHEMA)
