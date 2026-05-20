"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from g2 import scrape_alternatives, scrape_reviews, scrape_search


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


SEARCH_SCHEMA = {
    "name": {"type": "string", "required": True, "minlength": 1},
    "link": {"type": "string", "required": True, "minlength": 1},
    "image": {"type": "string", "nullable": True},
    "rate": {"type": "float", "nullable": True},
    "reviewsNumber": {"type": "integer", "nullable": True},
    "description": {"type": "string", "nullable": True},
    "categories": {"type": "list", "required": True},
}

REVIEW_SCHEMA = {
    "author": {
        "type": "dict",
        "required": True,
        "schema": {
            "authorName": {"type": "string", "nullable": True},
            "authorProfile": {"type": "string", "nullable": True},
            "authorPosition": {"type": "string", "nullable": True},
            "authorCompanySize": {"type": "string", "nullable": True},
        },
    },
    "review": {
        "type": "dict",
        "required": True,
        "schema": {
            "reviewTags": {"type": "list", "required": True},
            "reviewData": {"type": "string", "nullable": True},
            "reviewRate": {"type": "float", "nullable": True},
            "reviewTitle": {"type": "string", "nullable": True},
            "reviewLikes": {"type": "string"},
            "reviewDislikes": {"type": "string"},
        },
    },
}

ALTERNATIVE_SCHEMA = {
    "name": {"type": "string", "required": True, "minlength": 1},
    "link": {"type": "string", "nullable": True},
    "ranking": {"type": "integer", "nullable": True},
    "numberOfReviews": {"type": "integer", "nullable": True},
    "rate": {"type": "float", "nullable": True},
    "description": {"type": "string", "nullable": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    url = os.environ.get("G2_SAMPLE_SEARCH_URL", "https://www.g2.com/search?query=Infrastructure")
    results = await scrape_search(url=url, max_scrape_pages=1)
    assert len(results) >= 1
    for r in results:
        _validate(r, SEARCH_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_reviews():
    url = os.environ.get(
        "G2_SAMPLE_REVIEW_URL", "https://www.g2.com/products/digitalocean/reviews"
    )
    reviews = await scrape_reviews(url=url, max_review_pages=1)
    assert len(reviews) >= 1
    for r in reviews:
        _validate(r, REVIEW_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_alternatives():
    product = os.environ.get("G2_SAMPLE_PRODUCT", "digitalocean")
    alternatives = await scrape_alternatives(product=product)
    assert len(alternatives) >= 1
    for a in alternatives:
        _validate(a, ALTERNATIVE_SCHEMA)
