"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from yelp import scrape_pages, scrape_reviews, scrape_search


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


BUSINESS_SCHEMA = {
    "name": {"type": "string", "required": True, "minlength": 1},
    "website": {"type": "string"},
    "phone": {"type": "string"},
    "address": {"type": "string"},
    "logo": {"type": "string"},
    "claim_status": {"type": "string"},
    "open_hours": {"type": "dict", "required": True},
}

REVIEW_SCHEMA = {
    "encid": {"type": "string", "required": True, "minlength": 1},
    "text": {"type": "dict", "required": True},
    "rating": {"type": "integer", "required": True, "min": 1, "max": 5},
    "feedback": {"type": "dict", "required": True},
    "author": {"type": "dict", "required": True},
    "business": {"type": "dict", "required": True},
    "createdAt": {"type": "string", "required": True},
}

SEARCH_SCHEMA = {
    "bizId": {"type": "string", "required": True, "minlength": 1},
    "searchResultBusiness": {"type": "dict", "required": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_pages():
    sample_url = os.environ.get(
        "YELP_SAMPLE_URL", "https://www.yelp.com/biz/vons-1000-spirits-seattle-4"
    )
    pages = await scrape_pages([sample_url])
    assert len(pages) == 1
    _validate(pages[0], BUSINESS_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_reviews():
    sample_url = os.environ.get(
        "YELP_SAMPLE_URL", "https://www.yelp.com/biz/vons-1000-spirits-seattle-4"
    )
    reviews = await scrape_reviews(sample_url, max_reviews=10)
    assert len(reviews) >= 1
    for r in reviews:
        _validate(r, REVIEW_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    keyword = os.environ.get("YELP_SAMPLE_KEYWORD", "plumbers")
    location = os.environ.get("YELP_SAMPLE_LOCATION", "Seattle, WA")
    results = await scrape_search(keyword=keyword, location=location, max_pages=1)
    assert len(results) >= 1, "expected at least one search result"
    for r in results:
        _validate(r, SEARCH_SCHEMA)
