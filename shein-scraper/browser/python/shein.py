"""SHEIN scraper using the official Scrapeless Python SDK + Playwright over CDP."""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any, List, Optional

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 180
DEFAULT_HOST = "https://us.shein.com"


@dataclass
class Product:
    id: str
    url: str
    title: str
    brand: Optional[str] = None
    price: Optional[str] = None
    originalPrice: Optional[str] = None
    discount: Optional[str] = None
    currency: Optional[str] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None
    images: List[str] = field(default_factory=list)
    color: Optional[str] = None
    sizes: List[str] = field(default_factory=list)
    availability: Optional[str] = None
    description: Optional[str] = None
    categories: List[str] = field(default_factory=list)


@dataclass
class SearchResult:
    id: str
    title: str
    url: str
    image: Optional[str] = None
    price: Optional[str] = None
    originalPrice: Optional[str] = None
    discount: Optional[str] = None
    rating: Optional[float] = None


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


def _text(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    cleaned = re.sub(r"\s+", " ", s).strip()
    return cleaned or None


def _to_float(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    m = re.sub(r"[^0-9.]", "", str(s))
    if not m:
        return None
    try:
        return float(m)
    except ValueError:
        return None


def _to_int(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    m = re.sub(r"[^0-9]", "", str(s))
    if not m:
        return None
    try:
        return int(m)
    except ValueError:
        return None


def _uniq(seq):
    out, seen = [], set()
    for x in seq:
        if not x or x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def _id_from_url(url: Optional[str]) -> str:
    if not url:
        return ""
    m = re.search(r"-p-(\d+)\.html", url)
    if m:
        return m.group(1)
    m2 = re.search(r"/(\d{8,})\.html", url)
    if m2:
        return m2.group(1)
    return ""


def parse_product(html: str, url: str) -> Product:
    sel = Selector(text=html)

    title = (
        _text(sel.css("h1::text").get())
        or _text(sel.css("[class*='product-intro__head-name']::text, [class*='product-name']::text, [data-name='product-title']::text").get())
        or _text(sel.css("meta[property='og:title']::attr(content)").get())
    ) or ""

    # Shein bounces dead PDPs (and most bot-flagged sessions) back to the
    # homepage or serves an interstitial — both produce zero usable PDP fields.
    # Fail loudly so the run script doesn't emit a hollow stub.
    if not title:
        page_title = (sel.css("title::text").get() or "").strip()
        if re.search(r"Women.s.{0,3}Men.s Clothing,?\s*Shop Online Fashion", page_title, re.I):
            hint = "bounced to homepage"
        else:
            hint = "missing product fields"
        raise RuntimeError(f"shein: {hint} (anti-bot block or retired SKU) — {url}")

    price = _text(sel.css("[class*='product-intro__head-mainprice']::text, [class*='from-skc'] [class*='price']::text, [class*='product-price']::text, [class*='sale-price']::text").get())
    original_price = _text(sel.css("[class*='product-intro__head-original-price']::text, del[class*='retail']::text").get())
    discount = _text(sel.css("[class*='product-intro__head-discount']::text, [class*='discount-badge']::text").get())
    currency = sel.css("meta[itemprop='priceCurrency']::attr(content)").get() or sel.css("meta[property='og:price:currency']::attr(content)").get()

    rating = _to_float(_text(sel.css("[class*='ProductReviews_score']::text, [class*='rating-star'] [class*='value']::text, .score-num::text").get()))
    reviews = _to_int(_text(sel.css("[class*='ProductReviews_count']::text, [class*='review-count']::text, .review-num::text").get()))

    raw_images = sel.css(
        "[class*='product-intro__main-img-pic'] img::attr(src), [class*='product-intro__thumbs'] img::attr(src),"
        " [class*='gallery'] img::attr(src), [class*='product-image'] img::attr(src),"
        " [class*='product-intro__main-img-pic'] img::attr(data-src)"
    ).getall()
    raw_images += sel.css("meta[property='og:image']::attr(content)").getall()
    images = []
    for u in raw_images:
        if not u:
            continue
        if u.startswith("//"):
            u = "https:" + u
        images.append(u)
    images = _uniq(images)

    color = _text(sel.css("[class*='current-color-name']::text").get())
    sizes = _uniq([
        _text(t) for t in sel.css("[class*='product-intro__sizes-radio'] [class*='size-list__item']::text, [class*='size-radio'] [class*='item']::text").getall()
    ])

    brand = _text(sel.css("[class*='product-intro__head-brand']::text, a[class*='brand-link']::text").get()) or sel.css("meta[property='og:brand']::attr(content)").get()
    availability = sel.css("meta[itemprop='availability']::attr(content)").get() or _text(sel.css("[class*='out-of-stock']::text, [class*='sold-out']::text").get())
    description = sel.css("meta[name='description']::attr(content)").get() or sel.css("meta[property='og:description']::attr(content)").get()
    categories = _uniq([
        _text(t) for t in sel.css("[class*='breadcrumb'] a::text, [class*='crumb'] a::text, [class*='c-breadcrumb'] a::text").getall()
    ])

    return Product(
        id=str(_id_from_url(url) or ""),
        url=url,
        title=title,
        brand=brand,
        price=price,
        originalPrice=original_price,
        discount=discount,
        currency=currency,
        rating=rating,
        reviews=reviews,
        images=images,
        color=color,
        sizes=sizes,
        availability=availability,
        description=description,
        categories=categories,
    )


def parse_search(html: str) -> List[SearchResult]:
    sel = Selector(text=html)
    out: List[SearchResult] = []
    seen = set()
    cards = [
        "section[class*='product-card']",
        "section[data-locate-key]",
        "div[class*='product-list-item']",
        "div[class*='S-product-card']",
        "div[class*='product-card']",
        "li[class*='product-card']",
        "a[href*='-p-'][href$='.html']",
    ]
    for css in cards:
        for card in sel.css(css):
            href = card.attrib.get("href") if getattr(getattr(card, "root", None), "tag", None) == "a" else None
            href = href or card.css("a[href*='-p-']::attr(href), a[href*='.html']::attr(href)").get() or ""
            if href.startswith("//"):
                href = "https:" + href
            if href.startswith("/"):
                href = DEFAULT_HOST + href
            if not href:
                continue
            item_id = _id_from_url(href)
            if not item_id or item_id in seen:
                continue
            seen.add(item_id)
            title = _text(card.css("[class*='goods-title-link']::text, [class*='product-card__goods-name']::text, [class*='card-name']::text, a::attr(title)").get()) or _text(card.css("a::text").get()) or ""
            image = card.css("img::attr(src)").get() or card.css("img::attr(data-src)").get()
            if image and image.startswith("//"):
                image = "https:" + image
            price = _text(card.css("[class*='product-card__price-sale']::text, [class*='product-card-sale-price']::text, [class*='from-skc']::text, [class*='price']::text").get())
            original_price = _text(card.css("[class*='product-card__price-original']::text, del::text, [class*='retail']::text").get())
            discount = _text(card.css("[class*='product-card__discount']::text, [class*='discount-badge']::text").get())
            rating = _to_float(_text(card.css("[class*='product-card__rate']::text, [class*='rating']::text").get()))
            out.append(SearchResult(
                id=item_id,
                title=title,
                url=href,
                image=image,
                price=price,
                originalPrice=original_price,
                discount=discount,
                rating=rating,
            ))
    return out


async def scrape_product(product_url: str) -> Product:
    html = await _fetch_rendered_html(product_url, ready_selector="h1", auto_scroll=True)
    return parse_product(html, product_url)


async def scrape_search(query: str, max_pages: int = 1, host: str = DEFAULT_HOST) -> List[SearchResult]:
    results: List[SearchResult] = []
    for page in range(1, max_pages + 1):
        slug = query.strip().lower().replace(" ", "-")
        url = f"{host}/pdsearch/{slug}/?page={page}"
        html = await _fetch_rendered_html(url, ready_selector="section[class*='product-card'], div[class*='product-card']", auto_scroll=True)
        results.extend(parse_search(html))
    return results


def to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    return obj
