"""Leboncoin scraper using the official Scrapeless Python SDK + Playwright over CDP.
Targets:
- search pages e.g. https://www.leboncoin.fr/recherche?text=coffe
- ad pages     e.g. https://www.leboncoin.fr/ad/ventes_immobilieres/2919253293

Both surfaces embed the payload in `<script id="__NEXT_DATA__">`. The scraper
reads it directly (no DOM crawling) so the emitted ad objects keep every
nested key Leboncoin ships in its NextJS cache.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Any, Dict, List

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "FR"
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

async def _fetch_rendered_html(
    url: str,
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
    retries: int = 2,
) -> str:
    """Mint a session, goto, wait for __NEXT_DATA__, return HTML.

    Leboncoin is DataDome-protected and frequently redirects blocked requests
    back to the homepage, so the caller can re-try (matching the upstream reference's
    `_retries` flow in `scrape_ad`).
    """
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
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                try:
                    await page.wait_for_selector("script#__NEXT_DATA__", timeout=20000)
                except Exception as e:
                    logger.warning("__NEXT_DATA__ wait failed (continuing): {}", e)
                html = await page.content()
                if html and "__NEXT_DATA__" in html:
                    return html
                last_error = RuntimeError("blocked / empty NEXT_DATA")
            except Exception as e:
                last_error = e
                logger.warning("attempt {} failed: {}", attempt + 1, e)
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass
    raise RuntimeError(f"giving up after {retries + 1} attempts: {last_error}")

# ---------------------------------------------------------------------------
# Parsers — verbatim from the upstream reference
# ---------------------------------------------------------------------------

def parse_search(html: str) -> List[Dict]:
    """parse search result data from nextjs cache"""
    selector = Selector(text=html)
    next_data = selector.css("script[id='__NEXT_DATA__']::text").get()
    if not next_data:
        raise RuntimeError("__NEXT_DATA__ not found")
    ads_data = json.loads(next_data)["props"]["pageProps"]["searchData"]["ads"]
    return ads_data

def _max_search_pages(html: str) -> int:
    """get the number of max pages in the search"""
    selector = Selector(text=html)
    next_data = selector.css("script[id='__NEXT_DATA__']::text").get()
    max_search_pages = json.loads(next_data)["props"]["pageProps"]["searchData"]["max_pages"]
    return max_search_pages

def parse_ad(html: str) -> Dict:
    """parse ad data from nextjs cache"""
    selector = Selector(text=html)
    next_data = selector.css("script[id='__NEXT_DATA__']::text").get()
    if not next_data:
        raise RuntimeError("__NEXT_DATA__ not found")
    ad_data = json.loads(next_data)["props"]["pageProps"]["ad"]
    return ad_data

# ---------------------------------------------------------------------------
# Scrape functions — mirror the upstream reference's exports verbatim
# ---------------------------------------------------------------------------

async def scrape_search(
    url: str, scrape_all_pages: bool, max_pages: int = 10
) -> List[Dict]:
    """scrape leboncoin search"""
    logger.info("scraping search {}", url)
    first_html = await _fetch_rendered_html(url)
    search_data = parse_search(first_html)
    total_search_pages = _max_search_pages(first_html)

    if scrape_all_pages is False and max_pages < total_search_pages:
        total_pages = max_pages
    else:
        total_pages = total_search_pages
    logger.info("scraping search {} pagination ({} more pages)", url, total_pages - 1)

    sep = "&" if "?" in url else "?"
    for page in range(2, total_pages + 1):
        page_url = f"{url}{sep}page={page}"
        try:
            html = await _fetch_rendered_html(page_url)
            search_data.extend(parse_search(html))
        except Exception as e:
            logger.error("search page {} failed: {}", page, e)
    logger.info("scraped {} ads from {}", len(search_data), url)
    return search_data

async def scrape_ad(url: str, _retries: int = 0) -> Dict | None:
    """scrape ad page"""
    logger.info("scraping ad {}", url)
    try:
        html = await _fetch_rendered_html(url)
        return parse_ad(html)
    except Exception as e:
        if _retries < 2:
            logger.debug("retrying failed request: {}", e)
            return await scrape_ad(url, _retries=_retries + 1)
        logger.error("ad {} failed after retries: {}", url, e)
        return None

def to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
