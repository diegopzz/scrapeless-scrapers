"""Vestiairecollective scraper using the official Scrapeless Python SDK + Playwright over CDP.
the function names and emitted field names match verbatim.

Surfaces:
- scrape_products(urls)             -> list of product dicts (props.pageProps.product)
- scrape_search(url, max_pages)     -> list of search result dicts (paginated via /v1/product/search)

Vestiaire is React (Next.js) with serious anti-bot. We use a Scraping Browser
session with US residential proxy, lift the search XHR (headers + payload) from
the rendered first page, then paginate by re-issuing that POST through the
same browser context.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 180
SEARCH_API_URL = "https://search.vestiairecollective.com/v1/product/search"

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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_hidden_data(html: str) -> Dict[str, Any]:
    """Extract __NEXT_DATA__ JSON from a Vestiaire page."""
    sel = Selector(text=html)
    raw = sel.css("script#__NEXT_DATA__::text").get()
    if not raw:
        raise ValueError("__NEXT_DATA__ script not found")
    return json.loads(raw)

def parse_xhr_call(xhr_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Find the in-page `/v1/product/search` POST and lift headers/payload/data."""
    search_call = next(
        (c for c in xhr_records if "search" in c.get("url", "")), None
    )
    if not search_call:
        raise ValueError("couldn't find the search xhr call — is the search URL valid?")
    data = json.loads(search_call.get("response_body") or "{}")
    return {
        "headers": search_call.get("request_headers", {}),
        "payload": json.loads(search_call.get("request_post_data") or "{}"),
        "total_pages": data.get("paginationStats", {}).get("totalPages", 1),
        "data": data.get("items", []),
    }

def parse_search_api(body: str) -> List[Dict[str, Any]]:
    """Parse the /v1/product/search JSON response."""
    data = json.loads(body)
    return data.get("items", [])

# ---------------------------------------------------------------------------
# Browser-driven fetch
# ---------------------------------------------------------------------------

async def _scrape_first_search_page(url: str) -> Dict[str, Any]:
    """Render the first search page and capture the /v1/product/search XHR."""
    client = _client()
    session = client.browser.create(
        ICreateBrowser(proxy_country=DEFAULT_PROXY_COUNTRY, session_ttl=DEFAULT_SESSION_TTL)
    )
    ws = session.browser_ws_endpoint
    xhr_records: List[Dict[str, Any]] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(ws)
        try:
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = await context.new_page()

            async def _on_response(resp):
                try:
                    if "search" in resp.url and resp.request.method == "POST":
                        body = await resp.text()
                        xhr_records.append({
                            "url": resp.url,
                            "request_headers": resp.request.headers,
                            "request_post_data": resp.request.post_data,
                            "response_body": body,
                        })
                except Exception:
                    pass

            page.on("response", lambda r: _on_response(r))

            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass

            html = await page.content()
            return {"html": html, "xhr": xhr_records, "context": context}
        finally:
            try:
                await browser.close()
            except Exception:
                pass

async def _post_search_api(headers: Dict[str, str], payload: Dict[str, Any], offset: int) -> str:
    """POST to /v1/product/search through a fresh browser context."""
    client = _client()
    session = client.browser.create(
        ICreateBrowser(proxy_country=DEFAULT_PROXY_COUNTRY, session_ttl=DEFAULT_SESSION_TTL)
    )
    ws = session.browser_ws_endpoint
    payload = dict(payload)
    payload.setdefault("pagination", {})
    payload["pagination"] = dict(payload["pagination"])
    payload["pagination"]["offset"] = offset

    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(ws)
        try:
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            req = await context.request.post(
                SEARCH_API_URL,
                headers=headers,
                data=json.dumps(payload),
            )
            return await req.text()
        finally:
            try:
                await browser.close()
            except Exception:
                pass

# ---------------------------------------------------------------------------
# Scrape functions
# ---------------------------------------------------------------------------

async def scrape_products(urls: List[str]) -> List[Dict[str, Any]]:
    """Scrape Vestiaire product pages via __NEXT_DATA__."""
    products: List[Dict[str, Any]] = []
    for url in urls:
        logger.info("scraping product {}", url)
        client = _client()
        session = client.browser.create(
            ICreateBrowser(proxy_country=DEFAULT_PROXY_COUNTRY, session_ttl=DEFAULT_SESSION_TTL)
        )
        ws = session.browser_ws_endpoint
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(ws)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                try:
                    await page.wait_for_selector("script#__NEXT_DATA__", timeout=15000)
                except Exception:
                    pass
                html = await page.content()
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass
        try:
            data = find_hidden_data(html)
            products.append(data["props"]["pageProps"]["product"])
        except Exception as e:
            logger.error("An error occurred while parsing the product page. Is the listing expired?: {}", e)
            continue
    logger.success("scraped {} product listings from product pages", len(products))
    return products

async def scrape_search(url: str, max_pages: int = 10) -> List[Dict[str, Any]]:
    """Scrape Vestiaire /search?q=... pagination via the /v1/product/search XHR."""
    logger.info("scraping search page {}", url)
    first = await _scrape_first_search_page(url)
    api_result = parse_xhr_call(first["xhr"])
    headers = api_result["headers"]
    payload = api_result["payload"]
    results: List[Dict[str, Any]] = list(api_result["data"])
    total_pages = api_result["total_pages"]
    if max_pages and max_pages < total_pages:
        total_pages = max_pages
    total_products = total_pages * 48

    logger.info("scraping search pagination, remaining ({}) more pages", total_pages - 1)
    for offset in range(48, total_products, 48):
        try:
            body = await _post_search_api(headers, payload, offset)
            results.extend(parse_search_api(body))
        except Exception as e:
            logger.debug("Error occured while requesting search API: {}", e)
            continue
    logger.success("scraped {} product listings from search pages", len(results))
    return results

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
