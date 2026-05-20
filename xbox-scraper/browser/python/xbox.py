"""Xbox scraper using the official Scrapeless Python SDK + Playwright over CDP.

xbox.com store pages ship a single `application/ld+json` script that wraps
every node under `@graph`. The Product/VideoGame entry inside it carries the
full structured payload (offers, ratings, videos, ESRB rating). The /games
hub pages (e.g. /en-us/games/all-games) render game tiles as simple
`<a href="/games/store/<slug>/<storeId>">` anchors that we lift directly from
the SSR HTML.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any, Dict, List, Optional, TypedDict

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 240
ORIGIN = "https://www.xbox.com"
ALL_GAMES_PATH = "/en-us/games/all-games"

STORE_ID_RE = re.compile(r"/games/store/[^/]+/([A-Za-z0-9]+)")
TILE_RE = re.compile(r"/games/store/([^/?#]+)/([A-Za-z0-9]{6,})", re.IGNORECASE)


class VideoEntry(TypedDict, total=False):
    name: Optional[str]
    thumbnailUrl: Optional[str]
    contentUrl: Optional[str]


class Product(TypedDict, total=False):
    id: str
    name: str
    description: Optional[str]
    url: str
    image: Optional[str]
    publisher: Optional[str]
    developer: Optional[str]
    brand: Optional[str]
    genre: List[str]
    platforms: List[str]
    contentRating: Optional[str]
    releaseDate: Optional[str]
    ratingValue: Optional[float]
    ratingCount: Optional[int]
    price: Optional[str]
    priceCurrency: Optional[str]
    availability: Optional[str]
    isFree: Optional[bool]
    featureList: Optional[str]
    videos: List[VideoEntry]


class SearchResult(TypedDict, total=False):
    id: str
    slug: str
    name: str
    url: str
    image: Optional[str]
    badge: Optional[str]


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


def _ld_graph(html: str) -> List[Dict[str, Any]]:
    sel = Selector(text=html)
    out: List[Dict[str, Any]] = []
    for raw in sel.css('script[type="application/ld+json"]::text').getall():
        try:
            obj = json.loads(raw)
            graph = obj.get("@graph")
            if isinstance(graph, list):
                out.extend(graph)
            else:
                out.append(obj)
        except Exception:
            continue
    return out


def _find_product(graph: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for n in graph:
        t = n.get("@type")
        if t == "Product" or (isinstance(t, list) and "Product" in t):
            return n
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

def parse_product(html: str, url: str) -> Product:
    graph = _ld_graph(html)
    prod = _find_product(graph)
    if not prod:
        raise RuntimeError("could not find Product node in ld+json @graph")

    m = STORE_ID_RE.search(url)
    pid = m.group(1) if m else ""

    offers_raw = prod.get("offers")
    if isinstance(offers_raw, dict):
        offers_raw = [offers_raw]
    elif not isinstance(offers_raw, list):
        offers_raw = []
    first_offer = offers_raw[0] if offers_raw else {}

    image = prod.get("image")
    if isinstance(image, list):
        image_first = image[0] if image else None
    else:
        image_first = image

    videos_raw = prod.get("video")
    if isinstance(videos_raw, dict):
        videos_raw = [videos_raw]
    elif not isinstance(videos_raw, list):
        videos_raw = []
    videos: List[VideoEntry] = [
        {
            "name": v.get("name"),
            "thumbnailUrl": v.get("thumbnailUrl"),
            "contentUrl": v.get("contentUrl"),
        }
        for v in videos_raw
    ]

    rating = prod.get("aggregateRating") or {}
    genre = prod.get("genre")
    if isinstance(genre, str):
        genre = [genre]
    elif not isinstance(genre, list):
        genre = []
    platforms = prod.get("gamePlatform")
    if isinstance(platforms, str):
        platforms = [platforms]
    elif not isinstance(platforms, list):
        platforms = []

    return {
        "id": pid,
        "name": prod.get("name") or "",
        "description": prod.get("description"),
        "url": prod.get("url") or url,
        "image": image_first,
        "publisher": (prod.get("publisher") or {}).get("name") if isinstance(prod.get("publisher"), dict) else None,
        "developer": (prod.get("creator") or {}).get("name") if isinstance(prod.get("creator"), dict) else None,
        "brand": (prod.get("brand") or {}).get("name") if isinstance(prod.get("brand"), dict) else None,
        "genre": genre,
        "platforms": platforms,
        "contentRating": prod.get("contentRating"),
        "releaseDate": prod.get("datePublished"),
        "ratingValue": float(rating["ratingValue"]) if rating.get("ratingValue") is not None else None,
        "ratingCount": int(rating["ratingCount"]) if rating.get("ratingCount") is not None else None,
        "price": str(first_offer.get("price")) if first_offer.get("price") is not None else None,
        "priceCurrency": first_offer.get("priceCurrency"),
        "availability": first_offer.get("availability"),
        "isFree": prod.get("isAccessibleForFree"),
        "featureList": prod.get("featureList"),
        "videos": videos,
    }


async def scrape_product(product_url: str) -> Product:
    url = product_url if product_url.startswith("http") else f"{ORIGIN}{'' if product_url.startswith('/') else '/'}{product_url}"
    html = await _fetch_rendered_html(url, 'script[type="application/ld+json"]')
    return parse_product(html, url)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def _aria_to_parts(label: Optional[str]) -> Dict[str, Optional[str]]:
    if not label:
        return {"name": None, "badge": None}
    cleaned = re.sub(r"\.\s*Opens in a new tab\s*$", "", label, flags=re.IGNORECASE).strip()
    parts = cleaned.split(". ")
    if len(parts) >= 2 and re.match(r"^[A-Z0-9 +!&'-]+$", parts[0]):
        return {"badge": parts[0].strip(), "name": parts[1].strip()}
    return {"badge": None, "name": parts[0].strip() if parts else None}


def parse_search(html: str) -> List[SearchResult]:
    sel = Selector(text=html)
    seen: set[str] = set()
    out: List[SearchResult] = []
    for a in sel.css("a[href*='/games/store/']"):
        href = a.attrib.get("href") or ""
        m = TILE_RE.search(href)
        if not m:
            continue
        if "?icid=CNav" in href:
            continue
        pid = m.group(2)
        if pid in seen:
            continue
        seen.add(pid)
        if not href.startswith("http"):
            href = _abs(href) or ""
        aria = a.attrib.get("aria-label") or ""
        inner_title = (
            (a.css("h3::text, h2::text, span.c-meta-h3::text").get() or "").strip()
        )
        if not inner_title:
            inner_title = (a.css("[class*='title' i]::text, [class*='Title']::text").get() or "").strip()
        parts = _aria_to_parts(aria)
        name = inner_title or parts["name"] or m.group(1).replace("-", " ")
        if not name:
            continue
        img = a.css("img::attr(src)").get()
        out.append(
            {
                "id": pid,
                "slug": m.group(1),
                "name": name,
                "url": href,
                "image": img,
                "badge": parts["badge"],
            }
        )
    return out


async def scrape_search(query: str, max_pages: int = 1) -> List[SearchResult]:
    """Xbox.com lists games via /games/all-games rather than a true SERP."""
    _ = query  # kept for API parity
    out: List[SearchResult] = []
    for page in range(1, max_pages + 1):
        url = f"{ORIGIN}{ALL_GAMES_PATH}"
        if page > 1:
            url += f"?page={page}"
        html = await _fetch_rendered_html(url, "a[href*='/games/store/']")
        out.extend(parse_search(html))
    return out


def to_dict(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
