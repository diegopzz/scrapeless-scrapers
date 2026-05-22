"""Google Jobs scraper using the official Scrapeless Python SDK + Playwright over CDP.

Google renders a Jobs panel inside its standard SERP when a job-related query is
made (e.g. "software engineer jobs austin tx"). The panel data is embedded in the
rendered HTML card text — no special ibp=htl;jobs endpoint is needed.

Extraction strategy:
- Navigate to the SERP with ``waitUntil="networkidle2"`` so all redirects settle.
- Parse the ``body.innerText`` from the "Job postings" heading until the "more jobs"
  sentinel, grouping consecutive lines into one ``JobListing`` per card.
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any, List, Optional, TypedDict
from urllib.parse import quote_plus

from loguru import logger
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 180
GOOGLE_SEARCH_BASE = "https://www.google.com/search"


class JobListing(TypedDict, total=False):
    title: str
    company: str
    location: Optional[str]
    source: Optional[str]
    posted_at: Optional[str]
    salary: Optional[str]
    job_type: Optional[str]
    url: Optional[str]


def _client() -> Scrapeless:
    if not os.environ.get("SCRAPELESS_API_KEY") and not os.environ.get("SCRAPELESS_KEY"):
        raise RuntimeError("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com")
    if not os.environ.get("SCRAPELESS_API_KEY") and os.environ.get("SCRAPELESS_KEY"):
        os.environ["SCRAPELESS_API_KEY"] = os.environ["SCRAPELESS_KEY"]
    return Scrapeless()


async def _fetch_rendered_html(
    url: str,
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
    retries: int = 2,
) -> str:
    last_error: Optional[Exception] = None
    for attempt in range(retries + 1):
        client = _client()
        session = client.browser.create(
            ICreateBrowser(proxy_country=proxy_country, session_ttl=DEFAULT_SESSION_TTL)
        )
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
            try:
                page = await browser.new_page()
                await page.set_viewport_size({"width": 1366, "height": 900})
                await page.goto(url, wait_until="networkidle", timeout=60000)
                html = await page.content()
                if html and len(html) > 5000:
                    return html
                last_error = RuntimeError(f"short HTML len={len(html) if html else 0}")
            except Exception as e:  # noqa: BLE001
                last_error = e
                logger.warning("attempt {} failed: {}", attempt + 1, e)
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass
    raise RuntimeError(f"giving up after {retries + 1} attempts: {last_error}")


_TIME_RE = re.compile(r"^\d+\s+(?:second|minute|hour|day|week|month)s?\s+ago$", re.I)
_SALARY_RE = re.compile(r"^\$[\d,]+|^\d+[\–\-]\d+\s+an?\s+(?:hour|year)|^\d[\d,]*\s*(?:a|per)\s+(?:hour|year)", re.I)
_LOCATION_VIA_RE = re.compile(r"^.+,\s+[A-Z]{2}\s+•\s+via\s+")
_JOB_TYPE_RE = re.compile(r"^(?:Full-time|Part-time|Contractor|Internship|Temporary)", re.I)
_SKIP_LINES = {"Saved jobs", "Following", "Feedback", "Learn more", "Follow", "Search Results"}


def parse_jobs(html: str) -> List[JobListing]:
    """Parse JobListing objects from the rendered SERP HTML body text."""
    from parsel import Selector

    sel = Selector(text=html)
    body_text = " ".join(sel.css("body ::text").getall())
    # Use the raw text as individual lines
    lines = [ln.strip() for ln in "\n".join(sel.css("body *::text").getall()).splitlines() if ln.strip()]

    results: List[JobListing] = []
    in_jobs = False
    i = 0

    while i < len(lines):
        line = lines[i]
        if line == "Job postings":
            in_jobs = True
            i += 1
            continue
        if not in_jobs:
            i += 1
            continue
        if line in {"More jobs", "Search jobs on Google", "Web results"} or line.endswith("more jobs"):
            break
        if line in _SKIP_LINES or _TIME_RE.match(line) or _SALARY_RE.match(line) or _JOB_TYPE_RE.match(line):
            i += 1
            continue

        # Candidate job title — scan ahead for block fields
        if (
            len(line) > 5
            and not _LOCATION_VIA_RE.match(line)
            and not line.startswith("No degree")
        ):
            title = line
            company = ""
            location = ""
            source = ""
            posted_at = ""
            salary = ""
            job_type = ""
            j = i + 1

            while j < len(lines) and j < i + 10:
                nxt = lines[j]
                if _TIME_RE.match(nxt):
                    posted_at = nxt
                    j += 1
                    continue
                if _SALARY_RE.match(nxt):
                    salary = nxt
                    j += 1
                    continue
                if _JOB_TYPE_RE.match(nxt):
                    job_type = nxt
                    j += 1
                    continue
                if nxt.startswith("No degree"):
                    j += 1
                    continue
                if _LOCATION_VIA_RE.match(nxt):
                    parts = nxt.split(" • via ")
                    location = parts[0].strip()
                    source = parts[1].strip() if len(parts) > 1 else ""
                    j += 1
                    continue
                if not company and nxt and nxt != title and nxt not in _SKIP_LINES:
                    company = nxt
                    j += 1
                    continue
                break

            if company and (posted_at or location):
                results.append(
                    JobListing(
                        title=title,
                        company=company,
                        location=location or None,
                        source=source or None,
                        posted_at=posted_at or None,
                        salary=salary or None,
                        job_type=job_type or None,
                        url=None,
                    )
                )
                i = j
                continue

        i += 1

    return results


async def scrape_jobs(query: str, *, proxy_country: str = DEFAULT_PROXY_COUNTRY) -> List[JobListing]:
    url = f"{GOOGLE_SEARCH_BASE}?q={quote_plus(query)}&gl=us&hl=en"
    html = await _fetch_rendered_html(url, proxy_country=proxy_country)
    return parse_jobs(html)


def to_dict(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
