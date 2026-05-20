"""StockX scraper using the official Scrapeless Python SDK + Playwright over CDP.
the function names and emitted field names match verbatim.

Surfaces:
- scrape_product(url)            -> single product dict from __NEXT_DATA__ cache
- scrape_search(url, max_pages)  -> list of search result dicts (edges[].node)

StockX is React (Next.js) + heavy anti-bot. We use Scraping Browser sessions
with a US residential proxy and wait for the trade-box ask amount before lifting
__NEXT_DATA__. The `pricing` block on the returned product comes from a CDP-level
intercept of the in-page GraphQL XHR that hydrates the trade box.
"""

from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, List, Optional

from loguru import logger
from nested_lookup import nested_lookup
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

async def _fetch_with_xhrs(
    url: str,
    ready_selector: Optional[str],
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
    retries: int = 1,
) -> Dict[str, Any]:
    """Return {'html': ..., 'xhr': [{'url','body'}, ...]} after navigation."""
    last_error: Optional[Exception] = None
    for attempt in range(retries + 1):
        client = _client()
        session = client.browser.create(
            ICreateBrowser(proxy_country=proxy_country, session_ttl=DEFAULT_SESSION_TTL)
        )
        ws = session.browser_ws_endpoint
        xhr_records: List[Dict[str, Any]] = []
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(ws)
            try:
                page = await browser.new_page()

                async def _on_response(resp):
                    try:
                        if resp.request.resource_type in ("xhr", "fetch"):
                            ct = (resp.headers or {}).get("content-type", "")
                            if "json" in ct:
                                body = await resp.text()
                                xhr_records.append({"url": resp.url, "body": body})
                    except Exception:
                        pass

                page.on("response", lambda r: _on_response(r))

                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                if ready_selector:
                    try:
                        await page.wait_for_selector(ready_selector, timeout=20000)
                    except Exception as e:
                        logger.warning("wait_for_selector failed (continuing): {}", e)
                # let lazy XHRs settle
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass

                html = await page.content()
                if html:
                    return {"html": html, "xhr": xhr_records, "url": page.url}
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

def parse_nextjs(html: str) -> Dict[str, Any]:
    """Lift __NEXT_DATA__ JSON (or the query-data script fallback)."""
    sel = Selector(text=html)
    raw = sel.css("script#__NEXT_DATA__::text").get()
    if not raw:
        raw = sel.css("script[data-name=query]::text").get()
        if raw:
            raw = raw.split("=", 1)[-1].strip().strip(";")
    if not raw:
        raise ValueError("__NEXT_DATA__ not found")
    return json.loads(raw)

def parse_pricing(xhrs: List[Dict[str, Any]], sku: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Find the in-page product GraphQL XHR and lift its pricing fragment."""
    json_calls: List[Any] = []
    for xhr in xhrs:
        try:
            json_calls.append(json.loads(xhr["body"]))
        except Exception:
            continue
    for xhr in json_calls:
        if not isinstance(xhr, dict):
            continue
        product = (((xhr.get("data") or {}).get("product")) or {})
        if not product or "uuid" not in product:
            continue
        if sku is None or sku == product["uuid"]:
            return {
                "minimumBid": product.get("minimumBid"),
                "market": product.get("market"),
                "variants": product.get("variants"),
            }
    return None

# ---------------------------------------------------------------------------
# Scrape functions
# ---------------------------------------------------------------------------

async def scrape_product(url: str) -> Dict[str, Any]:
    """Scrape a single StockX product page."""
    logger.info("scraping product {}", url)
    fetched = await _fetch_with_xhrs(
        url, ready_selector="h2[data-testid='trade-box-buy-amount']"
    )
    data = parse_nextjs(fetched["html"])
    products = nested_lookup("product", data)
    try:
        product = next(p for p in products if isinstance(p, dict) and p.get("urlKey") and p["urlKey"] in fetched["url"])
    except StopIteration:
        raise ValueError(f"could not find product dataset in page cache for {url}")
    product["pricing"] = parse_pricing(fetched["xhr"], product.get("id"))
    return product

async def scrape_search(url: str, max_pages: int = 25) -> List[Dict[str, Any]]:
    """Scrape StockX search."""
    logger.info("scraping search {}", url)
    first = await _fetch_with_xhrs(url, ready_selector=None)
    data = parse_nextjs(first["html"])
    first_results = nested_lookup("results", data)[0]
    paging_info = first_results.get("pageInfo", {})
    total_pages = paging_info.get("pageCount") or math.ceil(
        (paging_info.get("total", 0)) / max(paging_info.get("limit", 1), 1)
    )
    if max_pages < total_pages:
        total_pages = max_pages

    previews: List[Dict[str, Any]] = [edge["node"] for edge in first_results.get("edges", [])]

    if total_pages > 1:
        logger.info("scraping search {} pagination ({} more pages)", url, total_pages - 1)
        for page in range(2, total_pages + 1):
            sep = "&" if "?" in url else "?"
            page_url = f"{url}{sep}page={page}"
            fetched = await _fetch_with_xhrs(page_url, ready_selector=None)
            page_data = parse_nextjs(fetched["html"])
            page_results = nested_lookup("results", page_data)[0]
            previews.extend(edge["node"] for edge in page_results.get("edges", []))

    logger.info("scraped {} products from {}", len(previews), url)
    return previews

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
