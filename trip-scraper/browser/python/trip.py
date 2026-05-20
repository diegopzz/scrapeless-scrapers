"""Trip.com scraper using the official Scrapeless Python SDK + Playwright over CDP.

Two surfaces:
- ``scrape_search(city_id, checkin, checkout, max_pages)`` — `div.hotel-card` items
  on the Trip.com city hotel list (`https://www.trip.com/hotels/list?city=<id>`).
- ``scrape_hotel(hotel_id, checkin, checkout)`` — single hotel detail page.
"""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any, List, Optional
from urllib.parse import urlencode

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 240


@dataclass
class SearchResult:
    id: str
    name: str
    url: str
    tags: List[str] = field(default_factory=list)
    score: Optional[str] = None
    reviewWord: Optional[str] = None
    reviewCount: Optional[int] = None
    price: Optional[str] = None
    totalPrice: Optional[str] = None
    location: Optional[str] = None
    image: Optional[str] = None


@dataclass
class Hotel:
    id: str
    url: str
    name: str
    description: str
    amenities: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    address: Optional[str] = None
    score: Optional[str] = None
    reviewCount: Optional[int] = None
    price: Optional[str] = None


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
    scroll: bool = True,
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
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                if ready_selector:
                    try:
                        await page.wait_for_selector(ready_selector, timeout=25000)
                    except Exception as e:
                        logger.warning("wait_for_selector {!r} failed (continuing): {}", ready_selector, e)
                if scroll:
                    try:
                        await page.evaluate(
                            "() => new Promise(r => { let y = 0; const i = setInterval(() => { window.scrollBy(0, 700); y += 700; if (y >= document.body.scrollHeight) { clearInterval(i); r(); } }, 250); })"
                        )
                    except Exception:
                        pass
                    await page.wait_for_timeout(2000)
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


def _parse_int(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    m = re.search(r"([\d,]+)", text)
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _detail_url(hotel_id: str, checkin: str = "", checkout: str = "") -> str:
    params: dict[str, str] = {"hotelId": str(hotel_id)}
    if checkin:
        params["checkIn"] = checkin
    if checkout:
        params["checkOut"] = checkout
    return f"https://www.trip.com/hotels/detail/?{urlencode(params)}"


# ---------------- search ----------------


def parse_search(html: str, checkin: str = "", checkout: str = "") -> List[SearchResult]:
    sel = Selector(text=html)
    out: List[SearchResult] = []
    # Trip ships two layouts: the older `.hotel-card` and the newer
    # `.compressmeta-hotel-wrap-v8` ("version B"). Accept both.
    cards = sel.css("[id][class*='hotel-card'], [id][class*='compressmeta-hotel-wrap']")
    for card in cards:
        hid = card.attrib.get("id", "")
        if not hid.isdigit():
            continue
        name = (
            card.css(".list-card-title .name::text").get()
            or card.css(".list-card-title::text").get()
            or card.css(".hotel-title *::text").get()
            or card.css(".hotel-title::text").get()
            or card.css(".name::text").get()
            or ""
        ).strip()
        # Score: a `.real` block whose text is a plain number.
        score: Optional[str] = None
        for t in card.css(".real::text").getall():
            t = t.strip()
            if re.fullmatch(r"\d+(\.\d+)?", t):
                score = t
                break
        if not score:
            score = (card.css(".score::text").get() or "").strip() or None
        word_block = " ".join(card.css(".describe *::text, .review-rt *::text, .outstanding *::text").getall())
        word_m = re.search(r"\b(Outstanding|Excellent|Very Good|Good|Pleasant|Fair|Wonderful|Fabulous|Exceptional)\b", word_block, re.I)
        review_word = word_m.group(1) if word_m else None
        review_block = " ".join(card.css(".count *::text, .review-rt *::text").getall())
        review_count_m = re.search(r"([\d,]+)\s+reviews?", review_block, re.I)
        review_count = _parse_int(review_count_m.group(1)) if review_count_m else None
        price = (
            (card.css(".real.labelColor::text").get() or "").strip()
            or (card.css(".price-line *::text").get() or "").strip()
            or None
        )
        total = "".join(card.css(".price-explain *::text").getall()).strip() or None
        tags: List[str] = []
        for t in card.css(".member-reward-tag *::text, .encourage-tag *::text, .highlight-tag *::text, .hotel-tag *::text").getall():
            t = t.strip()
            if t and t not in tags:
                tags.append(t)
        location_raw = " ".join(card.css(".transport *::text, [class*=location] *::text, [class*=landmark] *::text").getall()).strip()
        location = re.sub(r"\s+", " ", location_raw) or None
        image = card.css(".multi-images img::attr(src), img.m-lazyImg__img::attr(src)").get()
        out.append(
            SearchResult(
                id=hid,
                name=name,
                url=_detail_url(hid, checkin, checkout),
                score=score,
                reviewWord=review_word,
                reviewCount=review_count,
                price=price,
                totalPrice=total,
                tags=tags,
                location=location,
                image=image,
            )
        )
    return out


async def scrape_search(
    city_id: str = "53",
    checkin: str = "",
    checkout: str = "",
    max_pages: int = 1,
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
) -> List[SearchResult]:
    out: List[SearchResult] = []
    for page in range(1, max_pages + 1):
        params: dict[str, str] = {"city": str(city_id)}
        if checkin:
            params["checkin"] = checkin
        if checkout:
            params["checkout"] = checkout
        if page > 1:
            params["p"] = str(page)
        url = f"https://www.trip.com/hotels/list?{urlencode(params)}"
        html = await _fetch_rendered_html(
            url,
            "[id][class*='hotel-card'], [id][class*='compressmeta-hotel-wrap']",
            proxy_country=proxy_country,
        )
        items = parse_search(html, checkin, checkout)
        if not items and page > 1:
            break
        out.extend(items)
    return out


# ---------------- hotel ----------------


def parse_hotel(html: str, hotel_id: str, url: str) -> Hotel:
    sel = Selector(text=html)
    name = (
        sel.css("h1.headInfo .name::text").get()
        or sel.css("h1[class*=hotelName]::text").get()
        or sel.css("h1::text").get()
        or sel.css(".hotel-name::text").get()
        or ""
    ).strip()
    address = (sel.css("[class*=address] *::text").get() or "").strip() or None
    score = (sel.css(".score::text").get() or sel.css("[class*=real]::text").get() or "").strip() or None
    review_block = "".join(sel.css("[class*=comment-num]::text, [class*=reviewCount]::text").getall())
    review_count = _parse_int(review_block)
    description = "".join(sel.css("[class*=introduction] *::text").getall()).strip() \
        or "".join(sel.css("[class*=hotel-description] *::text").getall()).strip()
    amenities = [t.strip() for t in sel.css(
        "[class*=facilities] li *::text, [class*=amenities] li *::text, [class*=hotelFacility] li *::text"
    ).getall() if t.strip()]
    images: List[str] = []
    for src in sel.css("img::attr(src), img::attr(data-src)").getall():
        if not src:
            continue
        if re.search(r"tripcdn\.com|ak-d\.tripcdn", src) and re.search(r"hotel|images", src, re.I):
            if src not in images:
                images.append(src)
    price = (sel.css("[class*=price] [class*=real]::text").get() or "").strip() or None
    return Hotel(
        id=str(hotel_id),
        url=url,
        name=name,
        address=address,
        score=score,
        reviewCount=review_count,
        description=description,
        amenities=amenities,
        images=images[:30],
        price=price,
    )


async def scrape_hotel(
    hotel_id: str,
    checkin: str = "",
    checkout: str = "",
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
) -> Hotel:
    url = _detail_url(hotel_id, checkin, checkout)
    html = await _fetch_rendered_html(
        url,
        ready_selector="h1, [class*=headInfo], [class*=hotelName]",
        proxy_country=proxy_country,
    )
    return parse_hotel(html, hotel_id, url)


def to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
