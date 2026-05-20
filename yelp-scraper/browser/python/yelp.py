"""Yelp scraper using the official Scrapeless Python SDK + Playwright over CDP.
the function names and emitted field shapes match verbatim, so downstream
code can Three public entry points (mirror the upstream reference):
- `scrape_pages(urls)` -> list of business profile dicts
- `scrape_reviews(url, max_reviews=None)` -> list of reviews from Yelp's GraphQL feed
- `scrape_search(keyword, location, max_pages=None)` -> list of search result props
"""

from __future__ import annotations

import asyncio
import base64
import json
import math
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import jmespath
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

def _looks_blocked(html: str) -> bool:
    if not html or len(html) < 5000:
        return True
    if "captcha-delivery.com" in html or "DataDome CAPTCHA" in html:
        return True
    if "px-captcha" in html or "Pardon Our Interruption" in html:
        return True
    return False


async def _fetch_rendered_html(
    url: str,
    ready_selector: Optional[str] = None,
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
    retries: int = 2,
    warmup: bool = True,
) -> str:
    """Mint a cloud browser session, navigate, wait for a stable marker, return HTML."""
    last_error: Optional[Exception] = None
    for attempt in range(retries + 1):
        client = _client()
        session = client.browser.create(
            ICreateBrowser(proxy_country=proxy_country, session_ttl=DEFAULT_SESSION_TTL)
        )
        ws = session.browser_ws_endpoint
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(ws)
            try:
                page = await browser.new_page()
                if warmup:
                    # Hit yelp.com first so the session picks up DataDome cookies
                    # and second-hop traffic clears anti-bot more reliably.
                    try:
                        await page.goto("https://www.yelp.com/", wait_until="domcontentloaded", timeout=30000)
                        await asyncio.sleep(1.5)
                    except Exception:
                        pass
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                if ready_selector:
                    try:
                        await page.wait_for_selector(ready_selector, timeout=15000)
                    except Exception as e:
                        logger.warning("wait_for_selector failed (continuing): {}", e)
                html = await page.content()
                if html and not _looks_blocked(html):
                    return html
                last_error = RuntimeError("anti-bot block" if _looks_blocked(html) else "empty HTML")
            except Exception as e:  # noqa: BLE001
                last_error = e
                logger.warning("attempt {} failed: {}", attempt + 1, e)
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass
    raise RuntimeError(f"giving up after {retries + 1} attempts: {last_error}")

async def _post_json(
    url: str,
    payload: str,
    headers: Dict[str, str],
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
) -> str:
    """POST a JSON body via the cloud browser (so we inherit anti-bot session state)."""
    client = _client()
    session = client.browser.create(
        ICreateBrowser(proxy_country=proxy_country, session_ttl=DEFAULT_SESSION_TTL)
    )
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
        try:
            ctx = await browser.new_context()
            # Warm session cookies on www.yelp.com so the GQL endpoint accepts us.
            page = await ctx.new_page()
            referer = headers.get("referer", "https://www.yelp.com/")
            try:
                await page.goto(referer, wait_until="domcontentloaded", timeout=30000)
            except Exception:
                pass
            response = await ctx.request.post(url, data=payload, headers=headers)
            return await response.text()
        finally:
            try:
                await browser.close()
            except Exception:
                pass

# ---------------------------------------------------------------------------
# Parsers — mirror the upstream reference's function names verbatim
# ---------------------------------------------------------------------------

_BUSINESS_LD_TYPES = {
    "Restaurant", "LocalBusiness", "FoodEstablishment", "Bar",
    "CafeOrCoffeeShop", "Hotel", "Store", "Organization",
}


def _read_business_jsonld(sel: Selector) -> Optional[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for raw in sel.xpath('//script[@type="application/ld+json"]/text()').getall():
        try:
            data = json.loads(raw)
        except Exception:
            continue
        if isinstance(data, list):
            candidates.extend([d for d in data if isinstance(d, dict)])
        elif isinstance(data, dict):
            candidates.append(data)
    for node in candidates:
        t = node.get("@type")
        if isinstance(t, str) and t in _BUSINESS_LD_TYPES:
            return node
        if isinstance(t, list) and any(x in _BUSINESS_LD_TYPES for x in t):
            return node
    return None


def _address_to_string(addr: Any) -> str:
    if isinstance(addr, str):
        return addr
    if not isinstance(addr, dict):
        return ""
    parts = [
        addr.get("streetAddress"),
        addr.get("addressLocality"),
        addr.get("addressRegion"),
        addr.get("postalCode"),
        addr.get("addressCountry"),
    ]
    return ", ".join(str(p).strip() for p in parts if isinstance(p, str) and p.strip())


def _jsonld_open_hours(node: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    spec = node.get("openingHoursSpecification")
    if not isinstance(spec, list):
        return out
    for entry in spec:
        if not isinstance(entry, dict):
            continue
        days = entry.get("dayOfWeek")
        if not isinstance(days, list):
            days = [days]
        opens = entry.get("opens", "")
        closes = entry.get("closes", "")
        rng = f"{opens}-{closes}" if opens and closes else (opens or closes or "")
        for day in days:
            if not isinstance(day, str):
                continue
            key = day.rsplit("/", 1)[-1][:3].lower()
            out[key] = rng
    return out


def parse_page(html: str) -> Dict[str, Any]:
    """Parse business data from a yelp business profile HTML."""
    sel = Selector(text=html)
    xp = lambda q: (sel.xpath(q).get(default="") or "").strip()
    open_hours: Dict[str, str] = {}
    for day in sel.xpath('//th/p[contains(@class,"day-of-the-week")]'):
        name = (day.xpath("text()").get() or "").strip()
        value = (day.xpath("../following-sibling::td//p/text()").get() or "").strip()
        if name:
            open_hours[name.lower()] = value
    out = dict(
        name=xp("//h1/text()"),
        website=xp('//p[contains(text(),"Business website")]/following-sibling::p/a/text()'),
        phone=xp('//p[contains(text(),"Phone number")]/following-sibling::p/text()'),
        address=xp('//a[contains(text(),"Get Directions")]/../following-sibling::p/text()'),
        logo=xp('//img[contains(@class,"businessLogo")]/@src'),
        claim_status="".join(sel.xpath('//span[span[contains(@class,"claim")]]/text()').getall()).strip().lower(),
        open_hours=open_hours,
    )

    # JSON-LD fallback — DOM selectors are fragile across Yelp's A/B layouts.
    business = _read_business_jsonld(sel)
    if business:
        if not out["name"]:
            out["name"] = str(business.get("name", "")).replace("&apos;", "'")
        if not out["phone"]:
            out["phone"] = str(business.get("telephone", ""))
        if not out["address"]:
            out["address"] = _address_to_string(business.get("address"))
        if not out["website"]:
            same = business.get("sameAs")
            if isinstance(same, list) and same:
                out["website"] = same[0]
            elif isinstance(business.get("url"), str) and "yelp.com" not in business["url"]:
                out["website"] = business["url"]
        if not out["logo"]:
            img = business.get("image")
            if isinstance(img, str):
                out["logo"] = img
            elif isinstance(img, dict) and isinstance(img.get("url"), str):
                out["logo"] = img["url"]
        if not out["open_hours"]:
            oh = _jsonld_open_hours(business)
            if oh:
                out["open_hours"] = oh
    return out

def parse_business_id(html: str) -> Optional[str]:
    """Pluck the encoded business id from the page meta tag."""
    sel = Selector(text=html)
    return sel.css('meta[name="yelp-biz-id"]::attr(content)').get()

def parse_review_data(response_text: str) -> Dict[str, Any]:
    """Parse the GraphQL batch response from `/gql/batch`."""
    data = json.loads(response_text)
    reviews = data[0]["data"]["business"]["reviews"]["edges"]
    parsed_reviews = []
    for review in reviews:
        result = jmespath.search(
            """{
            encid: encid,
            text: text.{full: full, language: language},
            rating: rating,
            feedback: feedback.{coolCount: coolCount, funnyCount: funnyCount, usefulCount: usefulCount},
            author: author.{encid: encid, displayName: displayName, displayLocation: displayLocation, reviewCount: reviewCount, friendCount: friendCount, businessPhotoCount: businessPhotoCount},
            business: business.{encid: encid, alias: alias, name: name},
            createdAt: createdAt.utcDateTime,
            businessPhotos: businessPhotos[].{encid: encid, photoUrl: photoUrl.url, caption: caption, helpfulCount: helpfulCount},
            businessVideos: businessVideos,
            availableReactions: availableReactionsContainer.availableReactions[].{displayText: displayText, reactionType: reactionType, count: count}
            }""",
            review["node"],
        )
        parsed_reviews.append(result)
    total_reviews = data[0]["data"]["business"]["reviewCount"]
    return {"reviews": parsed_reviews, "total_reviews": total_reviews}

def parse_search(html: str) -> Dict[str, Any]:
    """Parse listing data from the inline `react-root-props` JSON."""
    search_data: List[Dict[str, Any]] = []
    total_results = 0
    sel = Selector(text=html)
    script = sel.xpath("//script[@data-id='react-root-props']/text()").get()
    if not script:
        return {"search_data": search_data, "total_results": total_results}
    data = json.loads(script.split("react_root_props = ")[-1].rsplit(";", 1)[0])
    search_page_props = (
        data.get("legacyProps", {}).get("searchAppProps", {}).get("searchPageProps", {})
    )
    if search_page_props:
        total_results = search_page_props.get("paginationInfo", {}).get("totalResults", 0)
    main_content = search_page_props.get("mainContentComponentsListProps", [])
    for item in main_content:
        if item.get("bizId") and item.get("searchResultBusiness") is not None:
            search_data.append(item)
    return {"search_data": search_data, "total_results": total_results}

# ---------------------------------------------------------------------------
# Scrape functions — mirror the upstream reference's exports verbatim
# ---------------------------------------------------------------------------

async def scrape_pages(urls: List[str]) -> List[Dict[str, Any]]:
    """Scrape Yelp business profile pages."""
    result: List[Dict[str, Any]] = []
    for url in urls:
        html = await _fetch_rendered_html(url, ready_selector="h1")
        result.append(parse_page(html))
    logger.success(f"scraped {len(result)} business pages")
    return result

async def _request_reviews_api(url: str, start_index: int, business_id: str) -> str:
    """POST Yelp's GetBusinessReviewFeed GQL batch endpoint."""
    pagination_data = json.dumps({"version": 1, "type": "offset", "offset": start_index})
    after = base64.b64encode(pagination_data.encode("utf-8")).decode("utf-8")

    payload = json.dumps(
        [
            {
                "operationName": "GetBusinessReviewFeed",
                "variables": {
                    "encBizId": business_id,
                    "reviewsPerPage": 10,
                    "selectedReviewEncId": "",
                    "hasSelectedReview": False,
                    "sortBy": "DATE_DESC",
                    "languageCode": "en",
                    "ratings": [5, 4, 3, 2, 1],
                    "isSearching": False,
                    "after": after,
                    "isTranslating": False,
                    "translateLanguageCode": "en",
                    "reactionsSourceFlow": "businessPageReviewSection",
                    "minConfidenceLevel": "HIGH_CONFIDENCE",
                    "highlightType": "",
                    "highlightIdentifier": "",
                    "isHighlighting": False,
                },
                "extensions": {
                    "operationType": "query",
                    "documentId": "ef51f33d1b0eccc958dddbf6cde15739c48b34637a00ebe316441031d4bf7681",
                },
            }
        ]
    )
    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "no-cache",
        "content-type": "application/json",
        "origin": "https://www.yelp.com",
        "referer": url,
        "x-apollo-operation-name": "GetBusinessReviewFeed",
    }
    return await _post_json("https://www.yelp.com/gql/batch", payload, headers)

async def scrape_reviews(url: str, max_reviews: Optional[int] = None) -> List[Dict[str, Any]]:
    """Scrape reviews for a Yelp business via the GraphQL feed."""
    logger.info("scraping the business id from the business page")
    business_html = await _fetch_rendered_html(url, ready_selector='meta[name="yelp-biz-id"]')
    business_id = parse_business_id(business_html)
    if not business_id:
        logger.error("could not find business id on {}", url)
        return []

    logger.info("scraping the first review page")
    first = await _request_reviews_api(url=url, business_id=business_id, start_index=1)
    review_data = parse_review_data(first)
    reviews = review_data["reviews"]
    total_reviews = review_data["total_reviews"]

    if max_reviews and max_reviews < total_reviews:
        total_reviews = max_reviews

    logger.info("scraping review pagination, remaining ({}) more pages", total_reviews // 10)
    for offset in range(11, total_reviews, 10):
        try:
            resp = await _request_reviews_api(url=url, business_id=business_id, start_index=offset)
            reviews.extend(parse_review_data(resp)["reviews"])
        except Exception as e:  # noqa: BLE001
            logger.error("error scraping review page offset {}: {}", offset, e)
    logger.success(f"scraped {len(reviews)} reviews from review pages")
    return reviews

async def scrape_search(
    keyword: str, location: str, max_pages: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Scrape Yelp search results for `keyword` near `location`."""

    def make_search_url(offset: int) -> str:
        base = "https://www.yelp.com/search?"
        return base + urlencode({"find_desc": keyword, "find_loc": location, "start": offset})

    logger.info("scraping the first search page")
    first_html = await _fetch_rendered_html(
        make_search_url(0), ready_selector="script[data-id='react-root-props']"
    )
    data = parse_search(first_html)
    search_data = data["search_data"]
    total_results = data["total_results"]

    total_pages = max(1, math.ceil(total_results / 10))
    if max_pages and max_pages < total_pages:
        total_pages = max_pages

    logger.info("scraping search pagination, remaining ({}) more pages", total_pages - 1)
    for offset in range(10, total_pages * 10, 10):
        try:
            html = await _fetch_rendered_html(
                make_search_url(offset), ready_selector="script[data-id='react-root-props']"
            )
            search_data.extend(parse_search(html)["search_data"])
        except Exception as e:  # noqa: BLE001
            logger.error("error scraping search page offset {}: {}", offset, e)
    logger.success(f"scraped {len(search_data)} listings from search pages")
    return search_data

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
