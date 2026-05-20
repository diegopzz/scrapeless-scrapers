"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from google_news import scrape_news, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


ARTICLE_SCHEMA = {
    "position": {"type": "integer", "required": True, "min": 1},
    "title": {"type": "string", "required": True, "minlength": 1},
    "url": {"type": "string", "required": True, "minlength": 1},
    "source": {"type": "string"},
    "time": {"type": "string"},
    "thumbnail": {"type": "string"},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_news():
    sample_query = os.environ.get("GOOGLE_NEWS_SAMPLE_QUERY", "adidas")
    results = [to_dict(r) for r in await scrape_news(sample_query)]
    assert len(results) >= 1, "expected at least one article"
    for r in results:
        _validate(r, ARTICLE_SCHEMA)
