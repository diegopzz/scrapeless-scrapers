"""Bunnings scraper using the official Scrapeless Python SDK + Playwright over CDP.

Bunnings ships every product page with a schema.org `ld+json` Product blob plus a
BreadcrumbList ld+json. The keyword-search page is a Coveo SPA, so the result tiles
(`[data-testid="productTileContainer"]`) are parsed after the front-end renders.
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

DEFAULT_PROXY_COUNTRY = "AU"
DEFAULT_SESSION_TTL = 240
ORIGIN = "https://www.bunnings.com.au"
SEARCH_BASE = f"{ORIGIN}/search/products"


class Product(TypedDict, total=False):
    sku: str
    name: str
    brand: Optional[str]
    brandLogo: Optional[str]
    description: Optional[str]
    category: Optional[str]
    image: Optional[str]
    price: Optional[str]
    priceCurrency: Optional[str]
    url: str
    warranty: Optional[str]
    breadcrumb: List[Dict[str, Any]]


class SearchResult(TypedDict, total=False):
    sku: str
    title: str
    url: str
    price: Optional[str]
    image: Optional[str]
    rating: Optional[str]


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
    settle_ms: int = 6000,
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
                        await page.wait_for_selector(ready_selector, timeout=60000)
                    except Exception:
                        pass
                if settle_ms > 0:
                    await asyncio.sleep(settle_ms / 1000)
                html = await page.content()
                title = await page.title()
                if "Access Denied" in title or "Cloudflare" in title or (html and len(html) < 5000):
                    last_error = RuntimeError(f"blocked (title={title}, len={len(html)})")
                    continue
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


def _ld_blocks(html: str) -> List[Dict[str, Any]]:
    sel = Selector(text=html)
    blocks: List[Dict[str, Any]] = []
    for raw in sel.css('script[type="application/ld+json"]::text').getall():
        try:
            blocks.append(json.loads(raw))
        except Exception:
            continue
    return blocks


def _find_product(blocks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for b in blocks:
        t = b.get("@type")
        if t == "Product" or (isinstance(t, list) and "Product" in t):
            return b
    return None


def _find_breadcrumb(blocks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for b in blocks:
        if b.get("@type") == "BreadcrumbList":
            return b
    return None


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------

def parse_product(html: str, url: str) -> Product:
    blocks = _ld_blocks(html)
    prod = _find_product(blocks)
    if not prod:
        raise RuntimeError("could not find Product ld+json on page")

    breadcrumb_ld = _find_breadcrumb(blocks)
    breadcrumb = [
        {"name": b.get("name"), "url": b.get("item"), "position": b.get("position")}
        for b in (breadcrumb_ld.get("itemListElement") if breadcrumb_ld else []) or []
    ]

    warranty: Optional[str] = None
    ap = prod.get("additionalProperty")
    if ap:
        items = ap if isinstance(ap, list) else [ap]
        for entry in items:
            if "warranty" in (entry.get("name") or "").lower():
                warranty = entry.get("value")
                break

    offers = prod.get("offers")
    offer = offers[0] if isinstance(offers, list) else (offers or {})

    return {
        "sku": str(prod.get("sku") or ""),
        "name": prod.get("name") or "",
        "brand": (prod.get("brand") or {}).get("name") if isinstance(prod.get("brand"), dict) else None,
        "brandLogo": (prod.get("brand") or {}).get("logo") if isinstance(prod.get("brand"), dict) else None,
        "description": prod.get("description"),
        "category": prod.get("category"),
        "image": prod.get("image") if isinstance(prod.get("image"), str) else None,
        "price": str(offer.get("price")) if offer.get("price") is not None else None,
        "priceCurrency": offer.get("priceCurrency"),
        "url": prod.get("url") or url,
        "warranty": warranty,
        "breadcrumb": breadcrumb,
    }


async def scrape_product(product_url: str) -> Product:
    url = product_url if product_url.startswith("http") else f"{ORIGIN}{'' if product_url.startswith('/') else '/'}{product_url}"
    html = await _fetch_rendered_html(url, 'script[type="application/ld+json"]')
    return parse_product(html, url)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

_SKU_RE = re.compile(r"_p(\d+)")


def parse_search(html: str) -> List[SearchResult]:
    sel = Selector(text=html)
    out: List[SearchResult] = []
    for tile in sel.css("[data-testid='productTileContainer']"):
        a = tile.css("a").xpath(".")[0] if tile.css("a") else None
        href = (a.attrib.get("href") if a is not None else "") or ""
        if href and not href.startswith("http"):
            href = f"{ORIGIN}{'' if href.startswith('/') else '/'}{href}"
        m = _SKU_RE.search(href)
        sku = m.group(1) if m else ""
        title = (tile.css(".product-title::text").get() or "").strip()
        if not title and a is not None:
            title = (a.attrib.get("title") or "").strip()
        price = tile.css("[data-testid='price-link']::text").get()
        if price is not None:
            price = price.strip() or None
        image = tile.css("img.product-tile-image::attr(src)").get()
        rating = tile.css("[role='img'][aria-label*='Rating']::attr(aria-label)").get()
        if not title or not href:
            continue
        out.append({"sku": sku, "title": title, "url": href, "price": price, "image": image, "rating": rating})
    return out


async def scrape_search(query: str, max_pages: int = 1) -> List[SearchResult]:
    out: List[SearchResult] = []
    for page in range(1, max_pages + 1):
        url = f"{SEARCH_BASE}?q={quote_plus(query)}"
        if page > 1:
            url += f"&page={page}"
        html = await _fetch_rendered_html(url, "[data-testid='productTileContainer']")
        out.extend(parse_search(html))
    return out


def to_dict(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
