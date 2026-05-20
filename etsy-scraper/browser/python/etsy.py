"""Etsy scraper using the official Scrapeless Python SDK + Playwright over CDP.
Surfaces:
- scrape_search(url, max_pages) -> list of search-card dicts
- scrape_product(urls)          -> list of JSON-LD Product dicts
- scrape_shop(urls)             -> list of JSON-LD ItemList dicts (with `url`)

Under the hood:
- `client.browser.create()` mints a cloud browser session (CDP WS endpoint).
- Playwright connects over CDP, drives the page, returns rendered HTML.
- Parsel parses the HTML; product/shop pages are JSON-LD lifts.
"""

from __future__ import annotations

import asyncio
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

def _looks_like_datadome_block(html: str) -> bool:
    if not html:
        return True
    if len(html) < 4000 and ("captcha-delivery" in html or "geo.captcha-delivery" in html):
        return True
    return False

async def _fetch_rendered_html(
    url: str,
    ready_selector: str,
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
    retries: int = 2,
    warmup: bool = True,
) -> str:
    """Discover -> extract: mint a session, goto, wait for stable marker, return HTML.

    Etsy is fronted by DataDome and almost always serves a captcha interstitial
    on a cold session. A homepage warm-up primes the DataDome cookie so the
    next navigation returns the real search HTML.
    """
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
                if warmup:
                    try:
                        await page.goto("https://www.etsy.com/", wait_until="domcontentloaded", timeout=30000)
                        await asyncio.sleep(2.5)
                    except Exception:
                        pass
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                try:
                    await page.wait_for_selector(ready_selector, timeout=15000)
                except Exception as e:
                    logger.warning("wait_for_selector failed (continuing): {}", e)
                html = await page.content()
                if html and not _looks_like_datadome_block(html):
                    return html
                last_error = RuntimeError("DataDome interstitial or empty HTML")
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
# Helpers
# ---------------------------------------------------------------------------

def strip_text(text: Optional[str]) -> Optional[str]:
    """trim whitespace; return None if input is None."""
    if text is None:
        return None
    return text.strip()

def _to_float(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    try:
        return float(re.sub(r"[^0-9.]", "", text))
    except ValueError:
        return None

def _to_int(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    digits = re.sub(r"[^0-9]", "", text)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None

# ---------------------------------------------------------------------------
# Parsers — keys mirror the upstream reference's verbatim
# ---------------------------------------------------------------------------

def parse_search(html: str) -> Dict[str, Any]:
    """Parse listing cards on an Etsy /search results page.

    Returns {"search_data": [...], "total_pages": int}.
    """
    sel = Selector(text=html)
    items: List[Dict[str, Any]] = []
    cards = sel.xpath(
        "//div[@data-search-results-lg]/ul/li[div[@data-appears-component-name]]"
    )
    for card in cards:
        link = card.xpath(".//a[contains(@class,'v2-listing-card')]/@href").get("")
        title = card.xpath(".//h3[contains(@class,'v2-listing-card__titl')]/@title").get("")
        image = card.xpath(".//img[@data-listing-card-listing-image]/@src").get("")
        seller_text = card.xpath(".//span[contains(text(),'From shop')]/text()").get()
        seller = None
        if seller_text:
            seller = re.sub(r"(?i)^From shop\s*", "", seller_text).strip() or None
        is_paid = card.xpath(".//span[@data-ad-label='Ad by Etsy seller']").get() is not None
        rating = _to_float(card.xpath(".//span[contains(@class,'review_stars')]/span/text()").get())
        reviews = _to_int(card.xpath(".//div[contains(@aria-label,'star rating')]/p/text()").get())
        free_shipping_text = card.xpath(".//span[contains(text(),'Free shipping')]/text()").get()
        free_shipping = "yes" if free_shipping_text else "no"
        price = _to_float(card.xpath(".//span[@class='currency-value']/text()").get()) or 0.0
        currency = card.xpath(".//span[@class='currency-symbol']/text()").get("")
        original_price = card.xpath(".//span[contains(text(),'Original Price')]/text()").get("")
        discount = card.xpath(".//span[contains(text(),'off')]/text()").get("") or ""

        items.append({
            "productLink": link,
            "productTitle": title,
            "productImage": image,
            "seller": seller,
            "listingType": "paid" if is_paid else "organic",
            "productRate": rating,
            "numberOfReviews": reviews,
            "freeShipping": free_shipping,
            "productPrice": price,
            "priceCurrency": currency,
            "originalPrice": (original_price or "").strip(),
            "discount": (discount or "").strip(),
        })

    # total page count: look at the pagination control's last page link
    last_page_text = sel.css("nav[aria-label='Pagination'] li:nth-last-child(2) a::text").get()
    total_pages = _to_int(last_page_text) or 1
    return {"search_data": items, "total_pages": total_pages}

def _iter_jsonld_nodes(raw_blocks: List[str]):
    """Yield every JSON-LD node from a list of raw <script> bodies.

    Handles three shapes:
      - bare object: `{"@type": "Product", ...}`
      - array of objects: `[{"@type": "Product"}, {"@type": "BreadcrumbList"}]`
      - graph wrapper: `{"@context": "...", "@graph": [{...}, {...}]}`
    """
    for raw in raw_blocks:
        if not raw or not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            graph = node.get("@graph")
            if isinstance(graph, list):
                for sub in graph:
                    if isinstance(sub, dict):
                        yield sub
            else:
                yield node

def _type_matches(node: Dict[str, Any], wanted: str) -> bool:
    t = node.get("@type")
    if isinstance(t, str):
        return t == wanted
    if isinstance(t, list):
        return wanted in t
    return False

def parse_product_page(html: str) -> Dict[str, Any]:
    """Lift the JSON-LD Product script from an Etsy listing page."""
    sel = Selector(text=html)
    raw_blocks = sel.css('script[type="application/ld+json"]::text').getall()
    for node in _iter_jsonld_nodes(raw_blocks):
        if _type_matches(node, "Product"):
            return node
    return {}

def parse_shop_page(html: str, url: str) -> Dict[str, Any]:
    """Lift the JSON-LD ItemList script from an Etsy shop page; attach `url`."""
    sel = Selector(text=html)
    raw_blocks = sel.css('script[type="application/ld+json"]::text').getall()
    for node in _iter_jsonld_nodes(raw_blocks):
        if _type_matches(node, "ItemList"):
            node["url"] = url
            return node
    return {"url": url}

# ---------------------------------------------------------------------------
# Scrape functions — mirror the upstream reference's exports verbatim
# ---------------------------------------------------------------------------

async def scrape_search(url: str, max_pages: Optional[int] = None) -> List[Dict[str, Any]]:
    """Scrape Etsy /search?q=... pagination, returning a flat list of card dicts."""
    logger.info("scraping search {}", url)
    html = await _fetch_rendered_html(url, ready_selector="div[data-search-results-lg]")
    parsed = parse_search(html)
    items: List[Dict[str, Any]] = list(parsed["search_data"])
    total_pages = parsed["total_pages"]
    if max_pages and max_pages < total_pages:
        total_pages = max_pages
    if total_pages > 1:
        logger.info("scraping search pagination ({} more pages)", total_pages - 1)
        for page in range(2, total_pages + 1):
            sep = "&" if "?" in url else "?"
            page_url = f"{url}{sep}page={page}"
            page_html = await _fetch_rendered_html(page_url, ready_selector="div[data-search-results-lg]")
            items.extend(parse_search(page_html)["search_data"])
    logger.success("scraped {} listings from {}", len(items), url)
    return items

async def scrape_product(urls: List[str]) -> List[Dict[str, Any]]:
    """Scrape Etsy /listing/<id> product pages, returning JSON-LD Product dicts."""
    products: List[Dict[str, Any]] = []
    for url in urls:
        logger.info("scraping product {}", url)
        html = await _fetch_rendered_html(url, ready_selector="script[type='application/ld+json']")
        products.append(parse_product_page(html))
    logger.success("scraped {} product listings", len(products))
    return products

async def scrape_shop(urls: List[str]) -> List[Dict[str, Any]]:
    """Scrape Etsy /shop/<name> pages, returning JSON-LD ItemList dicts with `url`."""
    shops: List[Dict[str, Any]] = []
    for url in urls:
        logger.info("scraping shop {}", url)
        html = await _fetch_rendered_html(url, ready_selector="script[type='application/ld+json']")
        shops.append(parse_shop_page(html, url))
    logger.success("scraped {} shop pages", len(shops))
    return shops

def to_dict(obj: Any) -> Any:
    """Identity for dicts/lists — kept for API parity with the other scrapers."""
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
