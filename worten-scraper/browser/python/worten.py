"""Worten scraper using the official Scrapeless Python SDK + Playwright over CDP.

Worten ships every `/produtos/<slug>-<id>` page with a schema.org Product `ld+json`
blob plus a BreadcrumbList ld+json. Category landing pages (`/promocoes/...`,
`/informatica-e-acessorios/...`) are SSR'd shells: product tiles render later via
Constructor.io + Turnstile, so we capture the breadcrumb / heading / meta only.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, List, Optional, TypedDict

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "PT"
DEFAULT_SESSION_TTL = 240
ORIGIN = "https://www.worten.pt"


class Product(TypedDict, total=False):
    sku: str
    name: str
    brand: Optional[str]
    description: Optional[str]
    image: Optional[str]
    price: Optional[str]
    priceCurrency: Optional[str]
    availability: Optional[str]
    ratingValue: Optional[float]
    reviewCount: Optional[int]
    url: str
    breadcrumb: List[Dict[str, Any]]


class Category(TypedDict, total=False):
    name: str
    title: Optional[str]
    description: Optional[str]
    url: str
    breadcrumb: List[Dict[str, Any]]


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
    settle_ms: int = 5000,
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
                await page.set_extra_http_headers({"accept-language": "pt-PT,pt;q=0.9,en;q=0.5"})
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


def _find_product(blocks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for b in blocks:
        if str(b.get("@type") or "").lower() == "product":
            return b
    return None


def _find_breadcrumb(blocks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for b in blocks:
        if b.get("@type") == "BreadcrumbList":
            return b
    return None


def _abs_url(u: Optional[str]) -> Optional[str]:
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

    offers = prod.get("offers")
    offer = offers[0] if isinstance(offers, list) else (offers or {})
    rating = prod.get("aggregateRating") or {}

    image = prod.get("image")
    if isinstance(image, list):
        image = image[0] if image else None

    return {
        "sku": str(prod.get("sku") or ""),
        "name": prod.get("name") or "",
        "brand": (prod.get("brand") or {}).get("name") if isinstance(prod.get("brand"), dict) else None,
        "description": prod.get("description"),
        "image": _abs_url(image),
        "price": str(offer.get("price")) if offer.get("price") is not None else None,
        "priceCurrency": offer.get("priceCurrency"),
        "availability": offer.get("availability"),
        "ratingValue": float(rating["ratingValue"]) if rating.get("ratingValue") is not None else None,
        "reviewCount": int(rating["reviewCount"]) if rating.get("reviewCount") is not None else None,
        "url": _abs_url(prod.get("url")) or url,
        "breadcrumb": breadcrumb,
    }


async def scrape_product(product_url: str) -> Product:
    url = product_url if product_url.startswith("http") else f"{ORIGIN}{'' if product_url.startswith('/') else '/'}{product_url}"
    html = await _fetch_rendered_html(url, 'script[type="application/ld+json"]')
    return parse_product(html, url)


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------

def parse_category(html: str, url: str) -> Category:
    sel = Selector(text=html)
    blocks = _ld_blocks(html)
    breadcrumb_ld = _find_breadcrumb(blocks)
    breadcrumb = [
        {"name": b.get("name"), "url": b.get("item"), "position": b.get("position")}
        for b in (breadcrumb_ld.get("itemListElement") if breadcrumb_ld else []) or []
    ]
    return {
        "name": (sel.css("h1::text").get() or "").strip(),
        "title": (sel.css("title::text").get() or "").strip() or None,
        "description": sel.css('meta[name="description"]::attr(content)').get(),
        "url": url,
        "breadcrumb": breadcrumb,
    }


async def scrape_category(category_url: str) -> Category:
    url = category_url if category_url.startswith("http") else f"{ORIGIN}{'' if category_url.startswith('/') else '/'}{category_url}"
    html = await _fetch_rendered_html(url, "h1")
    return parse_category(html, url)


def to_dict(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
