"""Lazada scraper using the official Scrapeless Python SDK + Playwright over CDP.

Lazada hydrates PDP fields client-side from an XHR to
``/h5/mtop.global.detail.web.getdetailinfo/1.0/``. The response wraps a
stringified ``data.module`` JSON that holds ``product``, ``skuInfos[id].price``,
``seller``, ``review``, ``Breadcrumb`` and ``skuGalleries``. We capture that
XHR live; the SSR HTML is too sparse to rely on.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from parsel import Selector
from playwright.async_api import Response, async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "SG"
DEFAULT_SESSION_TTL = 240
DEFAULT_HOST = "https://www.lazada.sg"


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
    seller: Optional[str] = None
    sellerUrl: Optional[str] = None
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
    reviews: Optional[int] = None
    location: Optional[str] = None


def _client() -> Scrapeless:
    if not os.environ.get("SCRAPELESS_API_KEY") and not os.environ.get("SCRAPELESS_KEY"):
        raise RuntimeError(
            "SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com"
        )
    if not os.environ.get("SCRAPELESS_API_KEY") and os.environ.get("SCRAPELESS_KEY"):
        os.environ["SCRAPELESS_API_KEY"] = os.environ["SCRAPELESS_KEY"]
    return Scrapeless()


def _text(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    cleaned = re.sub(r"\s+", " ", s).strip()
    return cleaned or None


def _to_float(s) -> Optional[float]:
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


def _to_int(s) -> Optional[int]:
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return int(s)
    m = re.sub(r"[^0-9]", "", str(s))
    if not m:
        return None
    try:
        return int(m)
    except ValueError:
        return None


def _abs(url: Optional[str], host: str = DEFAULT_HOST) -> Optional[str]:
    if not url:
        return None
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http"):
        return url
    return host + (url if url.startswith("/") else "/" + url)


def _id_from_url(url: Optional[str]) -> str:
    if not url:
        return ""
    m = re.search(r"-i(\d+)(?:-s\d+)?\.html", url)
    if m:
        return m.group(1)
    m2 = re.search(r"/(\d{8,})\.html", url)
    if m2:
        return m2.group(1)
    return ""


def _uniq(seq):
    out, seen = [], set()
    for x in seq:
        if not x or x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def parse_product_from_mtop(mod: Dict[str, Any], url: str) -> Product:
    product = mod.get("product") or {}
    sku_infos = mod.get("skuInfos") or {}
    sku_galleries = mod.get("skuGalleries") or {}
    seller = mod.get("seller") or {}
    review = mod.get("review") or {}
    breadcrumb = mod.get("Breadcrumb") or mod.get("breadcrumb") or []
    global_config = mod.get("globalConfig") or {}

    ids = list(sku_infos.keys())
    preferred_id = (mod.get("primaryKey") or {}).get("skuId")
    preferred = (
        sku_infos.get(preferred_id)
        or (sku_infos.get(ids[-1]) if ids else None)
        or sku_infos.get("0")
        or {}
    )
    price_obj = preferred.get("price") or {}
    sale = price_obj.get("salePrice") or {}
    orig = price_obj.get("originalPrice") or {}

    images: List[str] = []
    gallery_key = preferred_id or (ids[-1] if ids else "0")
    for g in sku_galleries.get(gallery_key) or []:
        u = (g or {}).get("src") or (g or {}).get("poster")
        if u:
            images.append("https:" + u if u.startswith("//") else u)
    for u in product.get("imageUrls") or []:
        if u:
            images.append(u)
    images = _uniq(images)

    brand = None
    pb = product.get("brand")
    if isinstance(pb, dict):
        brand = pb.get("name")
    elif isinstance(pb, str):
        brand = pb

    categories = [b.get("title") for b in (breadcrumb or []) if isinstance(b, dict) and b.get("title")]

    rating_val = (product.get("rating") or {}).get("score") if isinstance(product.get("rating"), dict) else None
    if rating_val is None:
        rating_val = review.get("averageRating")
    reviews_val = (product.get("rating") or {}).get("total") if isinstance(product.get("rating"), dict) else None
    if reviews_val is None:
        reviews_val = review.get("contentedNum")

    sale_value = sale.get("value") if isinstance(sale, dict) else None
    sale_sign = sale.get("sign") if isinstance(sale, dict) else None
    price_str = sale.get("text") if isinstance(sale, dict) else None
    if not price_str and isinstance(sale_value, (int, float)):
        price_str = f"{sale_sign or ''}{sale_value}"

    orig_value = orig.get("value") if isinstance(orig, dict) else None
    orig_str = orig.get("text") if isinstance(orig, dict) else None
    if not orig_str and isinstance(orig_value, (int, float)):
        orig_str = str(orig_value)

    return Product(
        id=str(_id_from_url(url) or product.get("itemId") or (mod.get("primaryKey") or {}).get("itemId") or ""),
        url=url,
        title=product.get("title") or "",
        brand=brand,
        price=price_str,
        originalPrice=orig_str,
        discount=price_obj.get("discount") if isinstance(price_obj, dict) else None,
        currency=global_config.get("currencyCode") if isinstance(global_config, dict) else None,
        rating=_to_float(rating_val),
        reviews=_to_int(reviews_val),
        images=images,
        seller=seller.get("name") if isinstance(seller, dict) else None,
        sellerUrl=_abs(seller.get("url")) if isinstance(seller, dict) else None,
        availability=((preferred.get("operation") or {}).get("text")) if isinstance(preferred.get("operation"), dict) else None,
        description=product.get("desc"),
        categories=categories,
    )


def parse_search(html: str) -> List[SearchResult]:
    sel = Selector(text=html)
    out: List[SearchResult] = []
    seen: set[str] = set()
    cards = [
        "div[data-qa-locator='product-item']",
        "div[class*='card--']",
        "div[class*='Bm3ON']",
        "div[class*='product-card']",
    ]
    for css in cards:
        for card in sel.css(css):
            href = card.css("a[href*='.html']::attr(href)").get() or ""
            if href.startswith("//"):
                href = "https:" + href
            if not href:
                continue
            item_id = _id_from_url(href)
            if not item_id or item_id in seen:
                continue
            seen.add(item_id)
            title = _text(card.css("[class*='RfADt']::text, [class*='title']::text, [class*='subject']::text, [class*='card-text-title']::text").get()) or card.css("a::attr(title)").get() or _text(card.css("a::text").get()) or ""
            image = card.css("img::attr(src)").get() or card.css("img::attr(data-src)").get()
            if image and image.startswith("//"):
                image = "https:" + image
            price = _text(card.css("[class*='price']::text, [class*='ooOxS']::text").get())
            original_price = _text(card.css("[class*='WNoq3']::text, [class*='origPrice']::text").get())
            discount = _text(card.css("[class*='IcOsH']::text, [class*='discount']::text").get())
            rating = _to_float(_text(card.css("[class*='qzqFw']::text, [class*='rating']::text").get()))
            if rating is not None and rating > 5:
                rating = rating / 10
            if rating is not None and rating > 5:
                rating = None
            reviews = _to_int(_text(card.css("[class*='_6uN7R']::text, span[class*='review']::text").get()))
            location = _text(card.css("[class*='oa6ri']::text, [class*='location']::text").get())
            out.append(SearchResult(
                id=item_id,
                title=title,
                url=href,
                image=image,
                price=price,
                originalPrice=original_price,
                discount=discount,
                rating=rating,
                reviews=reviews,
                location=location,
            ))
    return out


async def scrape_product(product_url: str) -> Product:
    client = _client()
    session = client.browser.create(ICreateBrowser(proxy_country=DEFAULT_PROXY_COUNTRY, session_ttl=DEFAULT_SESSION_TTL))
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
        try:
            page = await browser.new_page()
            holder: Dict[str, Any] = {"body": None}

            async def _on_response(resp: Response) -> None:
                try:
                    if holder["body"]:
                        return
                    u = resp.url.lower()
                    if "mtop.global.detail.web.getdetailinfo" not in u:
                        return
                    holder["body"] = await resp.text()
                except Exception:
                    pass

            page.on("response", lambda r: asyncio.create_task(_on_response(r)))
            await page.goto(product_url, wait_until="domcontentloaded", timeout=60000)
            for _ in range(60):
                if holder["body"]:
                    break
                await page.wait_for_timeout(500)
            if not holder["body"]:
                raise RuntimeError(
                    f"lazada: detail XHR (mtop.global.detail.web.getDetailInfo) never fired for {product_url}"
                )
            env = json.loads(holder["body"])
            raw_mod = (env or {}).get("data", {}).get("module")
            mod = json.loads(raw_mod) if isinstance(raw_mod, str) else (raw_mod or {})
            if not mod.get("product"):
                raise RuntimeError("lazada: detail XHR payload missing product block")
            return parse_product_from_mtop(mod, product_url)
        finally:
            try:
                await browser.close()
            except Exception:
                pass


async def scrape_search(query: str, max_pages: int = 1, host: str = DEFAULT_HOST) -> List[SearchResult]:
    client = _client()
    session = client.browser.create(ICreateBrowser(proxy_country=DEFAULT_PROXY_COUNTRY, session_ttl=DEFAULT_SESSION_TTL))
    results: List[SearchResult] = []
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
        try:
            page = await browser.new_page()
            for p in range(1, max_pages + 1):
                url = f"{host}/catalog/?q={query.replace(' ', '+')}&page={p}"
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                try:
                    await page.wait_for_selector("div[data-qa-locator='product-item'], div[class*='card']", timeout=20000)
                except Exception:
                    pass
                try:
                    await page.evaluate(
                        "() => new Promise(r => { let y = 0; const i = setInterval(() => { window.scrollBy(0, 600); y += 600; if (y >= document.body.scrollHeight) { clearInterval(i); r(); } }, 120); })"
                    )
                    await page.wait_for_timeout(1500)
                except Exception:
                    pass
                html = await page.content()
                results.extend(parse_search(html))
        finally:
            try:
                await browser.close()
            except Exception:
                pass
    return results


def to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    return obj
