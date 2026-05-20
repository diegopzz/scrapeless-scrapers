"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from glassdoor import (
    Region,
    Url,
    find_companies,
    scrape_jobs,
    scrape_reviews,
    scrape_salaries,
)


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


JOB_SCHEMA = {
    "jobTitle": {"type": "string", "required": True, "nullable": True},
    "jobLink": {"type": "string", "nullable": True},
    "job_location": {"type": "string", "nullable": True},
    "jobSalary": {"type": "string", "nullable": True},
    "jobDate": {"type": "string", "nullable": True},
}

REVIEW_SCHEMA = {
    "reviewId": {"type": "integer", "required": True},
    "ratingOverall": {"type": "integer", "required": True, "min": 1, "max": 5},
    "reviewDateTime": {"type": "string", "required": True},
}

SALARY_SCHEMA = {
    "results": {"type": "list", "required": True},
    "numPages": {"type": "integer", "required": True},
    "salaryCount": {"type": "integer", "required": True},
    "jobTitleCount": {"type": "integer", "required": True},
}

SALARY_ITEM_SCHEMA = {
    "jobTitle": {"type": "dict", "required": True},
    "salaryCount": {"type": "integer", "required": True},
    "basePayStatistics": {"type": "dict", "required": True},
}

COMPANY_SCHEMA = {
    "name": {"type": "string", "required": True, "minlength": 1},
    "id": {"type": "integer", "required": True},
    "shortName": {"type": "string"},
    "logoURL": {"type": "string", "nullable": True},
    "websiteURL": {"type": "string"},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


SAMPLE_EMPLOYER = os.environ.get("GLASSDOOR_SAMPLE_EMPLOYER", "eBay")
SAMPLE_EMPLOYER_ID = os.environ.get("GLASSDOOR_SAMPLE_EMPLOYER_ID", "7853")


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_jobs():
    url = Url.jobs(SAMPLE_EMPLOYER, SAMPLE_EMPLOYER_ID, region=Region.UNITED_STATES)
    jobs = await scrape_jobs(url, max_pages=1)
    assert len(jobs) >= 1
    for j in jobs:
        _validate(j, JOB_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_reviews():
    url = Url.reviews(SAMPLE_EMPLOYER, SAMPLE_EMPLOYER_ID)
    reviews = await scrape_reviews(url, max_pages=1)
    assert len(reviews) >= 1
    for r in reviews:
        _validate(r, REVIEW_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_salaries():
    url = Url.salaries(SAMPLE_EMPLOYER, SAMPLE_EMPLOYER_ID)
    salaries = await scrape_salaries(url, max_pages=1)
    _validate(salaries, SALARY_SCHEMA)
    for item in salaries["results"]:
        _validate(item, SALARY_ITEM_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_find_companies():
    companies = await find_companies(SAMPLE_EMPLOYER)
    assert len(companies) >= 1
    for c in companies:
        _validate(c, COMPANY_SCHEMA)
