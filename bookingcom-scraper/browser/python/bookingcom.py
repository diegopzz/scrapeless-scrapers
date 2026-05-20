"""Booking.com scraper using the official Scrapeless Python SDK + Playwright over CDP.
function names and emitted field names match verbatim, so downstream code
can Booking.com is known to be aggressive about anti-bot. We delegate that to the
Scrapeless cloud browser session (fresh fingerprint + residential proxy) and
keep the same flow the upstream reference uses:
- `search_location_suggestions(query)` — POST the autocomplete endpoint
  from inside a live booking.com tab so Origin / Referer match.
- `scrape_search(...)` — open the search-results HTML page, parse property
  cards directly from the rendered DOM (more robust than Apollo-extraction
  against the Booking GraphQL endpoint over the cloud browser).
- `scrape_hotel(...)` — open the hotel page, parse hotel metadata, then POST
  the `AvailabilityCalendar` GraphQL query via in-page fetch (CSRF / cookies
  inherited).
- `scrape_hotel_reviews(...)` — open the reviews modal, capture the
  GraphQL response from the page's XHR log.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, TypedDict
from urllib.parse import urlencode

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

# Booking.com aggressively blocks proxies, especially when the proxy region
# doesn't match the search region. Default to GB (matches the en-gb locale we
# pass on the URL); the per-call helpers accept a `proxy_country` override so
# scrape_search can target e.g. MT/IT/ES/FR depending on the destination.
DEFAULT_PROXY_COUNTRY = "GB"
DEFAULT_SESSION_TTL = 300

TRANSIENT_NET_ERRORS = (
    "ERR_TUNNEL_CONNECTION_FAILED",
    "ERR_CONNECTION_CLOSED",
    "ERR_CONNECTION_RESET",
    "ERR_CONNECTION_REFUSED",
    "ERR_TIMED_OUT",
    "ERR_NETWORK_CHANGED",
    "ERR_EMPTY_RESPONSE",
    "ERR_PROXY_CONNECTION_FAILED",
    "Navigation timeout",
    "net::",
)

def _is_transient_error(err: Exception) -> bool:
    msg = str(err)
    return any(s in msg for s in TRANSIENT_NET_ERRORS)

# ---------------------------------------------------------------------------
# Types — mirror the upstream reference's TypedDicts verbatim
# ---------------------------------------------------------------------------

class Location(TypedDict, total=False):
    b_max_los_data: dict
    b_show_entire_homes_checkbox: bool
    cc1: str
    cjk: bool
    dest_id: str
    dest_type: str
    label: str
    label1: str
    label2: str
    labels: list
    latitude: float
    lc: str
    longitude: float
    nr_homes: int
    nr_hotels: int
    nr_hotels_25: int
    photo_uri: str
    roundtrip: str
    rtl: bool
    value: str

class LocationSuggestions(TypedDict):
    results: List[Location]

class PriceData(TypedDict, total=False):
    checkin: str
    minLengthOfStay: int
    avgPriceFormatted: str
    available: bool

class Hotel(TypedDict, total=False):
    url: str
    id: Optional[str]
    title: Optional[str]
    description: str
    address: Optional[str]
    images: List[str]
    lat: str
    lng: str
    features: Dict[str, List[str]]
    price: List[PriceData]

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

def _new_session(proxy_country: str = DEFAULT_PROXY_COUNTRY):
    client = _client()
    return client.browser.create(
        ICreateBrowser(proxy_country=proxy_country, session_ttl=DEFAULT_SESSION_TTL)
    )

async def _with_browser_retry(fn, *, proxy_country: str = DEFAULT_PROXY_COUNTRY, retries: int = 2, label: str = "navigation"):
    """Open a tab, run ``fn(page)``, close. Retries up to ``retries`` times on
    transient network errors (ERR_TUNNEL_CONNECTION_FAILED etc.) with
    exponential backoff. Each attempt mints a fresh cloud-browser session so
    the proxy IP / fingerprint rotates.
    """
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        session = _new_session(proxy_country)
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
            try:
                page = await browser.new_page()
                return await fn(page)
            except Exception as e:  # noqa: BLE001
                last_error = e
                logger.warning("{} attempt {} failed: {}", label, attempt + 1, e)
                if not _is_transient_error(e) and attempt > 0:
                    raise
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass
        if attempt < retries:
            await asyncio.sleep(5.0 * (2 ** attempt))
    raise RuntimeError(f"{label}: giving up after {retries + 1} attempts: {last_error}")

# ---------------------------------------------------------------------------
# Location suggestions
# ---------------------------------------------------------------------------

async def search_location_suggestions(query: str, *, proxy_country: str = DEFAULT_PROXY_COUNTRY) -> LocationSuggestions:
    """scrape booking.com location suggestions to find location details for search scraping"""

    async def _run(page):
        # Bootstrap a real booking.com tab so Origin/Referer + cookies are valid.
        await page.goto("https://www.booking.com/", wait_until="domcontentloaded", timeout=45000)
        body = json.dumps({"query": query, "pageview_id": "", "aid": 800210, "language": "en-us", "size": 5})
        text = await page.evaluate(
            """async ({ url, body }) => {
                const res = await fetch(url, {
                    method: "POST",
                    headers: {
                        "Content-Type": "text/plain;charset=UTF-8",
                    },
                    body,
                    credentials: "include",
                });
                return await res.text();
            }""",
            {"url": "https://accommodations.booking.com/autocomplete.json", "body": body},
        )
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("autocomplete response not JSON: {}", text[:200])
            return {"results": []}

    return await _with_browser_retry(_run, proxy_country=proxy_country, label="search_location_suggestions")

# ---------------------------------------------------------------------------
# Search-results parsing (HTML)
# ---------------------------------------------------------------------------

def parse_search_html(html: str) -> List[Dict[str, Any]]:
    """Parse property cards from a rendered booking.com search-results page.

    Field names mirror what the upstream reference's `parse_graphql_response` exposes for
    common fields downstream consumers care about (basicPropertyData fields).
    """
    sel = Selector(text=html)
    out: List[Dict[str, Any]] = []
    for card in sel.css("div[data-testid='property-card']"):
        name = (card.css("div[data-testid='title']::text").get() or "").strip()
        link = card.css("a[data-testid='title-link']::attr(href)").get() or ""
        location = (card.css("span[data-testid='address']::text").get() or "").strip()
        distance = (card.css("span[data-testid='distance']::text").get() or "").strip()

        score = (card.css("div[data-testid='review-score'] > div::text").get() or "").strip() or None
        review_count_text = " ".join(card.css("div[data-testid='review-score'] *::text").getall())
        review_count_m = re.search(r"([\d,]+)\s+reviews?", review_count_text)
        review_count = int(review_count_m.group(1).replace(",", "")) if review_count_m else None
        review_word = (
            card.css("div[data-testid='review-score'] > div + div > div::text").get() or ""
        ).strip() or None

        price_text = (card.css("span[data-testid='price-and-discounted-price']::text").get() or "").strip()

        photo = card.css("img[data-testid='image']::attr(src)").get()

        # Star rating: count star icons in title row.
        stars = card.css("div[data-testid='rating-stars'] svg").getall()
        star_rating = len(stars) if stars else None

        free_cancellation = bool(card.xpath(".//*[contains(text(),'Free cancellation')]"))

        out.append(
            {
                "displayName": {"text": name},
                "basicPropertyData": {
                    "pageName": link,
                    "location": {"address": location, "city": None, "countryCode": None},
                    "reviewScore": {
                        "score": score,
                        "reviewCount": review_count,
                        "totalScoreTextTag": {"translation": review_word},
                    },
                    "starRating": {"value": star_rating} if star_rating else None,
                    "photos": {"main": {"highResUrl": {"relativeUrl": photo}} if photo else None},
                },
                "location": {"displayLocation": location, "mainDistance": distance or None},
                "priceDisplayInfoIrene": {
                    "displayPrice": {"amountPerStay": {"amount": price_text}} if price_text else None
                },
                "policies": {"showFreeCancellation": free_cancellation},
            }
        )
    return out

# ---------------------------------------------------------------------------
# Hotel parsing — mirror the upstream reference's parse_hotel verbatim
# ---------------------------------------------------------------------------

def parse_hotel(html: str, url: str) -> Hotel:
    logger.debug("parsing hotel page: {}", url)
    sel = Selector(text=html)
    features: Dict[str, List[str]] = defaultdict(list)
    for wrapper in sel.css('[data-testid="property-most-popular-facilities-wrapper"]'):
        header = (wrapper.css("h3 ::text").get() or "").strip()
        feats = [f.strip() for f in wrapper.css("li ::text").getall() if f.strip()]
        if header and feats:
            features[header] = feats

    addr_xpath = sel.xpath(
        "//div[@data-testid='PropertyHeaderAddressDesktop-wrapper']//a/@data-atlas-latlng"
    ).get()
    lat, lng = (addr_xpath.split(",") if addr_xpath else ("", ""))

    id_match = re.findall(r"b_hotel_id:\s*'(.+?)'", html)
    description = "\n".join(
        sel.css(
            '[data-capla-component-boundary="b-property-web-property-page/PropertyDescriptionDesktop"] ::text'
        ).getall()
    ).strip()
    return {
        "url": url,
        "id": id_match[0] if id_match else None,
        "title": sel.css("h2::text").get(),
        "description": description,
        "address": sel.xpath(
            "//div[@data-testid='PropertyHeaderAddressDesktop-wrapper']//button/div/text()"
        ).get(),
        "images": sel.css("#photo_wrapper img::attr(src)").getall(),
        "lat": lat,
        "lng": lng,
        "features": dict(features),
    }

# ---------------------------------------------------------------------------
# Scrape functions — mirror the upstream reference's exports verbatim
# ---------------------------------------------------------------------------

async def scrape_search(
    query: str,
    checkin: str = "",
    checkout: str = "",
    number_of_rooms: int = 1,
    max_pages: Optional[int] = None,
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
) -> List[Dict[str, Any]]:
    """Scrape booking.com search.

    Discovers the destination via `search_location_suggestions` (matching the upstream reference),
    builds the same search URL params, then loads each result page in a fresh
    cloud-browser tab and parses the cards.
    """
    logger.info("scraping search for {} {}-{}", query, checkin, checkout)
    location_suggestions = await search_location_suggestions(query, proxy_country=proxy_country)
    if not location_suggestions.get("results"):
        logger.warning("no location suggestions for query={}", query)
        return []
    destination = location_suggestions["results"][0]
    url_params = urlencode(
        {
            "ss": destination["value"],
            "ssne": destination["value"],
            "ssne_untouched": destination["value"],
            "checkin": checkin,
            "checkout": checkout,
            "no_rooms": number_of_rooms,
            "dest_id": destination["dest_id"],
            "dest_type": destination["dest_type"],
            "efdco": 1,
            "group_adults": 1,
            "group_children": 0,
            "lang": "en-gb",
            "sb": 1,
            "sb_travel_purpose": "leisure",
            "src": "index",
            "src_elem": "sb",
        }
    )
    base_url = "https://www.booking.com/searchresults.en-gb.html?" + url_params

    pages_to_scrape = max_pages or 1
    all_results: List[Dict[str, Any]] = []
    for page_index in range(pages_to_scrape):
        offset = page_index * 25
        url = base_url + (f"&offset={offset}" if offset else "")
        logger.info("scraping search page {} ({})", page_index + 1, url)

        async def _run(page, url=url):
            # Warm up against the homepage first so booking.com sets its session
            # cookies before we hit the heavily-defended search-results endpoint.
            try:
                await page.goto("https://www.booking.com/", wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(1.5)
            except Exception:
                pass
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            try:
                await page.wait_for_selector("div[data-testid='property-card']", timeout=30000)
            except Exception as e:
                logger.warning("search wait_for_selector failed: {}", e)
            html = await page.content()
            return parse_search_html(html)

        cards = await _with_browser_retry(
            _run, proxy_country=proxy_country, label=f"scrape_search page={page_index + 1}"
        )
        all_results.extend(cards)
        logger.info("page {} returned {} cards", page_index + 1, len(cards))
        if not cards:
            break
    logger.success("scraped {} results from search pages", len(all_results))
    return all_results

async def scrape_hotel(url: str, checkin: str, price_n_days: int = 61, *, proxy_country: str = DEFAULT_PROXY_COUNTRY) -> Hotel:
    """Scrape Booking.com hotel data and pricing information."""
    logger.info("scraping hotel {} {} with {} days of pricing data", url, checkin, price_n_days)

    async def _run(page):
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        try:
            await page.wait_for_selector("h2", timeout=30000)
        except Exception as e:
            logger.warning("hotel wait failed: {}", e)
        # Trigger lazy-loaded sections (mimics the upstream reference's auto_scroll).
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1.0)
            await page.evaluate("window.scrollTo(0, 0)")
        except Exception:
            pass
        html = await page.content()
        hotel = parse_hotel(html, url)

        # Extract the hotel variables Booking embeds in the HTML for GraphQL.
        country = (re.findall(r'hotelCountry:\s*"(.+?)"', html) or [None])[0]
        name = (re.findall(r'hotelName:\s*"(.+?)"', html) or [None])[0]
        csrf = (re.findall(r"b_csrf_token:\s*'(.+?)'", html) or [None])[0]

        price_days: List[Dict[str, Any]] = []
        if country and name and csrf:
            gql_body = {
                "operationName": "AvailabilityCalendar",
                "variables": {
                    "input": {
                        "travelPurpose": 2,
                        "pagenameDetails": {
                            "countryCode": country,
                            "pagename": name,
                        },
                        "searchConfig": {
                            "searchConfigDate": {
                                "startDate": checkin,
                                "amountOfDays": price_n_days,
                            },
                            "nbAdults": 2,
                            "nbRooms": 1,
                        },
                    }
                },
                "extensions": {},
                "query": (
                    "query AvailabilityCalendar($input: AvailabilityCalendarQueryInput!) "
                    "{ availabilityCalendar(input: $input) { ... on AvailabilityCalendarQueryResult "
                    "{ hotelId days { available avgPriceFormatted checkin minLengthOfStay __typename } "
                    "__typename } ... on AvailabilityCalendarQueryError { message __typename } __typename } }"
                ),
            }
            price_text = await page.evaluate(
                """async ({ url, body, csrf, referer }) => {
                    const res = await fetch(url, {
                        method: "POST",
                        headers: {
                            "content-type": "application/json",
                            "x-booking-csrf-token": csrf,
                            "referer": referer,
                            "origin": "https://www.booking.com",
                        },
                        body: JSON.stringify(body),
                        credentials: "include",
                    });
                    return await res.text();
                }""",
                {
                    "url": "https://www.booking.com/dml/graphql?lang=en-gb",
                    "body": gql_body,
                    "csrf": csrf,
                    "referer": url,
                },
            )
            try:
                price_data = json.loads(price_text)
                price_days = (
                    price_data.get("data", {})
                    .get("availabilityCalendar", {})
                    .get("days", [])
                ) or []
            except json.JSONDecodeError:
                logger.warning("price response not JSON: {}", price_text[:200])
        else:
            logger.warning("missing hotelCountry/hotelName/csrf — skipping price calendar")

        hotel["price"] = price_days
        return hotel

    return await _with_browser_retry(_run, proxy_country=proxy_country, label="scrape_hotel")

async def scrape_hotel_reviews(url: str, max_pages: Optional[int] = None, *, proxy_country: str = DEFAULT_PROXY_COUNTRY) -> List[Dict[str, Any]]:
    """Scrape hotel review data."""
    reviews_page_url = url + "?force_referer=#tab-reviews"
    logger.info("scraping reviews for {}", url)

    async def _run(page):
        reviews_data: List[Dict[str, Any]] = []
        captured_xhr: Dict[str, Any] = {}

        async def on_response(response):
            try:
                if "/dml/graphql" not in response.url:
                    return
                body = await response.text()
                if "reviewCard" in body:
                    req = response.request
                    captured_xhr["body"] = body
                    captured_xhr["request_body"] = req.post_data or ""
            except Exception:
                pass

        page.on("response", lambda r: asyncio.ensure_future(on_response(r)))
        await page.goto(reviews_page_url, wait_until="domcontentloaded", timeout=60000)
        # Trigger reviews modal.
        try:
            await page.wait_for_selector("button[data-testid='fr-read-all-reviews']", timeout=15000)
            await page.click("button[data-testid='fr-read-all-reviews']")
        except Exception:
            try:
                await page.wait_for_selector("[data-testid='PropertyReviewsRegionBlock']", timeout=15000)
            except Exception:
                pass
        # Wait for the GraphQL response.
        deadline = asyncio.get_event_loop().time() + 20
        while "body" not in captured_xhr and asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(0.5)

        if "body" not in captured_xhr:
            logger.warning("no reviewCard XHR captured")
            return []

        first = json.loads(captured_xhr["body"])
        initial = first.get("data", {}).get("reviewListFrontend", {}) or {}
        total_review_count = int(initial.get("reviewsCount") or 0)
        reviews_data.extend(initial.get("reviewCard") or [])

        total_pages = math.ceil(total_review_count / 10) if total_review_count else 1
        effective_max_pages = max_pages
        if effective_max_pages is None or effective_max_pages > total_pages:
            effective_max_pages = total_pages

        html = await page.content()
        csrf = (re.findall(r"b_csrf_token:\s*'(.+?)'", html) or [None])[0]
        try:
            gql_body = json.loads(captured_xhr["request_body"])
        except json.JSONDecodeError:
            gql_body = None

        # Paginate via in-page fetch.
        if gql_body and csrf:
            for offset in range(10, effective_max_pages * 10, 10):
                page_body = json.loads(json.dumps(gql_body))  # deep copy
                try:
                    page_body["variables"]["input"]["skip"] = offset
                except Exception:
                    continue
                text = await page.evaluate(
                    """async ({ url, body, csrf, referer }) => {
                        const res = await fetch(url, {
                            method: "POST",
                            headers: {
                                "content-type": "application/json",
                                "x-booking-csrf-token": csrf,
                                "referer": referer,
                                "origin": "https://www.booking.com",
                            },
                            body: JSON.stringify(body),
                            credentials: "include",
                        });
                        return await res.text();
                    }""",
                    {
                        "url": "https://www.booking.com/dml/graphql?lang=en-gb",
                        "body": page_body,
                        "csrf": csrf,
                        "referer": reviews_page_url,
                    },
                )
                try:
                    page_data = json.loads(text)
                    reviews_data.extend(
                        page_data.get("data", {}).get("reviewListFrontend", {}).get("reviewCard", [])
                    )
                except json.JSONDecodeError:
                    continue
        logger.success("scraped {} reviews from {}", len(reviews_data), url)
        return reviews_data

    return await _with_browser_retry(_run, proxy_country=proxy_country, label="scrape_hotel_reviews")

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
