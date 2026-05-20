"""GameStop scraper using the official Scrapeless Python SDK + Playwright over CDP.

GameStop runs on Salesforce Commerce Cloud. Detail pages ship a schema.org
Product `ld+json` (plus a BreadcrumbList ld+json). Category / search tiles use
the `.product-tile[data-pid]` markup and stamp a full structured payload into
the `data-gtmdata` attribute on each tile's primary link.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any, Dict, List, Optional, TypedDict
from urllib.parse import quote_plus

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 240
ORIGIN = "https://www.gamestop.com"
SEARCH_BASE = f"{ORIGIN}/search/"


class Offer(TypedDict, total=False):
    name: Optional[str]
    sku: Optional[str]
    price: Optional[str]
    priceCurrency: Optional[str]
    availability: Optional[str]


class Product(TypedDict, total=False):
    id: str
    name: str
    brand: Optional[str]
    description: Optional[str]
    platform: Optional[str]
    category: Optional[str]
    genre: Optional[str]
    contentRating: Optional[str]
    producer: Optional[str]
    publisher: Optional[str]
    image: Optional[str]
    url: str
    price: Optional[str]
    priceCurrency: Optional[str]
    availability: Optional[str]
    offers: List[Offer]
    breadcrumb: List[Dict[str, Any]]


class SearchResult(TypedDict, total=False):
    id: str
    name: str
    url: str
    price: Optional[str]
    salePrice: Optional[str]
    platform: Optional[str]
    image: Optional[str]
    ratingPercent: Optional[str]
    ratingCount: Optional[str]
    available: Optional[bool]
    isDigital: Optional[bool]


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
    settle_ms: int = 4000,
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
                await page.goto(url, wait_until="domcontentloaded", timeout=90000)
                if ready_selector:
                    try:
                        await page.wait_for_selector(ready_selector, timeout=45000)
                    except Exception:
                        pass
                if settle_ms > 0:
                    await asyncio.sleep(settle_ms / 1000)
                html = await page.content()
                if html and len(html) > 5000:
                    return html
                last_error = RuntimeError(f"empty/short HTML len={len(html) if html else 0}")
            except Exception as e:  # noqa: BLE001
                last_error = e
                logger.warning("attempt {} failed: {}", attempt + 1, e)
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass
    raise RuntimeError(f"giving up after {retries + 1} attempts: {last_error}")


def _ld_blocks(html: str) -> List[Dict[str, Any]]:
    sel = Selector(text=html)
    out: List[Dict[str, Any]] = []
    for raw in sel.css('script[type="application/ld+json"]::text').getall():
        try:
            out.append(json.loads(raw))
        except Exception:
            continue
    return out


def _find_by_type(blocks: List[Dict[str, Any]], type_name: str) -> Optional[Dict[str, Any]]:
    for b in blocks:
        t = b.get("@type")
        if t == type_name or (isinstance(t, list) and type_name in t):
            return b
    return None


def _abs(u: Optional[str]) -> Optional[str]:
    if not u:
        return None
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/"):
        return ORIGIN + u
    return u


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------

_PID_RE = re.compile(r"/(\d+)\.html")


def parse_product(html: str, url: str) -> Product:
    blocks = _ld_blocks(html)
    prod = _find_by_type(blocks, "Product")
    if not prod:
        raise RuntimeError("could not find Product ld+json on page")

    breadcrumb_ld = _find_by_type(blocks, "BreadcrumbList")
    breadcrumb = [
        {"name": b.get("name"), "url": b.get("item"), "position": b.get("position")}
        for b in (breadcrumb_ld.get("itemListElement") if breadcrumb_ld else []) or []
    ]

    offers_raw = prod.get("offers")
    if isinstance(offers_raw, dict):
        offers_raw = [offers_raw]
    elif not isinstance(offers_raw, list):
        offers_raw = []

    offers: List[Offer] = [
        {
            "name": o.get("name"),
            "sku": str(o.get("sku")) if o.get("sku") is not None else None,
            "price": str(o.get("price")) if o.get("price") is not None else None,
            "priceCurrency": o.get("priceCurrency"),
            "availability": o.get("availability"),
        }
        for o in offers_raw
    ]
    first_offer: Offer = offers[0] if offers else {}

    sel = Selector(text=html)
    pid = sel.css("[data-product-id]::attr(data-product-id)").get() or ""
    if not pid:
        m = _PID_RE.search(url)
        if m:
            pid = m.group(1)

    return {
        "id": str(pid),
        "name": prod.get("name") or "",
        "brand": prod.get("brand"),
        "description": prod.get("description"),
        "platform": prod.get("gamePlatform"),
        "category": prod.get("category"),
        "genre": prod.get("genre"),
        "contentRating": prod.get("contentRating"),
        "producer": prod.get("producer"),
        "publisher": prod.get("publisher"),
        "image": prod.get("image") if isinstance(prod.get("image"), str) else None,
        "url": prod.get("url") or url,
        "price": first_offer.get("price"),
        "priceCurrency": first_offer.get("priceCurrency"),
        "availability": first_offer.get("availability"),
        "offers": offers,
        "breadcrumb": breadcrumb,
    }


async def scrape_product(product_url: str) -> Product:
    url = product_url if product_url.startswith("http") else f"{ORIGIN}{'' if product_url.startswith('/') else '/'}{product_url}"
    html = await _fetch_rendered_html(url, 'script[type="application/ld+json"]')
    return parse_product(html, url)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def _parse_gtm(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def parse_search(html: str) -> List[SearchResult]:
    sel = Selector(text=html)
    out: List[SearchResult] = []
    for tile in sel.css(".product-tile"):
        pid = tile.attrib.get("data-pid") or tile.attrib.get("id") or ""
        anchor = tile.css("a.pdp-link, a.product-tile-link")
        if not anchor:
            continue
        gtm = _parse_gtm(anchor.attrib.get("data-gtmdata"))
        url = anchor.attrib.get("href") or ""
        if url and not url.startswith("http"):
            url = _abs(url) or ""
        name = (gtm or {}).get("name") or anchor.attrib.get("aria-label") or anchor.attrib.get("title") or ""
        if not pid or not url or not name:
            continue
        platforms = (gtm or {}).get("productPlatform") or []
        if not isinstance(platforms, list):
            platforms = []
        price = (((gtm or {}).get("price") or {}) or {}).get("base")
        sale = (((gtm or {}).get("price") or {}) or {}).get("sale")
        out.append(
            {
                "id": str(pid),
                "name": name,
                "url": url,
                "price": str(price) if price is not None else None,
                "salePrice": str(sale) if sale is not None else None,
                "platform": platforms[0] if platforms else None,
                "image": (((gtm or {}).get("image") or {}) or {}).get("base"),
                "ratingPercent": str((((gtm or {}).get("ratings") or {}) or {}).get("percentage")) if ((gtm or {}).get("ratings") or {}).get("percentage") is not None else None,
                "ratingCount": str((((gtm or {}).get("ratings") or {}) or {}).get("count")) if ((gtm or {}).get("ratings") or {}).get("count") is not None else None,
                "available": (((gtm or {}).get("availability") or {}) or {}).get("available"),
                "isDigital": (((gtm or {}).get("availability") or {}) or {}).get("isDigitalProduct"),
            }
        )
    return out


async def scrape_search(query: str, max_pages: int = 1) -> List[SearchResult]:
    out: List[SearchResult] = []
    for page in range(1, max_pages + 1):
        url = f"{SEARCH_BASE}?q={quote_plus(query)}"
        if page > 1:
            url += f"&start={(page - 1) * 20}&sz=20"
        html = await _fetch_rendered_html(url, ".product-tile")
        out.extend(parse_search(html))
    return out


async def scrape_category(category_url: str) -> List[SearchResult]:
    url = category_url if category_url.startswith("http") else f"{ORIGIN}{'' if category_url.startswith('/') else '/'}{category_url}"
    html = await _fetch_rendered_html(url, ".product-tile")
    return parse_search(html)


def to_dict(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
