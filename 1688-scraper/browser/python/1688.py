"""1688 scraper using the official Scrapeless Python SDK + Playwright over CDP.

Under the hood:
- `client.browser.create()` mints a cloud session on Scrapeless's Scraping Browser,
  returning a CDP WebSocket endpoint (`browser_ws_endpoint`).
- Playwright connects to that WebSocket, drives the page, returns rendered HTML.
- Parsel parses the HTML into dataclasses matching DATA_MODEL.md.
"""

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

DEFAULT_PROXY_COUNTRY = "CN"
DEFAULT_SESSION_TTL = 180


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


@dataclass
class Product:
    id: str
    url: str
    title: str
    price: Optional[str] = None
    priceRange: Optional[str] = None
    moq: Optional[str] = None
    images: List[str] = field(default_factory=list)
    seller: Optional[str] = None
    sellerUrl: Optional[str] = None
    location: Optional[str] = None
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
    seller: Optional[str] = None
    location: Optional[str] = None


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    return "https://www.1688.com" + (url if url.startswith("/") else "/" + url)


def _id_from_url(url: Optional[str]) -> str:
    if not url:
        return ""
    m = re.search(r"offer/(\d+)\.html", url)
    if m:
        return m.group(1)
    m2 = re.search(r"(\d{8,})", url)
    return m2.group(1) if m2 else ""


def _uniq(seq):
    out = []
    seen = set()
    for item in seq:
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def _detect_captcha(html: str) -> bool:
    t = (html or "").lower()
    return (
        "unusual traffic" in t
        or "captcha interception" in t
        or "captcha=true" in t
        or ("nocaptcha" in t and "punish" in t)
    )


def parse_product(html: str, product_id: str, url: str) -> Product:
    if _detect_captcha(html):
        raise RuntimeError(f"1688: captcha interstitial served (Alibaba bot wall) — {url}")
    sel = Selector(text=html)

    raw_images = sel.css(
        "div[class*='detail-gallery'] img::attr(src), div[class*='detail-gallery'] img::attr(data-src),"
        " ul[class*='thumbnail'] img::attr(src), ul[class*='thumbnail'] img::attr(data-src),"
        " .img-list img::attr(src), img[class*='gallery']::attr(src)"
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

    title = (
        _text(sel.css("h1::text").get())
        or _text(sel.css("[class*='d-title']::text, [class*='title-text']::text, [class*='offer-title']::text").get())
        or _text(sel.css("meta[property='og:title']::attr(content)").get())
    ) or ""

    price_nodes = [
        _text(t)
        for t in sel.css("[class*='price'] [class*='value']::text, [class*='price-num']::text, .mod-detail-price .value::text, .price .value::text").getall()
    ]
    price_nodes = [p for p in price_nodes if p]
    price = price_nodes[0] if price_nodes else None
    if len(price_nodes) > 1:
        price_range = " - ".join(price_nodes)
    else:
        price_range = _text(sel.css("[class*='price-range']::text, .price-range::text").get())

    moq = None
    for t in sel.css("[class*='obj-leading']::text, [class*='order-tip']::text, [class*='step-detail']::text, [class*='min-order']::text, [class*='moq']::text").getall():
        cleaned = _text(t)
        if cleaned and ("起订" in cleaned or "MOQ" in cleaned.upper() or cleaned.endswith("件")):
            moq = cleaned
            break
    if not moq:
        body_text = " ".join(sel.css("body *::text").getall())
        m = re.search(r"起订量[^0-9]{0,4}(\d[\d,]*\s*[件个套盒\w]*)", body_text)
        if m:
            moq = m.group(1).strip()

    seller = (
        _text(sel.css("a[class*='company-name']::text, a[class*='supplier-name']::text, a[class*='shop-name']::text").get())
        or _text(sel.css("[class*='company-name']::text, [class*='supplier']::text").get())
    )
    seller_url = _abs(sel.css("a[class*='company-name']::attr(href), a[class*='supplier-name']::attr(href), a[class*='shop-name']::attr(href)").get())
    location = _text(sel.css("[class*='location']::text, [class*='address-info']::text, [class*='province']::text").get())

    categories = _uniq(
        [_text(t) for t in sel.css("[class*='breadcrumb'] a::text, [class*='crumb'] a::text, .breadcrumb a::text").getall()]
    )

    description = (
        sel.css("meta[name='description']::attr(content)").get()
        or sel.css("meta[property='og:description']::attr(content)").get()
    )

    return Product(
        id=str(product_id),
        url=url,
        title=title or "",
        price=price,
        priceRange=price_range,
        moq=moq,
        images=images,
        seller=seller,
        sellerUrl=seller_url,
        location=location,
        description=description,
        categories=categories,
    )


def parse_search(html: str) -> List[SearchResult]:
    if _detect_captcha(html):
        raise RuntimeError("1688: captcha interstitial served on search (Alibaba bot wall)")
    sel = Selector(text=html)
    out: List[SearchResult] = []
    seen = set()
    card_selectors = [
        "div[class*='offer-card']",
        "div[class*='space-offer-card']",
        "li[class*='offer-list']",
        "div[data-aplus-auto-clk]",
        "div[class*='SearchOfferCard']",
        "div.organic-list .organic-item",
        "div.offer",
    ]
    for css in card_selectors:
        for card in sel.css(css):
            link = card.css("a[href*='offer/']::attr(href), a[href*='detail.1688.com']::attr(href), a[href*='.alibaba.com']::attr(href)").get() or card.css("a::attr(href)").get() or ""
            if link.startswith("//"):
                link = "https:" + link
            offer_id = _id_from_url(link)
            if not offer_id or offer_id in seen:
                continue
            seen.add(offer_id)
            title = _text(card.css("[class*='title']::text, [class*='offer-title']::text, [class*='subject']::text").get()) or _text(card.css("a::text").get()) or ""
            image = card.css("img::attr(src)").get() or card.css("img::attr(data-src)").get()
            if image and image.startswith("//"):
                image = "https:" + image
            price = _text(card.css("[class*='price']::text, [class*='Price']::text").get())
            moq = _text(card.css("[class*='moq']::text, [class*='order-tip']::text, [class*='step-tip']::text").get())
            seller = _text(card.css("[class*='company']::text, [class*='supplier']::text").get())
            location = _text(card.css("[class*='location']::text, [class*='address']::text").get())
            out.append(SearchResult(
                id=offer_id,
                title=title,
                url=link,
                image=image,
                price=price,
                moq=moq,
                seller=seller,
                location=location,
            ))
    return out


# ---------------------------------------------------------------------------
# Scrape functions
# ---------------------------------------------------------------------------


async def scrape_product(product_id: str) -> Product:
    url = f"https://detail.1688.com/offer/{product_id}.html"
    html = await _fetch_rendered_html(url, ready_selector="body", auto_scroll=True)
    return parse_product(html, product_id, url)


async def scrape_search(query: str, max_pages: int = 1) -> List[SearchResult]:
    results: List[SearchResult] = []
    for page in range(1, max_pages + 1):
        url = (
            "https://s.1688.com/selloffer/offer_search.htm"
            f"?keywords={query.replace(' ', '+')}&beginPage={page}"
        )
        html = await _fetch_rendered_html(url, ready_selector="body", auto_scroll=True)
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
