"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from redfin import (
    scrape_property_for_rent,
    scrape_property_for_sale,
    scrape_search,
)


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


DEFAULT_SEARCH_URL = (
    "https://www.redfin.com/stingray/api/gis?al=1&include_nearby_homes=true"
    "&market=seattle&num_homes=350&ord=redfin-recommended-asc&page_number=1"
    "&poly=-122.54472%2047.44109%2C-122.11144%2047.44109%2C-122.11144%2047.78363"
    "%2C-122.54472%2047.78363%2C-122.54472%2047.44109&sf=1,2,3,5,6,7&start=0"
    "&status=1&uipt=1,2,3,4,5,6,7,8&v=8&zoomLevel=11"
)
DEFAULT_SALE_URL = "https://www.redfin.com/WA/Seattle/506-E-Howell-St-98122/unit-W303/home/46456"
DEFAULT_RENT_URL = "https://www.redfin.com/WA/Seattle/Onni-South-Lake-Union/apartment/147020546"


# Verbatim Redfin field names — payload.homes entry.
SEARCH_RESULT_SCHEMA = {
    "propertyId": {"type": "integer", "required": True},
    "url": {"type": "string", "required": True},
}

# Verbatim parse_property_for_sale output.
PROPERTY_FOR_SALE_SCHEMA = {
    "address": {"type": "string", "required": True},
    "description": {"type": "string", "nullable": True},
    "price": {"type": "string", "nullable": True},
    "estimatedMonthlyPrice": {"type": "string", "nullable": True},
    "propertyUrl": {"type": "string", "required": True},
    "attachments": {"type": "list", "required": True},
    "details": {"type": "list", "required": True},
    "features": {"type": "dict", "required": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    url = os.environ.get("REDFIN_SEARCH_URL", DEFAULT_SEARCH_URL)
    results = await scrape_search(url)
    assert len(results) >= 1
    for r in results[:5]:
        _validate(r, SEARCH_RESULT_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_property_for_sale():
    url = os.environ.get("REDFIN_SALE_URL", DEFAULT_SALE_URL)
    results = await scrape_property_for_sale([url])
    assert len(results) == 1
    _validate(results[0], PROPERTY_FOR_SALE_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_property_for_rent():
    url = os.environ.get("REDFIN_RENT_URL", DEFAULT_RENT_URL)
    results = await scrape_property_for_rent([url])
    for r in results:
        assert isinstance(r, dict)
