"""Depop scraper using the official Scrapeless Python SDK + Playwright over CDP."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from typing import List, Optional

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 180
HOST = "https://www.depop.com"


@dataclass
class Product:
    id: str
    url: str
    title: str
    price: Optional[str] = None
    currency: Optional[str] = None
    brand: Optional[str] = None
    condition: Optional[str] = None
    size: Optional[str] = None
    color: Optional[str] = None
    description: Optional[str] = None
    images: List[str] = field(default_factory=list)
    seller: Optional[str] = None
    sellerUrl: Optional[str] = None
    hashtags: List[str] = field(default_factory=list)
    sold: bool = False


@dataclass
class SearchResult:
    id: str
    title: str
    url: str
    image: Optional[str] = None
    price: Optional[str] = None
    originalPrice: Optional[str] = None
    seller: Optional[str] = None
    size: Optional[str] = None


@dataclass
class Shop:
    username: str
    url: str
    displayName: Optional[str] = None
    bio: Optional[str] = None
    avatar: Optional[str] = None
    location: Optional[str] = None
    followers: Optional[int] = None
    following: Optional[int] = None
    reviews: Optional[int] = None
    rating: Optional[float] = None
    listings: List[dict] = field(default_factory=list)


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
    auto_scroll: bool = False,
) -> str:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        client = _client()
        session = client.browser.create(
            ICreateBrowser(proxy_country=proxy_country, session_ttl=DEFAULT_SESSION_TTL)
        )
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
            try:
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
                page = await context.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                if ready_selector:
                    try:
                        await page.wait_for_selector(ready_selector, timeout=20000)
                    except Exception as e:
                        logger.warning("wait_for_selector failed (continuing): {}", e)
                if auto_scroll:
                    try:
                        await page.evaluate(
                            "() => new Promise(r => { let y = 0; const i = setInterval(() => { window.scrollBy(0, 600); y += 600; if (y >= document.body.scrollHeight) { clearInterval(i); r(); } }, 120); })"
                        )
                        await page.wait_for_timeout(1500)
                    except Exception:
                        pass
                html = await page.content()
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


def _text(s):
    if not s:
        return None
    cleaned = re.sub(r"\s+", " ", str(s)).strip()
    return cleaned or None


def _abs(url):
    if not url:
        return None
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http"):
        return url
    return HOST + (url if url.startswith("/") else "/" + url)


def _uniq(seq):
    out, seen = [], set()
    for x in seq:
        if not x or x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def _to_float(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    m = re.sub(r"[^0-9.]", "", str(s))
    if not m:
        return None
    try:
        return float(m)
    except ValueError:
        return None


def _to_int(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return int(s)
    txt = str(s).replace(",", "").replace(" ", "")
    m = re.match(r"(-?\d+(?:\.\d+)?)\s*([kKmM])\b", txt)
    if m:
        n = float(m.group(1))
        mult = 1000 if m.group(2).lower() == "k" else 1_000_000
        return int(round(n * mult))
    digits = re.sub(r"[^0-9-]", "", txt)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _slug_from_url(url):
    if not url:
        return ""
    m = re.search(r"/products/([^/?#]+)", url)
    return m.group(1) if m else ""


def _seller_from_url(url):
    if not url:
        return None
    m = re.search(r"/products/([^-]+)-", url)
    return m.group(1) if m else None


def _extract_next_data(html):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>([\s\S]*?)</script>', html)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


# Depop's shop page is rendered through Next.js streaming (RSC). The seller
# payload ships inside a doubly-encoded JSON chunk whose raw bytes look like
# `\"seller\":{\"username\":\"…\",…,\"items_sold\":N}`. Brace-balancing across
# nested empties is brittle, so we anchor on the trailing `items_sold` sentinel
# and read scalars per-key.
_RSC_SELLER_RE = re.compile(
    r'\\"seller\\":\{.{200,2000}?\\"items_sold\\":[0-9]+',
    re.DOTALL,
)


def _extract_rsc_seller(html: str) -> str | None:
    m = _RSC_SELLER_RE.search(html)
    return m.group(0) if m else None


def _rsc_field(haystack: str, key: str):
    if not haystack:
        return None
    k = re.escape(key)
    # number / boolean / null
    m = re.search(rf'\\"{k}\\":(true|false|null|-?\d+(?:\.\d+)?)', haystack)
    if m:
        v = m.group(1)
        if v == "true":
            return True
        if v == "false":
            return False
        if v == "null":
            return None
        return float(v) if "." in v else int(v)
    # string value `\"…\"` with no embedded `\"`
    m = re.search(rf'\\"{k}\\":\\"((?:(?!\\").)*)\\"', haystack)
    if m:
        return m.group(1)
    if re.search(rf'\\"{k}\\":\{{\}}', haystack):
        return {}
    return None


def _jsonld_nodes(sel):
    out = []
    for raw in sel.css("script[type='application/ld+json']::text").getall():
        try:
            v = json.loads(raw)
        except Exception:
            continue
        arr = v if isinstance(v, list) else [v]
        for n in arr:
            if not isinstance(n, dict):
                continue
            graph = n.get("@graph")
            if isinstance(graph, list):
                for s in graph:
                    if isinstance(s, dict):
                        out.append(s)
            else:
                out.append(n)
    return out


def _type_matches(node, wanted):
    t = node.get("@type")
    if isinstance(t, str):
        return t == wanted
    if isinstance(t, list):
        return wanted in t
    return False


def parse_product(html: str, url: str) -> Product:
    sel = Selector(text=html)
    nodes = _jsonld_nodes(sel)
    product = next((n for n in nodes if _type_matches(n, "Product")), {})

    slug = _slug_from_url(url)

    title = (
        product.get("name")
        or _text(sel.css("h1::text").get())
        or sel.css("meta[property='og:title']::attr(content)").get()
        or ""
    )

    offers = product.get("offers")
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    offers = offers or {}
    price = None if offers.get("price") is None else str(offers["price"])
    currency = offers.get("priceCurrency") or sel.css("meta[itemprop='priceCurrency']::attr(content)").get()
    availability = offers.get("availability") if isinstance(offers.get("availability"), str) else None
    sold = bool(availability and re.search(r"OutOfStock|SoldOut", availability, re.I))

    brand = product.get("brand")
    if isinstance(brand, dict):
        brand = brand.get("name")
    condition = product.get("itemCondition")
    color = product.get("color")
    size = product.get("size")
    description = product.get("description") or sel.css("meta[property='og:description']::attr(content)").get()

    seller = _seller_from_url(url) or _text(sel.css("a[href^='/'][class*='username']::text, [data-testid*='username']::text").get())
    seller_url = f"{HOST}/{seller}/" if seller else None

    ld_images = product.get("image") or []
    if isinstance(ld_images, str):
        ld_images = [ld_images]

    raw_images = list(ld_images) + sel.css(
        "img[alt][src*='depop']::attr(src), picture img::attr(src), [class*='gallery'] img::attr(src)"
    ).getall() + sel.css("meta[property='og:image']::attr(content)").getall()
    images = []
    for u in raw_images:
        if not u:
            continue
        if u.startswith("//"):
            u = "https:" + u
        images.append(u)
    images = _uniq(images)

    hashtags = _uniq([
        _text(t) for t in sel.css("a[href*='/search/?q=%23']::text, a[href*='/search/?q=#']::text").getall()
    ])

    return Product(
        id=slug or "",
        url=url,
        title=title or "",
        price=price,
        currency=currency,
        brand=brand if isinstance(brand, str) else None,
        condition=condition if isinstance(condition, str) else None,
        size=size if isinstance(size, str) else None,
        color=color if isinstance(color, str) else None,
        description=description,
        images=images,
        seller=seller,
        sellerUrl=seller_url,
        hashtags=hashtags,
        sold=sold,
    )


def parse_search(html: str) -> List[SearchResult]:
    sel = Selector(text=html)
    out: List[SearchResult] = []
    seen = set()
    # Walk every list-item that contains a product anchor so price / size siblings
    # (rendered outside the <a>) come along with the metadata.
    items = sel.xpath("//li[.//a[starts-with(@href, '/products/')]] | //article[.//a[starts-with(@href, '/products/')]]")
    if not items:
        items = sel.css("a[href^='/products/']")
    for item in items:
        href = item.css("a[href^='/products/']::attr(href)").get() or item.attrib.get("href", "")
        slug = _slug_from_url(href)
        if not slug or slug in seen:
            continue
        seen.add(slug)
        img_src = item.css("img::attr(src)").get() or item.css("img::attr(data-src)").get()
        title = (
            item.css("img::attr(alt)").get()
            or _text(item.css("p[class*='styles__StyledProductCardTitle']::text").get())
            or _text(item.css("a[href^='/products/']::text").get())
            or ""
        )
        price = _text(item.css("p[aria-label='Price']::text, p[data-testid='product__priceAmount']::text, p[class*='Price']::text").get())
        original_price = _text(item.css("p[aria-label='Discounted price']::text, p[aria-label='original price']::text, s::text, del::text").get())
        seller = _seller_from_url(href)
        size = _text(item.css("p[aria-label='Size']::text, [data-testid*='size']::text").get())
        out.append(SearchResult(
            id=slug,
            title=title,
            url=_abs(href) or href,
            image=img_src,
            price=price,
            originalPrice=original_price,
            seller=seller,
            size=size,
        ))
    return out


def parse_shop(html: str, username: str) -> Shop:
    sel = Selector(text=html)
    nxt = _extract_next_data(html) or {}
    page = (nxt.get("props") or {}).get("pageProps") or {}
    profile = page.get("user") or page.get("shop") or {}

    rsc = _extract_rsc_seller(html) or ""
    rsc_first = _rsc_field(rsc, "first_name")
    rsc_last = _rsc_field(rsc, "last_name")
    composed = " ".join(p for p in (rsc_first, rsc_last) if p).strip() or None

    seller_name_dom = _text(sel.css("p[class*='styles_sellerName']::text").get())

    display_name = (
        profile.get("displayName")
        or composed
        or seller_name_dom
        or _text(sel.css("h1::text").get())
        or username
    )

    bio = (
        profile.get("bio")
        or _rsc_field(rsc, "bio")
        or _text(sel.css("p[data-testid='shop__bio']::text, div[class*='styles_shopBio'] p::text").get())
    )
    avatar = profile.get("profileImage") or profile.get("avatar") or sel.css("meta[property='og:image']::attr(content)").get()
    location = (
        profile.get("location")
        or _rsc_field(rsc, "location")
        or _text(sel.css("[data-testid*='location']::text").get())
    )

    followers = _to_int(profile.get("followers"))
    if followers is None:
        followers = _to_int(_text(sel.css("a[href*='/followers/'] span::text, a[href*='/followers/']::text").get()))
    if followers is None:
        followers = _rsc_field(rsc, "followers")
    following = _to_int(profile.get("following"))
    if following is None:
        following = _to_int(_text(sel.css("a[href*='/following/'] span::text, a[href*='/following/']::text").get()))
    if following is None:
        following = _rsc_field(rsc, "following")
    rating = _to_float(profile.get("rating"))
    if rating is None:
        rating = _to_float(_text(sel.css("[data-testid*='rating']::text").get()))
    if rating is None:
        rating = _rsc_field(rsc, "reviews_rating")
    reviews = _to_int(profile.get("reviewsCount"))
    if reviews is None:
        reviews = _to_int(_text(sel.css("a[href*='/reviews']::text").get()))
    if reviews is None:
        reviews = _rsc_field(rsc, "reviews_total")

    listings = [asdict(r) for r in parse_search(html)]

    return Shop(
        username=username,
        url=f"{HOST}/{username}/",
        displayName=display_name,
        bio=bio,
        avatar=avatar,
        location=location,
        followers=followers,
        following=following,
        reviews=reviews,
        rating=rating,
        listings=listings,
    )


async def scrape_product(product_url: str) -> Product:
    html = await _fetch_rendered_html(product_url, ready_selector="h1, script#__NEXT_DATA__", auto_scroll=True)
    return parse_product(html, product_url)


async def scrape_search(query: str, max_pages: int = 1) -> List[SearchResult]:
    results: List[SearchResult] = []
    for page in range(1, max_pages + 1):
        suffix = f"&page={page}" if page > 1 else ""
        url = f"{HOST}/search/?q={query.replace(' ', '+')}{suffix}"
        html = await _fetch_rendered_html(url, ready_selector="a[href^='/products/']", auto_scroll=True)
        results.extend(parse_search(html))
    return results


async def scrape_shop(username: str) -> Shop:
    url = f"{HOST}/{username}/"
    html = await _fetch_rendered_html(url, ready_selector="h1, script#__NEXT_DATA__", auto_scroll=True)
    return parse_shop(html, username)


def to_dict(obj):
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    return obj
