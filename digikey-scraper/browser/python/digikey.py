"""Digi-Key scraper using the official Scrapeless Python SDK + Playwright over CDP.

Under the hood:
- `client.browser.create()` mints a cloud session on Scrapeless's Scraping Browser,
  returning a CDP WebSocket endpoint (`browser_ws_endpoint`).
- Playwright connects to that WebSocket, drives the page, returns rendered HTML.
- The embedded `#__NEXT_DATA__` script ships every server-rendered Digi-Key page
  payload. Both the detail page (`envelope.type == "detail-page"`) and the
  keyword-search page (`envelope.type == "result-page"`) expose their data under
  `props.pageProps.envelope.data`.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, TypedDict
from urllib.parse import quote_plus

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 240
SEARCH_BASE = "https://www.digikey.com/en/products/result"


class Stock(TypedDict, total=False):
    quantityAvailable: Optional[str]
    hasLeadTime: bool
    leadTime: Optional[str]
    minimumOrderQuantity: Optional[int]
    packaging: Optional[str]


class Product(TypedDict, total=False):
    digikeyPartNumber: str
    manufacturerPartNumber: str
    manufacturer: str
    title: str
    description: Optional[str]
    detailedDescription: Optional[str]
    datasheetUrl: Optional[str]
    productUrl: str
    imageUrl: Optional[str]
    media: List[str]
    breadcrumb: List[Dict[str, Any]]
    attributes: List[Dict[str, Any]]
    pricing: List[Dict[str, Any]]
    stock: Stock
    isActive: bool
    isUnavailable: bool


class SearchResult(TypedDict, total=False):
    id: str
    categoryName: str
    parentCategory: Optional[str]
    productCount: str
    categoryUrl: str
    imageUrl: Optional[str]


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
                await page.set_viewport_size({"width": 1366, "height": 800})
                await page.goto(url, wait_until="domcontentloaded", timeout=90000)
                # Cloudflare interstitial: wait for the __NEXT_DATA__ payload (Digi-Key
                # ships it server-side on every real page). Up to 120 s; CF usually clears
                # in 5-20 s.
                try:
                    await page.wait_for_selector("script#__NEXT_DATA__", timeout=120000)
                except Exception:
                    pass
                html = await page.content()
                title = await page.title()
                if (
                    "Cloudflare" in title
                    or "Attention Required" in title
                    or "Just a moment" in title
                ):
                    last_error = RuntimeError(f"blocked by Cloudflare (title={title})")
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


def _extract_next_data(html: str) -> Optional[Dict[str, Any]]:
    sel = Selector(text=html)
    raw = sel.css("#__NEXT_DATA__::text").get()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _envelope_data(html: str) -> Optional[Dict[str, Any]]:
    nd = _extract_next_data(html)
    if not nd:
        return None
    return ((nd.get("props") or {}).get("pageProps") or {}).get("envelope", {}).get("data")


def _abs_url(u: Optional[str]) -> Optional[str]:
    if not u:
        return None
    if u.startswith("//"):
        return "https:" + u
    return u


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------

def parse_product(html: str, url: str) -> Product:
    data = _envelope_data(html)
    if not data:
        raise RuntimeError("could not parse __NEXT_DATA__ from product page")
    overview = data.get("productOverview") or {}
    pq = data.get("priceQuantity") or {}
    carousel = data.get("carouselMedia") or []
    breadcrumb = [
        {"label": b.get("label"), "url": b.get("url")}
        for b in (data.get("breadcrumb") or [])
    ]

    attrs = ((data.get("productAttributes") or {}).get("attributes")) or []
    attributes: List[Dict[str, Any]] = []
    for a in attrs:
        values = [v.get("value") for v in (a.get("values") or []) if v.get("value")]
        attributes.append(
            {
                "label": a.get("label"),
                "value": ", ".join(values) if values else None,
            }
        )

    pricing_tiers = ((pq.get("pricing") or [{}])[0]).get("mergedPricingTiers") or []
    pricing = [
        {
            "breakQuantity": t.get("brkQty"),
            "unitPrice": t.get("unitPrice"),
            "extendedPrice": t.get("extPrice"),
        }
        for t in pricing_tiers
    ]

    first_pricing = (pq.get("pricing") or [{}])[0]
    stock: Stock = {
        "quantityAvailable": pq.get("qtyAvailable"),
        "hasLeadTime": bool(pq.get("hasLeadTime")),
        "leadTime": overview.get("standardLeadTime"),
        "minimumOrderQuantity": first_pricing.get("minOrderQuantity"),
        "packaging": first_pricing.get("packaging"),
    }

    part_status_attr = next(
        (a for a in attrs if (a.get("label") or "").lower() == "part status"),
        None,
    )
    is_active = False
    if part_status_attr and part_status_attr.get("values"):
        is_active = (part_status_attr["values"][0].get("value") or "").lower() == "active"

    dk_values = ((overview.get("digikeyProductNumbers") or {}).get("value")) or []
    digikey_pn = (dk_values[0] or {}).get("value") if dk_values else overview.get("rolledUpProductNumber") or ""

    return {
        "digikeyPartNumber": digikey_pn or "",
        "manufacturerPartNumber": overview.get("manufacturerProductNumber") or overview.get("title") or "",
        "manufacturer": overview.get("manufacturer") or "",
        "title": overview.get("title") or "",
        "description": overview.get("description"),
        "detailedDescription": overview.get("detailedDescription"),
        "datasheetUrl": overview.get("datasheetUrl"),
        "productUrl": url,
        "imageUrl": _abs_url(carousel[0].get("displayUrl")) if carousel else None,
        "media": [_abs_url(m.get("displayUrl")) for m in carousel if m.get("displayUrl")],
        "breadcrumb": breadcrumb,
        "attributes": attributes,
        "pricing": pricing,
        "stock": stock,
        "isActive": bool(is_active),
        "isUnavailable": bool(data.get("isUnavailable")),
    }


async def scrape_product(product_id_or_url: str) -> Product:
    url = (
        product_id_or_url
        if product_id_or_url.startswith("http")
        else f"{SEARCH_BASE}?keywords={quote_plus(product_id_or_url)}"
    )
    html = await _fetch_rendered_html(url)
    return parse_product(html, url)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def parse_search(html: str) -> List[SearchResult]:
    data = _envelope_data(html)
    if not data:
        return []
    out: List[SearchResult] = []
    for r in data.get("topResults") or []:
        out.append(
            {
                "id": str(r.get("id") or ""),
                "categoryName": r.get("categoryName") or "",
                "parentCategory": r.get("parentCategory"),
                "productCount": str(r.get("productCount") or ""),
                "categoryUrl": r.get("categoryUrl") or "",
                "imageUrl": _abs_url(r.get("imageUrl")),
            }
        )
    return out


async def scrape_search(query: str, max_pages: int = 1) -> List[SearchResult]:
    out: List[SearchResult] = []
    for page in range(1, max_pages + 1):
        url = f"{SEARCH_BASE}?keywords={quote_plus(query)}"
        if page > 1:
            url += f"&page={page}"
        html = await _fetch_rendered_html(url)
        out.extend(parse_search(html))
    return out


def to_dict(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
