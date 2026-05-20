"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from trustpilot import scrape_company, scrape_reviews, scrape_search


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


COMPANY_SCHEMA = {
    "pageUrl": {"type": "string", "required": True, "minlength": 1},
    "companyDetails": {"type": "dict", "required": True},
    "reviews": {"type": "list", "required": True},
}

SEARCH_SCHEMA = {
    "identifyingName": {"type": "string", "required": True, "minlength": 1},
    "displayName": {"type": "string", "required": True, "minlength": 1},
}

REVIEW_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "consumer": {"type": "dict", "required": True},
    "rating": {"type": "integer", "required": True, "min": 1, "max": 5},
    "dates": {"type": "dict", "required": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_company():
    url = os.environ.get(
        "TRUSTPILOT_SAMPLE_COMPANY_URL", "https://www.trustpilot.com/review/www.bhphotovideo.com"
    )
    companies = await scrape_company([url])
    assert len(companies) == 1
    _validate(companies[0], COMPANY_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    url = os.environ.get(
        "TRUSTPILOT_SAMPLE_SEARCH_URL",
        "https://www.trustpilot.com/categories/electronics_technology",
    )
    results = await scrape_search(url, max_pages=1)
    assert len(results) >= 1
    for r in results:
        _validate(r, SEARCH_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_reviews():
    url = os.environ.get(
        "TRUSTPILOT_SAMPLE_COMPANY_URL", "https://www.trustpilot.com/review/www.bhphotovideo.com"
    )
    reviews = await scrape_reviews(url, max_pages=1)
    assert len(reviews) >= 1
    for r in reviews:
        _validate(r, REVIEW_SCHEMA)
