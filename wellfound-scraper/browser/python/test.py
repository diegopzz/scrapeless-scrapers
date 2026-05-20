"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from wellfound import scrape_companies, scrape_search, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


COMPANY_SCHEMA = {
    "id": {"type": "string", "required": True, "minlength": 1},
    "name": {"type": "string", "required": True, "minlength": 1},
    "slug": {"type": "string", "required": True, "minlength": 1},
    "badges": {"type": "list", "required": False},
    "companySize": {"type": "string", "required": False, "nullable": True},
    "highConcept": {"type": "string", "required": False, "nullable": True},
    "logoUrl": {"type": "string", "required": False, "nullable": True},
    "highlightedJobListings": {"type": "list", "required": False},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    role = os.environ.get("WELLFOUND_ROLE", "engineer")
    location = os.environ.get("WELLFOUND_LOCATION", "")
    results = [to_dict(r) for r in await scrape_search(role, location, max_pages=1)]
    assert len(results) >= 1, "expected at least one company"
    for c in results:
        _validate(c, COMPANY_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_companies():
    urls = (os.environ.get("WELLFOUND_COMPANY_URLS")
            or "https://wellfound.com/company/openai").split(",")
    results = [to_dict(r) for r in await scrape_companies(urls)]
    assert len(results) >= 1
    for c in results:
        _validate(c, COMPANY_SCHEMA)
