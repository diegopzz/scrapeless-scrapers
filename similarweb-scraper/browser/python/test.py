"""Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset."""

from __future__ import annotations

import os

import pytest
from cerberus import Validator

from similarweb import (
    scrape_sitemaps,
    scrape_trendings,
    scrape_website,
    scrape_website_compare,
    to_dict,
)


pytestmark = pytest.mark.skipif(
    not (os.environ.get("SCRAPELESS_API_KEY") or os.environ.get("SCRAPELESS_KEY")),
    reason="SCRAPELESS_API_KEY / SCRAPELESS_KEY not set — skipping live tests",
)


WEBSITE_SCHEMA = {
    "overview": {"type": "dict", "required": True},
}

COMPARE_DOMAIN_SCHEMA = {
    "overview": {"type": "dict", "required": True},
}

TRENDING_SCHEMA = {
    "name": {"type": "string", "required": True},
    "url": {"type": "string", "required": True, "minlength": 1},
    "list": {"type": "list", "required": True},
}


def _validate(item: dict, schema: dict) -> None:
    v = Validator(schema, allow_unknown=True)
    assert v.validate(item), f"schema mismatch: {v.errors}"


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_website():
    domain = os.environ.get("SIMILARWEB_SAMPLE_DOMAIN", "google.com")
    results = to_dict(await scrape_website([domain]))
    assert len(results) == 1
    _validate(results[0], WEBSITE_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_website_compare():
    result = to_dict(await scrape_website_compare("google.com", "youtube.com"))
    assert "google.com" in result and "youtube.com" in result
    _validate(result["google.com"], COMPARE_DOMAIN_SCHEMA)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_sitemaps():
    url = "https://www.similarweb.com/sitemaps/top-websites/top-websites-001.xml.gz"
    urls = await scrape_sitemaps(url)
    assert isinstance(urls, list) and len(urls) >= 1
    for u in urls:
        assert isinstance(u, str)


@pytest.mark.flaky(reruns=3, reruns_delay=30)
@pytest.mark.asyncio
async def test_trendings():
    url = "https://www.similarweb.com/top-websites/computers-electronics-and-technology/programming-and-developer-software/"
    results = to_dict(await scrape_trendings([url]))
    assert len(results) == 1
    _validate(results[0], TRENDING_SCHEMA)
