"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from google_jobs import scrape_jobs, to_dict


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


JOB_SCHEMA = {
    "title": {"type": "string", "required": True, "minlength": 1},
    "company": {"type": "string", "required": True, "minlength": 1},
    "location": {"type": "string", "nullable": True},
    "source": {"type": "string", "nullable": True},
    "posted_at": {"type": "string", "nullable": True},
    "salary": {"type": "string", "nullable": True},
    "job_type": {"type": "string", "nullable": True},
    "url": {"type": "string", "nullable": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_jobs():
    query = os.environ.get("GOOGLE_JOBS_QUERY", "software engineer jobs austin tx")
    jobs = to_dict(await scrape_jobs(query))
    assert isinstance(jobs, list) and len(jobs) > 0, "expected at least one job listing"
    for job in jobs[:3]:
        _validate(job, JOB_SCHEMA)
