"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from linkedin import (
    scrape_articles,
    scrape_company,
    scrape_job_search,
    scrape_jobs,
    scrape_profile,
    to_dict,
)


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


PROFILE_SCHEMA = {
    "profile": {"type": "dict", "required": True},
    "posts": {"type": "list", "required": False},
}

COMPANY_SCHEMA = {
    "name": {"type": "string", "required": True, "minlength": 1},
    "url": {"type": "string", "required": True},
    "description": {"type": "string", "nullable": True, "required": False},
    "logo": {"type": ["string", "dict"], "nullable": True, "required": False},
}

JOB_SEARCH_SCHEMA = {
    "data": {"type": "list", "required": True},
    "total_results": {"type": "integer", "nullable": True, "required": False},
}

JOB_SCHEMA = {
    "@type": {"type": "string", "required": False},
}

ARTICLE_SCHEMA = {
    "@type": {"type": "string", "required": False},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_profile():
    urls = (os.environ.get("LINKEDIN_PROFILE_URLS")
            or "https://www.linkedin.com/in/williamhgates").split(",")
    for p in [to_dict(x) for x in await scrape_profile(urls)]:
        _validate(p, PROFILE_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_company():
    urls = (os.environ.get("LINKEDIN_COMPANY_URLS")
            or "https://www.linkedin.com/company/microsoft").split(",")
    for c in [to_dict(x) for x in await scrape_company(urls)]:
        _validate(c, COMPANY_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_job_search():
    keyword = os.environ.get("LINKEDIN_JOB_KEYWORD", "Python Developer")
    location = os.environ.get("LINKEDIN_JOB_LOCATION", "United States")
    pages = [to_dict(p) for p in await scrape_job_search(keyword, location, max_pages=1)]
    assert len(pages) >= 1
    for p in pages:
        _validate(p, JOB_SEARCH_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_jobs():
    urls = (os.environ.get("LINKEDIN_JOB_URLS")
            or "https://www.linkedin.com/jobs/view/3766857648").split(",")
    for j in [to_dict(x) for x in await scrape_jobs(urls)]:
        _validate(j, JOB_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_articles():
    urls = (os.environ.get("LINKEDIN_ARTICLE_URLS")
            or "https://www.linkedin.com/pulse/how-i-learnt-stop-worrying-love-rejection-richard-branson").split(",")
    for a in [to_dict(x) for x in await scrape_articles(urls)]:
        _validate(a, ARTICLE_SCHEMA)
