"""Alibaba scraper using the official Scrapeless Python SDK + Playwright over CDP."""

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


@dataclass
class Product:
    id: str
    url: str
    title: str
    price: Optional[str] = None
    priceRange: Optional[str] = None
    moq: Optional[str] = None
    images: List[str] = field(default_factory=list)
    supplier: Optional[str] = None
    supplierUrl: Optional[str] = None
    supplierYears: Optional[str] = None
    location: Optional[str] = None
    rating: Optional[str] = None
    description: Optional[str] = None
    categories: List[str] = field(default_factory=list)


@dataclass
class SearchResult:
    id: str
    title: str
    url: str
    image: Optional[str] = None
    price: Optional[str] = None
    moq: Optional[str] = None
    supplier: Optional[str] = None
    location: Optional[str] = None


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
                        logger.warning("wait_for_selector {!r} failed (continuing): {}", ready_selector, e)
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


def _abs(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http"):
        return url
    return "https://www.alibaba.com" + (url if url.startswith("/") else "/" + url)


def _id_from_url(url: Optional[str]) -> str:
    if not url:
        return ""
    m = re.search(r"product-detail/[^/]+_(\d+)\.html", url)
    if m:
        return m.group(1)
    m2 = re.search(r"_(\d{8,})\.html", url)
    if m2:
        return m2.group(1)
    m3 = re.search(r"/(\d{8,})\.html", url)
    if m3:
        return m3.group(1)
    return ""


def _uniq(seq):
    out, seen = [], set()
    for x in seq:
        if not x or x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def parse_product(html: str, url: str) -> Product:
    sel = Selector(text=html)

    title = (
        _text(sel.css("h1::text").get())
        or _text(" ".join(sel.css("h1 *::text").getall()))
        or _text(sel.css("[class*='product-title']::text, [class*='title-content']::text, [class*='ife-title-display']::text, [data-test='product-title']::text").get())
        or _text(sel.css("meta[property='og:title']::attr(content)").get())
    ) or ""

    raw_images = sel.css(
        "[class*='detail-gallery'] img::attr(src), [class*='detail-gallery'] img::attr(data-src),"
        " [class*='main-image'] img::attr(src), [class*='preview-image'] img::attr(src),"
        " [class*='gallery'] img::attr(src), img[class*='lazyload']::attr(data-src)"
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

    price_nodes = [
        _text(t) for t in sel.css(
            "[class*='price-value']::text, [class*='price-text']::text,"
            " [class*='product-price'] [class*='price']::text,"
            " [class*='ladderPrice'] [class*='price']::text"
        ).getall()
    ]
    price_nodes = [p for p in price_nodes if p]
    price = price_nodes[0] if price_nodes else None
    price_range = " - ".join(price_nodes) if len(price_nodes) > 1 else None

    moq = _text(sel.css("[class*='min-order']::text, [class*='moq']::text, [class*='ladderMinOrder']::text").get())

    supplier = _text(sel.css("a[class*='company-name']::text, a[class*='supplier-name']::text, [class*='company-detail-name']::text").get())
    supplier_url = _abs(sel.css("a[class*='company-name']::attr(href), a[class*='supplier-name']::attr(href)").get())
    supplier_years = _text(sel.css("[class*='supplier-years']::text, [class*='verified-years']::text, [class*='years-label']::text").get())
    location = _text(sel.css("[class*='supplier-location']::text, [class*='location-info']::text, [class*='country-name']::text").get())
    rating = _text(sel.css("[class*='supplier-rating']::text, [class*='star-rating']::text").get())

    description = (
        sel.css("meta[name='description']::attr(content)").get()
        or sel.css("meta[property='og:description']::attr(content)").get()
    )

    categories = _uniq([
        _text(t) for t in sel.css("[class*='breadcrumb'] a::text, [class*='crumb'] a::text, nav[aria-label*='readcrumb'] a::text").getall()
    ])

    return Product(
        id=str(_id_from_url(url) or ""),
        url=url,
        title=title,
        price=price,
        priceRange=price_range,
        moq=moq,
        images=images,
        supplier=supplier,
        supplierUrl=supplier_url,
        supplierYears=supplier_years,
        location=location,
        rating=rating,
        description=description,
        categories=categories,
    )


def parse_search(html: str) -> List[SearchResult]:
    sel = Selector(text=html)
    out: List[SearchResult] = []
    seen = set()
    card_css = [
        "div[class*='organic-list-offer']",
        "div[class*='J-offer-wrapper']",
        "div[class*='fy23-search-card']",
        "div[class*='fy24-search-card']",
        "div[class*='search-card']",
        "div[data-content='product']",
        "div[class*='list-no-v2-outter']",
        "div[data-aplus-auto-clk]",
        "a[class*='card-offer']",
        "a[href*='product-detail']",
    ]
    for css in card_css:
        for card in sel.css(css):
            href = card.attrib.get("href") if getattr(getattr(card, "root", None), "tag", None) == "a" else None
            href = href or card.css("a[href*='product-detail']::attr(href), a[href*='/product/']::attr(href), a[href*='_p']::attr(href)").get() or card.css("a::attr(href)").get() or ""
            if href.startswith("//"):
                href = "https:" + href
            offer_id = _id_from_url(href)
            if not offer_id or offer_id in seen:
                continue
            seen.add(offer_id)
            title = _text(card.css("h2::text, [class*='title']::text, [class*='subject']::text, [class*='product-title']::text").get()) or _text(card.css("a::text").get()) or ""
            image = card.css("img::attr(src)").get() or card.css("img::attr(data-src)").get()
            if image and image.startswith("//"):
                image = "https:" + image
            price = _text(card.css("[class*='price']::text").get())
            moq = _text(card.css("[class*='min-order']::text, [class*='moq']::text, [class*='order-num']::text").get())
            supplier = _text(card.css("[class*='supplier']::text, [class*='company']::text, [class*='seller-name']::text").get())
            location = _text(card.css("[class*='location']::text, [class*='country']::text, [class*='supplier-loc']::text").get())
            out.append(SearchResult(
                id=offer_id,
                title=title,
                url=href,
                image=image,
                price=price,
                moq=moq,
                supplier=supplier,
                location=location,
            ))
    return out


async def scrape_product(product_url: str) -> Product:
    html = await _fetch_rendered_html(product_url, ready_selector="h1", auto_scroll=True)
    return parse_product(html, product_url)


async def scrape_search(query: str, max_pages: int = 1) -> List[SearchResult]:
    results: List[SearchResult] = []
    slug = re.sub(r"\s+", "-", query.strip().lower())
    for page in range(1, max_pages + 1):
        # Try the showroom slug first (less aggressive CAPTCHA than /trade/search),
        # then the canonical /trade/search surface.
        candidates = [
            f"https://www.alibaba.com/showroom/{slug}.html",
            f"https://www.alibaba.com/trade/search?SearchText={query.replace(' ', '+')}&page={page}",
        ]
        added = 0
        for url in candidates:
            try:
                html = await _fetch_rendered_html(url, ready_selector="a[href*='product-detail']", auto_scroll=True)
            except Exception:
                continue
            if "Captcha Interception" in html:
                continue
            parsed = parse_search(html)
            if parsed:
                results.extend(parsed)
                added = len(parsed)
                break
        if not added:
            break
    return results


def to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    return obj
