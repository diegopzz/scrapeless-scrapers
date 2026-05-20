"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from bing import scrape_keywords, scrape_search, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


SEARCH_SCHEMA = {
    "position": {"type": "integer", "required": True, "min": 1},
    "title": {"type": "string", "required": True, "minlength": 1},
    "url": {"type": "string", "required": True, "minlength": 1},
    "origin": {"type": "string", "required": False},
    "domain": {"type": "string", "required": True},
    "description": {"type": "string", "required": False},
    "date": {"type": "string", "required": False},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    query = os.environ.get("BING_SAMPLE_QUERY", "web scraping emails")
    results = to_dict(await scrape_search(query, max_pages=1))
    assert len(results) >= 1, "expected at least one search result"
    for r in results:
        _validate(r, SEARCH_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_keywords():
    query = os.environ.get("BING_SAMPLE_QUERY", "web scraping emails")
    result = to_dict(await scrape_keywords(query))
    assert isinstance(result, list)
    for kw in result:
        assert isinstance(kw, str) and kw
