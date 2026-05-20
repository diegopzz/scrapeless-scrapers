"""Priceline scraper using the official Scrapeless Python SDK + Playwright over CDP.

Priceline is a Next.js + Apollo Client app. Both the listing and detail surfaces
hydrate React via the Apollo SSR Data Transport: a series of inline ``<script>``
tags that call

    (window[Symbol.for("ApolloSSRDataTransport")] ??= []).push({ rehydrate: { … } })

Each ``rehydrate`` payload contains the GraphQL data the server fetched, e.g.
``standaloneHotelListings.listings[].hotelInfo`` for search and
``rtlHotelDetails`` for the PDP. We read those payloads directly from the raw
HTML so we don't race against the client running its own GraphQL queries after
hydration.

Two surfaces:
- ``scrape_search(city_id, checkin, checkout)`` — Apollo SSR listings.
- ``scrape_hotel(hotel_id, checkin, checkout)`` — Apollo SSR + pcln-graph fallback.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional

from parsel import Selector
from playwright.async_api import Response, async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 300
HOMEPAGE_URL = "https://www.priceline.com/"


@dataclass
class Hotel:
    id: str
    url: str
    name: str
    description: str
    amenities: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    policies: List[Dict[str, Any]] = field(default_factory=list)
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    starRating: Optional[str] = None
    pageTitle: Optional[str] = None


@dataclass
class SearchResult:
    id: str
    name: str
    url: str
    price: Optional[str] = None
    starRating: Optional[float] = None
    review: Optional[float] = None
    reviewCount: Optional[int] = None
    image: Optional[str] = None
    neighborhood: Optional[str] = None


def _client() -> Scrapeless:
    if not os.environ.get("SCRAPELESS_API_KEY") and not os.environ.get("SCRAPELESS_KEY"):
        raise RuntimeError(
            "SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com"
        )
    if not os.environ.get("SCRAPELESS_API_KEY") and os.environ.get("SCRAPELESS_KEY"):
        os.environ["SCRAPELESS_API_KEY"] = os.environ["SCRAPELESS_KEY"]
    return Scrapeless()


def _hotel_detail_url(hotel_id: str, checkin: str = "", checkout: str = "") -> str:
    ci = checkin.replace("-", "")
    co = checkout.replace("-", "")
    segments = ["https://www.priceline.com/relax/at", str(hotel_id)]
    if ci:
        segments += ["from", ci]
    if co:
        segments += ["to", co]
    segments += ["rooms", "1"]
    return "/".join(segments)


def _list_url(city_id: str, checkin: str = "", checkout: str = "") -> str:
    ci = checkin.replace("-", "")
    co = checkout.replace("-", "")
    segments = ["https://www.priceline.com/relax/in", str(city_id)]
    if ci:
        segments += ["from", ci]
    if co:
        segments += ["to", co]
    segments += ["rooms", "1"]
    return "/".join(segments)


# ---------------- Apollo SSR transport extraction ----------------


def extract_apollo_rehydrate(html: str) -> Dict[str, Any]:
    """Pull every ``{ rehydrate: { … } }`` payload pushed to the SSR transport."""
    merged: Dict[str, Any] = {}
    pos = 0
    needle = ".push("
    while True:
        at = html.find(needle, pos)
        if at == -1:
            break
        before = html[max(0, at - 80):at]
        if "ApolloSSRDataTransport" not in before:
            pos = at + len(needle)
            continue
        start = at + len(needle)
        depth = 0
        i = start
        end = -1
        n = len(html)
        while i < n:
            c = html[i]
            if c == '"':
                i += 1
                while i < n and html[i] != '"':
                    if html[i] == "\\":
                        i += 1
                    i += 1
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
            i += 1
        if end < 0:
            break
        obj_str = re.sub(r":\s*undefined\b", ": null", html[start:end])
        try:
            obj = json.loads(obj_str)
            if isinstance(obj, dict) and isinstance(obj.get("rehydrate"), dict):
                merged.update(obj["rehydrate"])
        except Exception:
            pass
        pos = end
    return merged


def _walk(node: Any, predicate: Callable[[Any], bool], out: List[Any]) -> List[Any]:
    if not isinstance(node, (dict, list)):
        return out
    if isinstance(node, list):
        for v in node:
            _walk(v, predicate, out)
        return out
    if predicate(node):
        out.append(node)
    for v in node.values():
        _walk(v, predicate, out)
    return out


# ---------------- hotel ----------------


def _flatten_amenities(amenity_categories, amenities) -> List[str]:
    out: List[str] = []
    for cat in amenity_categories or []:
        for a in (cat or {}).get("amenities", []) or []:
            t = (a.get("name") or a.get("label")) if isinstance(a, dict) else (a if isinstance(a, str) else None)
            if t and t not in out:
                out.append(t)
    for a in amenities or []:
        t = (a.get("name") or a.get("label")) if isinstance(a, dict) else (a if isinstance(a, str) else None)
        if t and t not in out:
            out.append(t)
    return out


def _flatten_images(info: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for ig in info.get("imageGroups", []) or []:
        for img in (ig or {}).get("images", []) or []:
            u = img.get("fastlyUrl") or img.get("url") or img.get("source")
            if u and u not in out:
                out.append(u)
    for img in info.get("images", []) or []:
        u = img.get("fastlyUrl") or img.get("url") or img.get("source")
        if u and u not in out:
            out.append(u)
    return out


def parse_hotel_from_graphql(graphql_data: Dict[str, Any]) -> Dict[str, Any]:
    details = (graphql_data or {}).get("data", {}).get("rtlHotelDetails", {}) or {}
    if not details:
        details = (graphql_data or {}).get("rtlHotelDetails", {}) or {}
    info = details.get("hotelInfo", {}) or {}
    geo = info.get("geoCoordinate", {}) or {}
    policies = []
    for p in info.get("propertyPolicies", []) or []:
        policies.append({
            "type": p.get("type"),
            "label": p.get("label"),
            "description": (p.get("description") or {}).get("policyList", []),
        })
    return {
        "name": info.get("name") or "",
        "address": info.get("address") or None,
        "description": info.get("description") or "",
        "amenities": _flatten_amenities(info.get("amenityCategories"), info.get("amenities")),
        "images": _flatten_images(info),
        "latitude": geo.get("latitude") if isinstance(geo.get("latitude"), (int, float)) else None,
        "longitude": geo.get("longitude") if isinstance(geo.get("longitude"), (int, float)) else None,
        "starRating": info.get("starRating") or info.get("starLevelText") or None,
        "policies": policies,
    }


def _map_listing_item(info: Dict[str, Any], listing_wrapper: Optional[Dict[str, Any]] = None) -> Optional[SearchResult]:
    if not isinstance(info, dict):
        return None
    hid = str(info.get("id") or info.get("hotelId") or "")
    if not hid:
        return None
    name = info.get("name") or info.get("hotelName") or (info.get("brand") or {}).get("name") or ""
    if not name:
        return None
    property_info = info.get("propertyInfo") or {}
    review_info = info.get("reviewInfo") or info.get("review") or {}
    star_raw = property_info.get("starRating") or info.get("starRating") or info.get("starLevelText")
    star = None
    if isinstance(star_raw, (int, float)):
        star = float(star_raw)
    elif isinstance(star_raw, str):
        try:
            star = float(star_raw)
        except ValueError:
            star = None
    review_raw = review_info.get("guestRating") or review_info.get("overallGuestRating")
    review = float(review_raw) if isinstance(review_raw, (int, float)) else None
    rc_raw = review_info.get("totalReviewCount") or review_info.get("reviewCount")
    review_count: Optional[int]
    if isinstance(rc_raw, int):
        review_count = rc_raw
    elif isinstance(rc_raw, str):
        try:
            review_count = int(rc_raw.replace(",", ""))
        except ValueError:
            review_count = None
    else:
        review_count = None
    images = info.get("images") or []
    first = images[0] if images else None
    image = None
    if isinstance(first, dict):
        image = first.get("fastlyUrl") or first.get("url") or first.get("source")
    neighborhood = None
    if isinstance(info.get("neighborhood"), dict):
        neighborhood = info["neighborhood"].get("name")
    elif isinstance(info.get("location"), dict):
        neighborhood = info["location"].get("neighborhoodName")

    price: Optional[str] = None
    if listing_wrapper:
        candidates = [
            ((listing_wrapper.get("minRateSummary") or {}).get("formattedAverageNightlyPrice")),
            (lambda v: f"${round(v)}" if isinstance(v, (int, float)) else None)(
                (listing_wrapper.get("minRateSummary") or {}).get("averageNightlyPrice")
            ),
            (((listing_wrapper.get("rateAvailability") or {}).get("bestRoomRate") or {}).get("priceDetails") or {}).get("displayPrice"),
            (((listing_wrapper.get("rateAvailability") or {}).get("bestRoomRate") or {}).get("priceDetails") or {}).get("formattedPrice"),
        ]
        for c in candidates:
            if isinstance(c, str) and c:
                price = c
                break

    return SearchResult(
        id=hid,
        name=name,
        url=_hotel_detail_url(hid),
        price=price,
        starRating=star,
        review=review,
        reviewCount=review_count,
        image=image,
        neighborhood=neighborhood,
    )


async def scrape_hotel(
    hotel_id: str,
    checkin: str = "",
    checkout: str = "",
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
) -> Hotel:
    url = _hotel_detail_url(hotel_id, checkin, checkout)
    client = _client()
    session = client.browser.create(
        ICreateBrowser(proxy_country=proxy_country, session_ttl=DEFAULT_SESSION_TTL)
    )
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
        try:
            page = await browser.new_page()
            detail_responses: List[Dict[str, Any]] = []

            async def _on_response(resp: Response) -> None:
                try:
                    u = resp.url
                    if "/pws/v0/pcln-graph" not in u:
                        return
                    if not re.search(r"rtlHotelDetails|RtlHotelStandaloneDetails|InventoryQlContent", u, re.I):
                        return
                    text = await resp.text()
                    try:
                        detail_responses.append(json.loads(text))
                    except Exception:
                        pass
                except Exception:
                    pass

            page.on("response", lambda r: asyncio.create_task(_on_response(r)))
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(7000)
            html = await page.content()

            rehydrate = extract_apollo_rehydrate(html)
            info: Optional[Dict[str, Any]] = None
            for cand in _walk(rehydrate, lambda n: isinstance(n, dict) and n.get("rtlHotelDetails"), []):
                d = cand.get("rtlHotelDetails") or {}
                hi = d.get("hotelInfo") or {}
                if hi.get("address") or (hi.get("imageGroups") or []):
                    info = hi
                    break

            if info is None:
                best = None
                for r in detail_responses:
                    hi = ((r or {}).get("data") or {}).get("rtlHotelDetails", {}).get("hotelInfo") or {}
                    if not hi:
                        continue
                    score = (2 if hi.get("address") else 0) + (2 if hi.get("imageGroups") else 0) + (1 if hi.get("amenityCategories") else 0)
                    if not best or score > best[1]:
                        best = (hi, score)
                if best:
                    info = best[0]

            if info is None:
                raise RuntimeError(
                    f"priceline: no hotelInfo for {hotel_id} (Apollo SSR + GraphQL both empty — hotel ID may be invalid or page is anti-bot blocked)"
                )

            parsed = parse_hotel_from_graphql({"data": {"rtlHotelDetails": {"hotelInfo": info}}})
            sel = Selector(text=html)
            page_title = (sel.css("title::text").get() or "").strip() or None
            return Hotel(
                id=str(hotel_id),
                url=url,
                pageTitle=page_title,
                **parsed,
            )
        finally:
            try:
                await browser.close()
            except Exception:
                pass


async def scrape_search(
    city_id: str,
    checkin: str = "",
    checkout: str = "",
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
) -> List[SearchResult]:
    url = _list_url(city_id, checkin, checkout)
    client = _client()
    session = client.browser.create(
        ICreateBrowser(proxy_country=proxy_country, session_ttl=DEFAULT_SESSION_TTL)
    )
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(6000)
            html = await page.content()
            rehydrate = extract_apollo_rehydrate(html)
            containers = _walk(rehydrate, lambda n: isinstance(n, dict) and isinstance(n.get("listings"), list), [])
            listings: List[SearchResult] = []
            seen: set[str] = set()
            for c in containers:
                for l in c.get("listings") or []:
                    info = (l or {}).get("hotelInfo") or l
                    mapped = _map_listing_item(info, l if isinstance(l, dict) else None)
                    if mapped and mapped.id not in seen:
                        listings.append(mapped)
                        seen.add(mapped.id)
            if not listings:
                raise RuntimeError(
                    f"priceline: no listings found in Apollo SSR transport for city {city_id} (likely anti-bot block or empty city)"
                )
            return listings
        finally:
            try:
                await browser.close()
            except Exception:
                pass


def to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
