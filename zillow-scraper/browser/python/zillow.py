"""Zillow scraper using the official Scrapeless Python SDK + Playwright over CDP.
function names and emitted field names match verbatim.

Discovery: Zillow's property page embeds `__NEXT_DATA__` (modern) or
`hdpApolloPreloadedData` (legacy) script tags containing the full property JSON.
We render the page through a Scrapeless Scraping Browser session (residential
proxy + DataDome mitigation), then parse the embedded JSON with parsel.

For search, we bootstrap the queryState from the first page's `__NEXT_DATA__`
then call the public `async-create-search-page-state` endpoint with PUT, mirroring
the upstream reference's approach. The endpoint is unauthenticated but rejects non-browser
TLS fingerprints — calling it through the rendered page's fetch context keeps
the session sticky.
"""

from __future__ import annotations

import json
import os
import random
from typing import Any

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 180

BACKEND_SEARCH_URL = "https://www.zillow.com/async-create-search-page-state"

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

async def _new_browser(proxy_country: str = DEFAULT_PROXY_COUNTRY):
    """Mint a Scrapeless browser session and connect Playwright over CDP."""
    client = _client()
    session = client.browser.create(
        ICreateBrowser(proxy_country=proxy_country, session_ttl=DEFAULT_SESSION_TTL)
    )
    return session.browser_ws_endpoint

async def _fetch_rendered_html(
    url: str,
    ready_selector: str | None,
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
    retries: int = 1,
) -> str:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        ws = await _new_browser(proxy_country=proxy_country)
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(ws)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                if ready_selector:
                    try:
                        await page.wait_for_selector(ready_selector, timeout=15000)
                    except Exception as e:
                        logger.warning("wait_for_selector failed (continuing): {}", e)
                html = await page.content()
                if html:
                    return html
                last_error = RuntimeError("empty HTML")
            except Exception as e:  # noqa: BLE001
                last_error = e
                logger.warning("attempt {} failed: {}", attempt + 1, e)
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass
    raise RuntimeError(f"giving up after {retries + 1} attempts: {last_error}")

# ---------------------------------------------------------------------------
# Scrape functions — mirror the upstream reference's exports verbatim
# ---------------------------------------------------------------------------

def _create_search_payload(query_data: dict, page_number: int | None = None) -> str:
    """"""
    payload = {
        "searchQueryState": query_data,
        "wants": {"cat1": ["listResults", "mapResults"], "cat2": ["total"]},
        "requestId": random.randint(2, 10),
    }
    if page_number:
        payload["searchQueryState"]["pagination"] = {"currentPage": page_number}
    return json.dumps(payload)

async def scrape_search(url: str, max_scrape_pages: int | None = None) -> list[dict]:
    """Scrape Zillow's search page + pagination via the async-create-search-page-state endpoint."""
    logger.info("scraping search: {}", url)
    search_data: list[dict] = []

    ws = await _new_browser()
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(ws)
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            try:
                await page.wait_for_selector("script#__NEXT_DATA__", timeout=15000)
            except Exception:
                pass
            html = await page.content()
            sel = Selector(text=html)
            next_data_text = sel.xpath("//script[@id='__NEXT_DATA__']/text()").get()
            if not next_data_text:
                raise RuntimeError("missing __NEXT_DATA__ on search page")
            script_data = json.loads(next_data_text)
            query_data = script_data["props"]["pageProps"]["searchPageState"]["queryState"]

            async def _call_backend(body: str) -> dict:
                # Use the browser's fetch so TLS / cookie fingerprint match.
                result = await page.evaluate(
                    """async ({url, body}) => {
                        const res = await fetch(url, {
                            method: 'PUT',
                            headers: {'content-type': 'application/json'},
                            body,
                        });
                        const text = await res.text();
                        return text;
                    }""",
                    {"url": BACKEND_SEARCH_URL, "body": body},
                )
                return json.loads(result)

            data = await _call_backend(_create_search_payload(query_data))
            property_data = data["cat1"]["searchResults"]["listResults"]
            search_data.extend(property_data)
            total_pages = data["cat1"]["searchList"]["totalPages"]

            if total_pages > 1:
                if max_scrape_pages and max_scrape_pages < total_pages:
                    total_pages = max_scrape_pages
                logger.info("scraping {} more pages", total_pages - 1)
                for p in range(2, total_pages + 1):
                    page_data = await _call_backend(
                        _create_search_payload(query_data, page_number=p)
                    )
                    search_data.extend(
                        page_data["cat1"]["searchResults"]["listResults"]
                    )
        finally:
            try:
                await browser.close()
            except Exception:
                pass

    logger.success("scraped {} properties from search pages", len(search_data))
    return search_data

async def scrape_properties(urls: list[str]) -> list[dict]:
    """Scrape Zillow property pages — extract the embedded property JSON."""
    results: list[dict] = []
    for url in urls:
        html = await _fetch_rendered_html(url, ready_selector="script#__NEXT_DATA__")
        results.append(_parse_property(html))
    return results

# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _parse_property(html: str) -> dict:
    """Extract the property dict from __NEXT_DATA__ or hdpApolloPreloadedData."""
    sel = Selector(text=html)
    data = sel.css("script#__NEXT_DATA__::text").get()
    if data:
        data = json.loads(data)
        cache = json.loads(
            data["props"]["pageProps"]["componentProps"]["gdpClientCache"]
        )
        first_key = next(iter(cache))
        return cache[first_key]["property"]
    apollo = sel.css("script#hdpApolloPreloadedData::text").get()
    if not apollo:
        raise RuntimeError("no property JSON found on page")
    apollo_data = json.loads(json.loads(apollo)["apiCache"])
    return next(v["property"] for k, v in apollo_data.items() if "ForSale" in k)

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
