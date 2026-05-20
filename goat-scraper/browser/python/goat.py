"""Goat scraper using the official Scrapeless Python SDK + Playwright over CDP.
the function names and emitted field names match verbatim.

Surfaces:
- scrape_products(urls)             -> list of productTemplate dicts (with `offers`)
- scrape_search(query, max_pages)   -> list of search result dicts

Goat.com is React-rendered (Next.js). Product pages embed a `__NEXT_DATA__`
script we lift. Search uses goat.com's public consumer-search JSON endpoint;
we still fetch it through the Scraping Browser so Cloudflare clears.
"""

from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 180

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

async def _fetch_rendered(
    url: str,
    *,
    ready_selector: Optional[str] = None,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
    retries: int = 1,
) -> str:
    last_error: Optional[Exception] = None
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
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                if ready_selector:
                    try:
                        await page.wait_for_selector(ready_selector, timeout=15000)
                    except Exception as e:
                        logger.warning("wait_for_selector failed (continuing): {}", e)
                content = await page.content()
                if content:
                    return content
                last_error = RuntimeError("empty content")
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
# Helpers — names mirror the upstream reference verbatim
# ---------------------------------------------------------------------------

def find_hidden_data(html: str) -> Dict[str, Any]:
    """Extract __NEXT_DATA__ JSON from a Goat page."""
    sel = Selector(text=html)
    raw = sel.css("script#__NEXT_DATA__::text").get()
    if not raw:
        raise ValueError("__NEXT_DATA__ script not found")
    return json.loads(raw)

def _extract_json_payload(html: str) -> Dict[str, Any]:
    """The browser wraps JSON endpoints in <pre>…</pre> — peel that off."""
    try:
        return json.loads(html)
    except json.JSONDecodeError:
        sel = Selector(text=html)
        body = sel.css("pre::text").get() or sel.xpath("string(/)").get() or ""
        return json.loads(body)

# ---------------------------------------------------------------------------
# Scrape functions
# ---------------------------------------------------------------------------

async def scrape_products(urls: List[str]) -> List[Dict[str, Any]]:
    """Scrape Goat product pages for productTemplate + offers."""
    products: List[Dict[str, Any]] = []
    for url in urls:
        logger.info("scraping product {}", url)
        html = await _fetch_rendered(url, ready_selector="script#__NEXT_DATA__")
        data = find_hidden_data(html)
        page_props = data.get("props", {}).get("pageProps", {})
        product = page_props.get("productTemplate", {})
        if page_props.get("offers"):
            product["offers"] = page_props["offers"].get("offerData")
        else:
            product["offers"] = None
        products.append(product)
    logger.success("scraped {} product listings from product pages", len(products))
    return products

async def scrape_search(query: str, max_pages: int = 10) -> List[Dict[str, Any]]:
    """Scrape Goat consumer-search JSON endpoint with pagination."""

    def make_page_url(page: int = 1) -> str:
        params = {
            "queryString": query,
            "pageLimit": "12",
            "pageNumber": page,
            "sortType": "1",
        }
        return f"https://www.goat.com/web-api/consumer-search/get-product-search-results?{urlencode(params)}"

    logger.info("scraping product search with query {!r}", query)
    first_html = await _fetch_rendered(make_page_url(1), ready_selector=None)
    first_data = _extract_json_payload(first_html).get("data", {})
    results: List[Dict[str, Any]] = list(first_data.get("productsList", []))
    total_results = first_data.get("totalResults", 0)
    results_per_page = 12
    total_pages = math.ceil(total_results / results_per_page) if total_results else 1
    if max_pages and max_pages < total_pages:
        total_pages = max_pages

    if total_pages > 1:
        logger.info("scraping search pagination ({} more pages)", total_pages - 1)
        for page in range(2, total_pages + 1):
            html = await _fetch_rendered(make_page_url(page), ready_selector=None)
            data = _extract_json_payload(html).get("data", {})
            results.extend(data.get("productsList", []))

    logger.success("scraped {} product listings from search", len(results))
    return results

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
