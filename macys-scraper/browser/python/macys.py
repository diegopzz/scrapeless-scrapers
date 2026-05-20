"""Macy's scraper using the official Scrapeless Python SDK + Playwright over CDP.

Surfaces:
- scrape_product(urls)                  -> list of Product dicts (PDP fields lifted from JSON-LD)
- scrape_search(category_url, max_pages) -> list of SearchResult dicts (PLP tiles)

Macys.com is fronted by Akamai Bot Manager. We warm up each session by hitting the
homepage first, then navigate to the target with a referer set; we also rotate
sessions on a 403/Access Denied response.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 240
HOME = "https://www.macys.com/"

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
    retries: int = 3,
) -> str:
    last_error: Optional[Exception] = None
    for attempt in range(retries + 1):
        if attempt > 0:
            # Back off between session attempts to give Akamai's rate-limit some headroom.
            await asyncio.sleep(15)
        client = _client()
        session = client.browser.create(
            ICreateBrowser(proxy_country=proxy_country, session_ttl=DEFAULT_SESSION_TTL)
        )
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
            try:
                page = await browser.new_page()
                await page.set_extra_http_headers({"accept-language": "en-US,en;q=0.9"})
                # Warm up the Akamai cookie via the homepage.
                await page.goto(HOME, wait_until="domcontentloaded", timeout=45000)
                await asyncio.sleep(4)
                try:
                    await page.evaluate("() => window.scrollBy(0, 600)")
                except Exception:
                    pass
                await asyncio.sleep(2)

                await page.goto(url, wait_until="domcontentloaded", timeout=60000, referer=HOME)
                if ready_selector:
                    try:
                        await page.wait_for_selector(ready_selector, timeout=20000)
                    except Exception as e:
                        logger.warning("wait_for_selector {!r} failed (continuing): {}", ready_selector, e)
                # Nuxt SPA: wait an extra beat for client-side JSON-LD to be injected.
                await asyncio.sleep(4)
                html = await page.content()
                title = (await page.title()) or ""
                blocked = (
                    title == "Access Denied"
                    or "Access Denied" in html
                    or re.search(r"sec-if-cpt-container|akamai-logo-msg|Powered and protected by", html, re.I)
                )
                if blocked:
                    last_error = RuntimeError("blocked by Akamai (Access Denied)")
                elif html and "<html" in html.lower():
                    return html
                else:
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

def _to_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    s = re.sub(r"[^\d.\-]", "", str(value))
    try:
        return float(s)
    except (TypeError, ValueError):
        return None

def _iter_jsonld_nodes(sel: Selector):
    for raw in sel.css('script[type="application/ld+json"]::text').getall():
        if not raw or not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        stack = list(data) if isinstance(data, list) else [data]
        while stack:
            node = stack.pop(0)
            if not isinstance(node, dict):
                continue
            graph = node.get("@graph")
            if isinstance(graph, list):
                stack.extend(graph)
            else:
                yield node

def _type_matches(node: Dict[str, Any], wanted: str) -> bool:
    t = node.get("@type")
    if isinstance(t, str):
        return t == wanted
    if isinstance(t, list):
        return wanted in t
    return False

def _short_availability(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    return value.rsplit("/", 1)[-1] if "/" in value else value

_ID_RE = re.compile(r"[?&]ID=(\d+)", re.I)

def _extract_product_id(url: str) -> str:
    if not url:
        return ""
    try:
        qs = parse_qs(urlparse(url).query)
        if "ID" in qs and qs["ID"]:
            return qs["ID"][0]
    except Exception:
        pass
    m = _ID_RE.search(url)
    return m.group(1) if m else ""

# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_product(html: str, url: str) -> Dict[str, Any]:
    sel = Selector(text=html)

    ld: Optional[Dict[str, Any]] = None
    for node in _iter_jsonld_nodes(sel):
        if _type_matches(node, "Product"):
            ld = node
            break
    if not ld:
        body_text = (sel.css("p::text").get() or "").lower()
        if "no longer available" in body_text:
            reason = "product retired"
        elif "Access Denied" in html:
            reason = "Akamai Access Denied"
        else:
            reason = "no Product JSON-LD found"
        raise RuntimeError(f"macys: {reason} for {url}")

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
        images = sel.css('meta[property="og:image"]::attr(content)').getall()

    brand = None
    brand_node = ld.get("brand")
    if isinstance(brand_node, dict):
        brand = brand_node.get("name")
    elif isinstance(brand_node, str):
        brand = brand_node

    product_id = str(ld.get("productID")) if ld.get("productID") else _extract_product_id(url)

    return {
        "id": product_id or "",
        "url": url,
        "name": _clean(ld.get("name"))
                or _clean(sel.css("h1::text").get())
                or _clean(sel.css('[data-auto="product-name"]::text').get())
                or "",
        "brand": _clean(brand),
        "description": _clean(ld.get("description"))
                       or _clean(sel.css('meta[name="description"]::attr(content)').get()),
        "price": _to_number(offer.get("price")),
        "priceCurrency": offer.get("priceCurrency"),
        "availability": _short_availability(offer.get("availability")),
        "images": images,
        "rating": float(rating["ratingValue"]) if rating.get("ratingValue") else None,
        "reviewCount": int(rating["reviewCount"]) if rating.get("reviewCount") else None,
        "sku": str(ld.get("sku")) if ld.get("sku") else None,
    }

def parse_search(html: str) -> List[Dict[str, Any]]:
    sel = Selector(text=html)
    items: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for a in sel.css('a[href*="ID="]'):
        href = a.attrib.get("href", "")
        if "/shop/product/" not in href.lower():
            continue
        abs_url = href if href.startswith("http") else f"https://www.macys.com{href}"
        pid = _extract_product_id(abs_url)
        if not pid or pid in seen:
            continue
        seen.add(pid)
        card = a.xpath("ancestor::*[self::li or contains(@data-testid,'product-tile') or contains(@data-auto,'product-tile') or contains(@class,'product-thumbnail')][1]")
        ctx = card if card else a

        name = _clean(
            ctx.css('[data-auto="product-title"]::text, [data-testid="product-title"]::text, .product-description *::text, h3::text, h2::text').get()
            or a.attrib.get("aria-label")
            or ctx.css('img::attr(alt)').get()
        ) or ""

        brand = _clean(
            ctx.css('[data-auto="product-brand"]::text, [data-testid="product-brand"]::text, .product-brand::text').get()
        )

        price_text = _clean(
            " ".join(ctx.css('[data-auto="product-price"] *::text, [data-testid="product-price"] *::text, .price-reg *::text, .pricing *::text').getall())
        )
        price = _to_number(price_text)

        image = ctx.css('img::attr(src)').get() or ctx.css('img::attr(data-src)').get()

        items.append({
            "id": pid,
            "url": abs_url,
            "name": name,
            "brand": brand,
            "image": image,
            "price": price,
            "priceCurrency": "USD" if price_text and "$" in price_text else None,
        })

    return items

# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def _with_query(url: str, **params: Any) -> str:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    for k, v in params.items():
        qs[k] = [str(v)]
    flat = [(k, vv) for k, vs in qs.items() for vv in vs]
    return urlunparse(parsed._replace(query=urlencode(flat)))

# ---------------------------------------------------------------------------
# Scrape functions
# ---------------------------------------------------------------------------

async def scrape_product(urls: List[str]) -> List[Dict[str, Any]]:
    if isinstance(urls, str):
        urls = [urls]
    out: List[Dict[str, Any]] = []
    for url in urls:
        logger.info("scraping product {}", url)
        html = await _fetch_rendered_html(url, ready_selector='script[type="application/ld+json"], h1')
        out.append(parse_product(html, url))
    return out

async def scrape_search(category_url: str, max_pages: int = 1) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        url = category_url if page == 1 else _with_query(category_url, Pageindex=page)
        logger.info("scraping search {} (page {})", url, page)
        html = await _fetch_rendered_html(url, ready_selector='a[href*="ID="]')
        out.extend(parse_search(html))
    logger.success("search returned {} items", len(out))
    return out

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
