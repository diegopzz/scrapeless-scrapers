"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest

from immowelt import scrape_properties, scrape_search

pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)

SAMPLE_SEARCH = "https://www.immowelt.de/classified-search?distributionTypes=Buy&estateTypes=Apartment&locations=AD08DE6345"
SAMPLE_PROPERTIES = ["https://www.immowelt.de/expose/k2ag632"]

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    results = await scrape_search(SAMPLE_SEARCH, max_scrape_pages=1)
    assert isinstance(results, list)
    assert len(results) >= 1
    for r in results:
        assert isinstance(r, dict)

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_properties():
    results = await scrape_properties(SAMPLE_PROPERTIES)
    assert len(results) >= 1
    for r in results:
        assert isinstance(r, dict)
        # the upstream reference projects {sections, id, brand, tags, contactSections}
        for key in ("sections", "id"):
            assert key in r
