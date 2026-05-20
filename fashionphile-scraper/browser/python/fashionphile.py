"""Fashionphile scraper using the official Scrapeless Python SDK + Playwright over CDP.
Surfaces:
- scrape_search(url, max_pages)   -> list of search-card dicts
- scrape_products(urls)            -> list of product JSON dicts lifted from /products/<slug>.json

Under the hood:
- `client.browser.create()` mints a cloud browser session (CDP WS endpoint).
- Playwright connects over CDP, fetches the rendered HTML (or JSON endpoint as text).
- Parsel parses search cards; product pages are JSON lifts off the JSON endpoint.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

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
    """Mint a session, navigate, optionally wait for a selector, return page content."""
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
# Helpers — names mirror the upstream reference's verbatim
# ---------------------------------------------------------------------------

def convert_to_json_urls(urls: List[str]) -> List[str]:
    """Rewrite /p/<slug> -> /products/<slug>.json (Fashionphile's data endpoint)."""
    out: List[str] = []
    for url in urls:
        out.append(url.replace("/p/", "/products/") + ".json")
    return out

def parse_price(price_text: Optional[str]) -> int:
    if not price_text:
        return 0
    return int(re.sub(r"[$,\s]", "", price_text.strip()) or 0)

def extract_product_from_card(card) -> Dict[str, Any]:
    """Extract a SearchResult from a `.fp-algolia-product-card` parsel Selector."""
    product_id = card.css("::attr(data-product-id)").get("") or ""
    brand_name = (card.css(".fp-card__vendor::text").get("") or "").strip()
    product_name = (card.css(".fp-card__link__product-name::text").get("") or "").strip()
    condition = (card.css(".fp-condition::text").get("") or "").strip()

    regular_price_text = (card.css(".price-item--regular::text").get("") or "").strip()
    sale_price_text = (card.css(".price-item--sale.price-item--last::text").get("") or "").strip()

    if sale_price_text:
        price_text = sale_price_text
    elif regular_price_text:
        price_text = regular_price_text
    else:
        price_text = (card.css(".price-item::text").get("$0") or "$0").strip()

    price = parse_price(price_text)
    if regular_price_text and sale_price_text:
        regular = parse_price(regular_price_text)
        discounted_price = regular - price
    else:
        discounted_price = 0

    return {
        "brand_name": brand_name,
        "product_name": product_name,
        "condition": condition,
        "discounted_price": discounted_price,
        "price": price,
        "id": int(product_id) if product_id.isdigit() else 0,
    }

# ---------------------------------------------------------------------------
# Scrape functions — mirror the upstream reference's exports verbatim
# ---------------------------------------------------------------------------

async def scrape_products(urls: List[str]) -> List[Dict[str, Any]]:
    """Scrape Fashionphile product pages via the /products/<slug>.json endpoint."""
    json_urls = convert_to_json_urls(urls)
    products: List[Dict[str, Any]] = []
    for url in json_urls:
        logger.info("scraping product {}", url)
        content = await _fetch_rendered(url, ready_selector=None)
        # The JSON endpoint may be wrapped in <pre>...</pre> when rendered as HTML.
        text = content
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            sel = Selector(text=content)
            body = sel.css("pre::text").get() or sel.xpath("string(/)").get() or ""
            data = json.loads(body)
        if isinstance(data, dict) and "product" in data:
            products.append(data["product"])
        else:
            products.append(data)
    logger.success("scraped {} product listings from product pages", len(products))
    return products

async def scrape_search(url: str, max_pages: int = 10) -> List[Dict[str, Any]]:
    """Scrape a Fashionphile /shop/... page across paginated results."""
    logger.info("scraping search {}", url)
    html = await _fetch_rendered(url, ready_selector=".fp-algolia-product-card")
    sel = Selector(text=html)
    results: List[Dict[str, Any]] = []
    cards = sel.css(".fp-algolia-product-card")
    logger.info("found {} products on first page", len(cards))
    for card in cards:
        try:
            results.append(extract_product_from_card(card))
        except Exception as e:  # noqa: BLE001
            logger.warning("failed to extract product: {}", e)

    pagination_href = sel.css(".ais-Pagination-item--lastPage a::attr(href)").get("") or ""
    total_pages = 1
    if pagination_href:
        match = re.search(r"page=(\d+)", pagination_href)
        if match:
            total_pages = int(match.group(1))
    if max_pages and max_pages < total_pages:
        total_pages = max_pages
    logger.info("total pages: {}", total_pages)

    if total_pages > 1:
        logger.info("scraping pagination ({} more pages)", total_pages - 1)
        base_url = url.split("?")[0]
        for page in range(2, total_pages + 1):
            page_url = f"{base_url}?page={page}"
            page_html = await _fetch_rendered(page_url, ready_selector=".fp-algolia-product-card")
            page_sel = Selector(text=page_html)
            for card in page_sel.css(".fp-algolia-product-card"):
                try:
                    results.append(extract_product_from_card(card))
                except Exception as e:  # noqa: BLE001
                    logger.warning("failed to extract product: {}", e)

    logger.success("scraped {} product listings from search pages", len(results))
    return results

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
