"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest

from homegate import scrape_properties, scrape_search


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


SAMPLE_PROPERTIES = ["https://www.homegate.ch/rent/4002086534"]
SAMPLE_SEARCH = "https://www.homegate.ch/rent/real-estate/city-bern/matching-list"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_properties():
    results = await scrape_properties(SAMPLE_PROPERTIES)
    assert len(results) >= 1
    for r in results:
        assert isinstance(r, dict)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    results = await scrape_search(SAMPLE_SEARCH, scrape_all_pages=False, max_scrape_pages=1)
    assert isinstance(results, list)
    assert len(results) >= 1
    for r in results:
        assert isinstance(r, dict)
