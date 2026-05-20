"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from crunchbase import scrape_company, scrape_person, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


COMPANY_SCHEMA = {
    "organization": {"type": "dict", "required": True},
    "employees": {"type": "list", "required": True},
}

PERSON_SCHEMA = {
    "name": {"type": "string", "required": False},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_company():
    url = os.environ.get(
        "CRUNCHBASE_SAMPLE_COMPANY_URL",
        "https://www.crunchbase.com/organization/tesla-motors/people",
    )
    result = to_dict(await scrape_company(url))
    _validate(result, COMPANY_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_person():
    url = os.environ.get(
        "CRUNCHBASE_SAMPLE_PERSON_URL",
        "https://www.crunchbase.com/person/elon-musk",
    )
    result = to_dict(await scrape_person(url))
    _validate(result, PERSON_SCHEMA)
