"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from google import scrape_google_map_places, scrape_keywords, scrape_serp, to_dict

pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)

SERP_SCHEMA = {
    "position": {"type": "integer", "required": True, "min": 1},
    "title": {"type": "string", "required": True, "minlength": 1},
    "url": {"type": "string", "required": True, "minlength": 1},
    "origin": {"type": "string", "required": False},
    "domain": {"type": "string", "required": True},
    "description": {"type": "string", "required": False},
    "date": {"type": "string", "required": False},
}

KEYWORDS_SCHEMA = {
    "related_search": {"type": "list", "required": True, "schema": {"type": "string"}},
    "people_ask_for": {"type": "list", "required": True, "schema": {"type": "string"}},
}

PLACE_SCHEMA = {
    "name": {"type": "string", "required": True, "minlength": 1},
    "category": {"type": "string", "required": False},
    "address": {"type": "string", "required": False},
    "website": {"type": "string", "required": False},
    "phone": {"type": "string", "required": False},
    "review_count": {"type": "string", "required": False},
    "stars": {"type": "string", "required": False},
    "5_stars": {"type": "string", "required": False},
    "4_stars": {"type": "string", "required": False},
    "3_stars": {"type": "string", "required": False},
    "2_stars": {"type": "string", "required": False},
    "1_stars": {"type": "string", "required": False},
}

def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_serp():
    query = os.environ.get("GOOGLE_SAMPLE_QUERY", "the upstream reference blog web scraping")
    results = to_dict(await scrape_serp(query, max_pages=1))
    assert len(results) >= 1, "expected at least one SERP result"
    for r in results:
        _validate(r, SERP_SCHEMA)

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_keywords():
    query = os.environ.get("GOOGLE_SAMPLE_QUERY", "web scraping emails")
    result = to_dict(await scrape_keywords(query))
    _validate(result, KEYWORDS_SCHEMA)

@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_google_map_places():
    url = os.environ.get(
        "GOOGLE_SAMPLE_PLACE_URL",
        "https://www.google.com/maps/place/Mus%C3%A9e+d%27Orsay/data=!4m7!3m6!1s0x47e66e2bb630941b:0xd071bd8cb14423d8!8m2!3d48.8599614!4d2.3265614!16zL20vMGYzYjk!19sChIJG5Qwtitu5kcR2CNEsYy9cdA",
    )
    results = to_dict(await scrape_google_map_places([url]))
    assert len(results) == 1
    _validate(results[0], PLACE_SCHEMA)
