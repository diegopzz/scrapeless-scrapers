"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from indeed import scrape_jobs, scrape_search, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


# Search-result items come from Indeed's mosaicProviderJobCardsModel.results
# (jobcard dicts). We assert a stable subset; Indeed adds keys constantly.
SEARCH_RESULT_SCHEMA = {
    "jobkey": {"type": "string", "required": True, "minlength": 1},
    "company": {"type": "string", "required": False, "nullable": True},
    "title": {"type": "string", "required": False},
    "displayTitle": {"type": "string", "required": False},
    "formattedLocation": {"type": "string", "required": False},
}

JOB_SCHEMA = {
    "description": {"type": "string", "required": True, "minlength": 1},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_search():
    sample_url = os.environ.get(
        "INDEED_SAMPLE_URL",
        "https://www.indeed.com/jobs?q=python&l=Texas",
    )
    results = [to_dict(r) for r in await scrape_search(sample_url, max_results=10)]
    assert len(results) >= 1, "expected at least one search result"
    for r in results:
        _validate(r, SEARCH_RESULT_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_jobs():
    raw = os.environ.get("INDEED_SAMPLE_JOB_KEYS", "")
    job_keys = [k.strip() for k in raw.split(",") if k.strip()] or [
        "fc5ec64fc4d62cea",
    ]
    jobs = [to_dict(j) for j in await scrape_jobs(job_keys)]
    assert len(jobs) == len(job_keys)
    for j in jobs:
        _validate(j, JOB_SCHEMA)
