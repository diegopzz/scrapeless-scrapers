"""Walmart scraper using the official Scrapeless Python SDK + Playwright over CDP.
the function names and emitted field names match verbatim. Data is extracted
from the `__NEXT_DATA__` script blob, not from DOM CSS selectors.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from loguru import logger as log
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 300

# Transient network failures we treat as retryable. Booking, ChatGPT and
# Walmart all sit behind aggressive CDNs that occasionally tear down the TLS
# tunnel mid-handshake — surfaced by Playwright as one of these strings.
TRANSIENT_NET_ERRORS = (
    "ERR_TUNNEL_CONNECTION_FAILED",
    "ERR_CONNECTION_CLOSED",
    "ERR_CONNECTION_RESET",
    "ERR_CONNECTION_REFUSED",
    "ERR_TIMED_OUT",
    "ERR_NETWORK_CHANGED",
    "ERR_EMPTY_RESPONSE",
    "ERR_PROXY_CONNECTION_FAILED",
    "Navigation timeout",
    "net::",
)

def _is_transient_error(err: Exception) -> bool:
    msg = str(err)
    return any(s in msg for s in TRANSIENT_NET_ERRORS)

def _looks_like_perimeterx_block(html: Optional[str]) -> bool:
    if not html:
        return True
    if "__NEXT_DATA__" not in html:
        return True
    if "px-captcha" in html or "Robot or human?" in html:
        return True
    return False

# upstream filter — keep these in sync with the upstream reference's wanted_product_keys
WANTED_PRODUCT_KEYS = [
    "availabilityStatus",
    "averageRating",
    "brand",
    "id",
    "imageInfo",
    "manufacturerName",
    "name",
    "orderLimit",
    "orderMinLimit",
    "priceInfo",
    "shortDescription",
    "type",
]

def _client() -> Scrapeless:
    if not os.environ.get("SCRAPELESS_API_KEY") and not os.environ.get("SCRAPELESS_KEY"):
        raise RuntimeError(
            "SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com"
        )
    if not os.environ.get("SCRAPELESS_API_KEY") and os.environ.get("SCRAPELESS_KEY"):
        os.environ["SCRAPELESS_API_KEY"] = os.environ["SCRAPELESS_KEY"]
    return Scrapeless()

async def _fetch_rendered_html(
    url: str,
    ready_selector: Optional[str] = None,
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
    retries: int = 2,
    warmup: bool = True,
) -> str:
    last_error: Exception | None = None
    total_attempts = retries + 1
    for attempt in range(total_attempts):
        client = _client()
        session = client.browser.create(
            ICreateBrowser(proxy_country=proxy_country, session_ttl=DEFAULT_SESSION_TTL)
        )
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
            try:
                page = await browser.new_page()
                # Warm-up: hit walmart.com homepage first so the session picks up
                # PerimeterX cookies and a real visit history before navigating to
                # the product / search URL. PX is much less aggressive on the
                # second hop within an established session.
                if warmup:
                    try:
                        await page.goto("https://www.walmart.com/", wait_until="domcontentloaded", timeout=45000)
                        await asyncio.sleep(2.0)
                    except Exception:
                        pass
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                # Wait for the React data blob to materialise rather than parsing
                # the raw shell HTML immediately.
                try:
                    await page.wait_for_function(
                        "() => !!document.getElementById('__NEXT_DATA__')",
                        timeout=25000,
                    )
                except Exception:
                    if ready_selector:
                        try:
                            await page.wait_for_selector(ready_selector, timeout=5000)
                        except Exception as e:
                            log.warning("wait_for_selector {!r} failed (continuing): {}", ready_selector, e)
                html = await page.content()
                if not _looks_like_perimeterx_block(html):
                    return html
                last_error = RuntimeError("no __NEXT_DATA__ in response (likely PerimeterX interstitial)")
                log.warning("attempt {}: {}", attempt + 1, last_error)
            except Exception as e:  # noqa: BLE001
                last_error = e
                log.warning("attempt {} failed: {}", attempt + 1, e)
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass
        if attempt < retries:
            # Sleep 30s between PX retries — PerimeterX rate-limits new
            # sessions per /24, so spacing matters more than rotation.
            sleep_secs = 30.0 * (1.5 ** attempt)
            await asyncio.sleep(sleep_secs)
    raise RuntimeError(f"giving up after {total_attempts} attempts: {last_error}")

def _next_data(html: str) -> Optional[Dict[str, Any]]:
    """Return the parsed __NEXT_DATA__ payload, or None if missing."""
    sel = Selector(text=html)
    raw = sel.xpath('//script[@id="__NEXT_DATA__"]/text()').get()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None

# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------

def parse_product(html: str) -> Optional[Dict[str, Any]]:
    """parse product data from walmart product pages"""
    data = _next_data(html)
    if not data:
        return None
    try:
        _product_raw = data["props"]["pageProps"]["initialData"]["data"]["product"]
        reviews_raw = data["props"]["pageProps"]["initialData"]["data"]["reviews"]
    except KeyError:
        return None
    product = {k: v for k, v in _product_raw.items() if k in WANTED_PRODUCT_KEYS}
    return {"product": product, "reviews": reviews_raw}

async def _scrape_product_with_fallback(url: str) -> Dict[str, Any]:
    """Scrape a single product URL with retries."""
    log.info(f"scraping product: {url}")
    try:
        html = await _fetch_rendered_html(url, ready_selector="script#__NEXT_DATA__")
        parsed = parse_product(html)
        if parsed is None:
            return {"url": url, "error": "failed to parse"}
        return parsed
    except Exception as e:  # noqa: BLE001
        log.error(f"failed to scrape {url}: {e}")
        return {"url": url, "error": str(e)}

async def scrape_products(urls: List[str]) -> List[Dict[str, Any]]:
    """Scrape product data from product pages with a JS rendering fallback."""
    tasks = [_scrape_product_with_fallback(url) for url in urls]
    results = await asyncio.gather(*tasks)
    log.success(f"scraped {len(results)} product pages")
    return results

# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def parse_search(html: str) -> Dict[str, Any]:
    """parse product listing data from search pages"""
    data = _next_data(html)
    if not data:
        return {"results": [], "total_results": 0}
    try:
        stack = data["props"]["pageProps"]["initialData"]["searchResult"]["itemStacks"][0]
    except (KeyError, IndexError):
        return {"results": [], "total_results": 0}
    return {"results": stack.get("items", []), "total_results": stack.get("count", 0)}

def _make_search_url(query: str, page: int, sort: str) -> str:
    return "https://www.walmart.com/search?" + urlencode(
        {
            "q": query,
            "page": page,
            sort: sort,
            "affinityOverride": "default",
        }
    )

async def scrape_search(
    query: str = "",
    sort: str = "best_match",
    max_pages: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """scrape walmart search pages"""
    log.info(f"scraping the first search page with the query ({query})")
    try:
        first_html = await _fetch_rendered_html(
            _make_search_url(query, 1, sort), ready_selector="script#__NEXT_DATA__"
        )
    except Exception as e:
        # PerimeterX is more aggressive on /search than on /ip — return what we
        # have rather than propagating the failure.
        log.error("scrape_search page=1 blocked: {}", e)
        return []
    data = parse_search(first_html)
    search_data: List[Dict[str, Any]] = list(data["results"])
    total_results = data["total_results"]

    total_pages = math.ceil(total_results / 40) if total_results else 1
    if total_pages > 25:
        total_pages = 25
    if max_pages and max_pages < total_pages:
        total_pages = max_pages

    log.info(f"scraping search pagination, remaining ({max(0, total_pages - 1)}) more pages")
    for page in range(2, total_pages + 1):
        try:
            page_html = await _fetch_rendered_html(
                _make_search_url(query, page, sort), ready_selector="script#__NEXT_DATA__"
            )
            search_data.extend(parse_search(page_html)["results"])
        except Exception as e:
            log.error("scrape_search page={} blocked: {}", page, e)
            break
    log.success(f"scraped {len(search_data)} product listings from search pages")
    return search_data

def to_dict(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
