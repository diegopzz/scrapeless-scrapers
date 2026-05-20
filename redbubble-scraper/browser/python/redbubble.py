"""Redbubble scraper using the official Scrapeless Python SDK + Playwright over CDP.

Surfaces:
- scrape_product(urls)          -> list of Product dicts (PDP fields lifted from JSON-LD + __NEXT_DATA__)
- scrape_search(query, max_pages) -> list of SearchResult dicts (PLP cards from __NEXT_DATA__)

Redbubble pages are Next.js-rendered, so `__NEXT_DATA__` is the primary source of truth.
We fall back to JSON-LD Product on the PDP and to anchor scraping on the PLP.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote

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

async def _fetch_rendered_html(
    url: str,
    ready_selector: Optional[str] = None,
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
    retries: int = 1,
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
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                if ready_selector:
                    try:
                        await page.wait_for_selector(ready_selector, timeout=15000)
                    except Exception as e:
                        logger.warning("wait_for_selector {!r} failed (continuing): {}", ready_selector, e)
                html = await page.content()
                if html and "<html" in html.lower():
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = re.sub(r"\s+", " ", str(value)).strip()
    return s or None

def _read_next_data(sel: Selector) -> Dict[str, Any]:
    raw = sel.css('script#__NEXT_DATA__::text').get()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}

def _iter_jsonld_nodes(sel: Selector):
    for raw in sel.css('script[type="application/ld+json"]::text').getall():
        if not raw or not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if isinstance(node, dict):
                yield node

def _type_matches(node: Dict[str, Any], wanted: str) -> bool:
    t = node.get("@type")
    if isinstance(t, str):
        return t == wanted
    if isinstance(t, list):
        return wanted in t
    return False

_PDP_URL_RE = re.compile(r"/i/([^/]+)/([^/]+?)(?:-by-([^/]+))?/(\d+)/[a-z0-9]+", re.I)

def _parse_pdp_url(url: str) -> Dict[str, Optional[str]]:
    if not url:
        return {"medium": None, "artist": None, "workId": None}
    m = _PDP_URL_RE.search(url)
    if not m:
        return {"medium": None, "artist": None, "workId": None}
    return {"medium": m.group(1) or None, "artist": m.group(3) or None, "workId": m.group(4) or None}

def _short_availability(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    return value.rsplit("/", 1)[-1] if "/" in value else value

def _to_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    s = re.sub(r"[^\d.\-]", "", str(value))
    try:
        return float(s)
    except (TypeError, ValueError):
        return None

# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_product(html: str, url: str) -> Dict[str, Any]:
    sel = Selector(text=html)
    next_data = _read_next_data(sel)
    pp = (next_data.get("props") or {}).get("pageProps") or {}

    ld: Dict[str, Any] = {}
    for node in _iter_jsonld_nodes(sel):
        if _type_matches(node, "Product"):
            ld = node
            break

    offers = ld.get("offers")
    if isinstance(offers, list) and offers:
        offer = offers[0] if isinstance(offers[0], dict) else {}
    elif isinstance(offers, dict):
        offer = offers
    else:
        offer = {}

    rating = ld.get("aggregateRating") if isinstance(ld.get("aggregateRating"), dict) else {}

    images_raw = ld.get("image")
    if isinstance(images_raw, str):
        images = [images_raw]
    elif isinstance(images_raw, list):
        images = [str(x) for x in images_raw if x]
    else:
        images = []

    parsed = _parse_pdp_url(url)
    item = pp.get("initialInventoryItem") or {}
    review_summary = pp.get("reviewSummary") or {}

    price = _to_number((item.get("price") or {}).get("amount") if isinstance(item.get("price"), dict) else None)
    if price is None:
        price = _to_number(offer.get("price"))

    currency = None
    if isinstance(item.get("price"), dict):
        currency = item["price"].get("currency")
    if not currency:
        currency = offer.get("priceCurrency")

    rating_value = None
    if rating.get("ratingValue") is not None:
        try:
            rating_value = float(rating["ratingValue"])
        except (TypeError, ValueError):
            rating_value = None
    if rating_value is None and review_summary.get("rating") is not None:
        try:
            rating_value = float(review_summary["rating"])
        except (TypeError, ValueError):
            rating_value = None

    review_count = None
    for key in ("ratingCount", "reviewCount"):
        if rating.get(key) is not None:
            try:
                review_count = int(rating[key]); break
            except (TypeError, ValueError):
                pass
    if review_count is None and review_summary.get("count") is not None:
        try:
            review_count = int(review_summary["count"])
        except (TypeError, ValueError):
            review_count = None

    work_id = parsed["workId"] or (str(item.get("workId")) if item.get("workId") is not None else "")

    return {
        "id": work_id or "",
        "url": url,
        "name": _clean(ld.get("name")) or "",
        "description": _clean(ld.get("description")),
        "medium": parsed["medium"],
        "artist": parsed["artist"],
        "price": price,
        "priceCurrency": currency,
        "availability": _short_availability(offer.get("availability")),
        "images": images,
        "rating": rating_value,
        "reviewCount": review_count,
    }

def parse_search(html: str) -> List[Dict[str, Any]]:
    sel = Selector(text=html)
    next_data = _read_next_data(sel)
    rows = ((next_data.get("props") or {}).get("pageProps") or {}).get("results") or []
    items: List[Dict[str, Any]] = []

    for row in rows:
        inv = row.get("inventoryItem") if isinstance(row, dict) else None
        if not isinstance(inv, dict):
            continue
        work = inv.get("work") if isinstance(inv.get("work"), dict) else {}
        url = inv.get("productPageUrl")
        if not url:
            urls = inv.get("productPageUrls")
            url = urls.get("url") if isinstance(urls, dict) else ""
        parsed = _parse_pdp_url(url or "")
        work_id = parsed["workId"] or (str(inv.get("workId")) if inv.get("workId") is not None else work.get("id"))
        previews = (inv.get("previewSet") or {}).get("previews") if isinstance(inv.get("previewSet"), dict) else None
        image = None
        if isinstance(previews, list) and previews:
            image = previews[0].get("url") if isinstance(previews[0], dict) else None
        price = _to_number((inv.get("price") or {}).get("amount") if isinstance(inv.get("price"), dict) else None)
        currency = None
        if isinstance(inv.get("price"), dict):
            currency = inv["price"].get("currency")
        items.append({
            "id": str(work_id or ""),
            "url": url or "",
            "name": _clean(work.get("title")) or "",
            "artist": parsed["artist"] or _clean(work.get("artistUsername")),
            "medium": parsed["medium"],
            "image": str(image) if image else None,
            "price": price,
            "priceCurrency": currency,
        })

    if not items:
        # DOM fallback — anchors with /i/<medium>/.../<workId>/<token>
        seen: set[str] = set()
        for a in sel.css('a[href*="/i/"]'):
            href = a.attrib.get("href", "")
            if not _PDP_URL_RE.search(href):
                continue
            abs_url = href if href.startswith("http") else f"https://www.redbubble.com{href}"
            parsed = _parse_pdp_url(abs_url)
            wid = parsed["workId"]
            if not wid or wid in seen:
                continue
            seen.add(wid)
            card = a.xpath("ancestor::div[1]")
            name = _clean(card.css("h3::text, h2::text").get()) or _clean(a.attrib.get("aria-label"))
            price_text = _clean(card.css('[class*="Price_"] *::text').get())
            items.append({
                "id": wid,
                "url": abs_url,
                "name": name or "",
                "artist": parsed["artist"],
                "medium": parsed["medium"],
                "image": card.css("img::attr(src)").get(),
                "price": _to_number(price_text),
                "priceCurrency": "USD" if price_text and "$" in price_text else None,
            })

    return items

# ---------------------------------------------------------------------------
# Scrape functions
# ---------------------------------------------------------------------------

async def scrape_product(urls: List[str]) -> List[Dict[str, Any]]:
    if isinstance(urls, str):
        urls = [urls]
    out: List[Dict[str, Any]] = []
    for url in urls:
        logger.info("scraping product {}", url)
        html = await _fetch_rendered_html(url, ready_selector='script[type="application/ld+json"]')
        out.append(parse_product(html, url))
    return out

async def scrape_search(query: str, max_pages: int = 1) -> List[Dict[str, Any]]:
    base = f"https://www.redbubble.com/shop/{quote(query, safe='')}"
    out: List[Dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        url = base if page == 1 else f"{base}?page={page}"
        logger.info("scraping search {} (page {})", url, page)
        html = await _fetch_rendered_html(url, ready_selector='script#__NEXT_DATA__')
        out.extend(parse_search(html))
    logger.success("search {!r} returned {} items", query, len(out))
    return out

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
