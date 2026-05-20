"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from zillow import scrape_properties, scrape_search


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


DEFAULT_SEARCH_URL = (
    "https://www.zillow.com/san-francisco-ca/?searchQueryState=%7B%22usersSearchTerm%22%3A%22Nebraska%22"
    "%2C%22mapBounds%22%3A%7B%22north%22%3A37.890669225201904%2C%22east%22%3A-122.26750460986328"
    "%2C%22south%22%3A37.659734343010626%2C%22west%22%3A-122.59915439013672%7D"
    "%2C%22isMapVisible%22%3Atrue%2C%22filterState%22%3A%7B%22sort%22%3A%7B%22value%22%3A%22days%22%7D"
    "%2C%22ah%22%3A%7B%22value%22%3Atrue%7D%7D%2C%22isListVisible%22%3Atrue%2C%22mapZoom%22%3A12"
    "%2C%22regionSelection%22%3A%5B%7B%22regionId%22%3A20330%2C%22regionType%22%3A6%7D%5D"
    "%2C%22pagination%22%3A%7B%7D%7D"
)
DEFAULT_PROPERTY_URL = (
    "https://www.zillow.com/homedetails/661-Lakeview-Ave-San-Francisco-CA-94112/15192198_zpid/"
)


# Mirror Zillow's listResults shape — verbatim field names from
# cat1.searchResults.listResults. Extra keys are allowed.
SEARCH_RESULT_SCHEMA = {
    "zpid": {"type": "string", "required": True},
    "detailUrl": {"type": "string", "required": True},
    "statusType": {"type": "string", "nullable": True},
    "price": {"type": "string", "nullable": True},
    "address": {"type": "string", "nullable": True},
}

# Mirror Zillow's property shape — verbatim from gdpClientCache[*].property
# or hdpApolloPreloadedData ForSale.*.property. Extra keys allowed.
PROPERTY_SCHEMA = {
    "zpid": {"type": "integer", "required": True},
    "streetAddress": {"type": "string", "nullable": True},
    "city": {"type": "string", "nullable": True},
    "state": {"type": "string", "nullable": True},
    "zipcode": {"type": "string", "nullable": True},
    "homeStatus": {"type": "string", "nullable": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    url = os.environ.get("ZILLOW_SEARCH_URL", DEFAULT_SEARCH_URL)
    results = await scrape_search(url, max_scrape_pages=1)
    assert len(results) >= 1, "expected at least one search result"
    for r in results[:5]:
        _validate(r, SEARCH_RESULT_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_properties():
    url = os.environ.get("ZILLOW_PROPERTY_URL", DEFAULT_PROPERTY_URL)
    results = await scrape_properties([url])
    assert len(results) == 1
    _validate(results[0], PROPERTY_SCHEMA)
