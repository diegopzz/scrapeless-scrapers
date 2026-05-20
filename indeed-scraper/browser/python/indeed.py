"""Indeed scraper using the official Scrapeless Python SDK + Playwright over CDP.
Indeed exposes two embedded JSON blobs:
- Search pages: `window.mosaic.providerData["mosaic-provider-jobcards"]={...}`
- Job pages:    `_initialData={...};`

Both are extracted with the same regexes the upstream reference uses and the dicts are
forwarded with identical top-level keys (`results`, `meta`, `description`, plus
the flattened `jobMetadataHeaderModel` / `jobTagModel` / `jobInfoHeaderModel`).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from loguru import logger
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 180

SEARCH_JSON_RE = re.compile(
    r'window\.mosaic\.providerData\["mosaic-provider-jobcards"\]=(\{.+?\});',
    re.DOTALL,
)
JOB_JSON_RE = re.compile(r"_initialData=(\{.+?\});", re.DOTALL)

# ---------------------------------------------------------------------------
# Scrapeless plumbing
# ---------------------------------------------------------------------------

def _client() -> Scrapeless:
    if not os.environ.get("SCRAPELESS_API_KEY") and not os.environ.get("SCRAPELESS_KEY"):
        raise RuntimeError(
            "SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com"
        )
    if not os.environ.get("SCRAPELESS_API_KEY") and os.environ.get("SCRAPELESS_KEY"):
        os.environ["SCRAPELESS_API_KEY"] = os.environ["SCRAPELESS_KEY"]
    return Scrapeless()

def _looks_auth_walled(html: str, final_url: str) -> bool:
    if not html:
        return True
    if "secure.indeed.com/auth" in (final_url or ""):
        return True
    if "Sign In | Indeed Accounts" in html:
        return True
    if "Just a moment" in html and len(html) < 90000:
        return True
    return False


async def _fetch_rendered_html(
    url: str,
    ready_selector: str | None = None,
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
    retries: int = 2,
    warmup: bool = True,
) -> str:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        client = _client()
        session = client.browser.create(
            ICreateBrowser(proxy_country=proxy_country, session_ttl=DEFAULT_SESSION_TTL)
        )
        ws = session.browser_ws_endpoint
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(ws)
            try:
                page = await browser.new_page()
                if warmup:
                    try:
                        await page.goto("https://www.indeed.com/", wait_until="domcontentloaded", timeout=30000)
                        for _ in range(6):
                            await asyncio.sleep(2)
                            h = await page.content()
                            if h and "Just a moment" not in h and len(h) > 30000:
                                break
                    except Exception:
                        pass
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                html = ""
                for _ in range(6):
                    if ready_selector:
                        try:
                            await page.wait_for_selector(ready_selector, timeout=5000)
                            break
                        except Exception:
                            pass
                    await asyncio.sleep(2)
                    html = await page.content()
                    if html and "Just a moment" not in html:
                        break
                final_url = page.url
                if not html:
                    html = await page.content()
                if html and not _looks_auth_walled(html, final_url):
                    return html
                last_error = RuntimeError(
                    f"auth-wall (final={final_url[:60]})" if _looks_auth_walled(html, final_url) else "empty HTML"
                )
            except Exception as e:  # noqa: BLE001
                last_error = e
                logger.warning("attempt {} failed: {}", attempt + 1, e)
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass
    raise RuntimeError(f"giving up after {retries + 1} attempts: {last_error}")

def _add_url_parameter(url: str, **params: Any) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query))
    query.update({k: str(v) for k, v in params.items()})
    return urlunparse(parsed._replace(query=urlencode(query)))

# ---------------------------------------------------------------------------
# Parsers — verbatim shape from the upstream reference's indeed.py
# ---------------------------------------------------------------------------

def parse_search_page(html: str) -> dict[str, Any]:
    m = SEARCH_JSON_RE.search(html)
    if not m:
        return {"results": [], "meta": []}
    data = json.loads(m.group(1))
    model = data.get("metaData", {}).get("mosaicProviderJobCardsModel", {})
    return {
        "results": model.get("results", []),
        "meta": model.get("tierSummaries", []),
    }

def parse_job_page(html: str) -> dict[str, Any]:
    m = JOB_JSON_RE.search(html)
    if not m:
        return {}
    data = json.loads(m.group(1))
    job_data: dict[str, Any] = {}
    try:
        job_data["description"] = data["jobInfoWrapperModel"]["jobInfoModel"][
            "sanitizedJobDescription"
        ]
    except (KeyError, TypeError):
        job_data["description"] = ""
    for sub_key in ("jobMetadataHeaderModel", "jobTagModel", "jobInfoHeaderModel"):
        sub = data.get(sub_key)
        if isinstance(sub, dict):
            job_data.update(sub)
    return job_data

# ---------------------------------------------------------------------------
# Scrape functions — mirror the upstream reference's exports verbatim
# ---------------------------------------------------------------------------

async def scrape_search(url: str, max_results: int = 1000) -> list[dict[str, Any]]:
    """Scrape Indeed search results across pagination (10 jobs per page)."""
    first = await _fetch_rendered_html(url, ready_selector="#mosaic-provider-jobcards")
    first_page = parse_search_page(first)
    all_results: list[dict[str, Any]] = list(first_page.get("results", []))
    total = max_results
    try:
        total = min(max_results, int(first_page["meta"][0]["jobCount"]))
    except (KeyError, IndexError, TypeError, ValueError):
        pass
    # Indeed paginates with start=10, 20, ...
    other_pages = []
    for start in range(10, total, 10):
        other_pages.append(_add_url_parameter(url, start=start))
    for page_url in other_pages:
        try:
            html = await _fetch_rendered_html(page_url, ready_selector="#mosaic-provider-jobcards")
            parsed = parse_search_page(html)
            all_results.extend(parsed.get("results", []))
            if len(all_results) >= max_results:
                break
        except Exception as e:  # noqa: BLE001
            logger.warning("search page {} failed: {}", page_url, e)
            break
    return all_results[:max_results]

async def scrape_jobs(job_keys: list[str]) -> list[dict[str, Any]]:
    """Scrape individual job listing pages by `jk` (job key)."""
    out: list[dict[str, Any]] = []
    for jk in job_keys:
        url = f"https://www.indeed.com/viewjob?jk={jk}"
        try:
            html = await _fetch_rendered_html(url, ready_selector="#jobDescriptionText")
            parsed = parse_job_page(html)
            if parsed:
                out.append(parsed)
        except Exception as e:  # noqa: BLE001
            # Indeed often locks /viewjob behind a bot-detection sign-in wall on
            # fresh proxies. Skip rather than poison the result file.
            logger.warning("skip jk={}: {}", jk, e)
    return out

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
