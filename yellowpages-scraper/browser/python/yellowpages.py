"""YellowPages scraper using the official Scrapeless Python SDK + Playwright over CDP.
function names and emitted field names match verbatim, so downstream code can
Search pages: JSON-LD ItemList in the second `application/ld+json` block.
Detail pages: plain CSS selectors against the rendered HTML.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any
from urllib.parse import quote_plus

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 180

def _client() -> Scrapeless:
    if not os.environ.get("SCRAPELESS_API_KEY") and not os.environ.get("SCRAPELESS_KEY"):
        raise RuntimeError(
            "SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com"
        )
    if not os.environ.get("SCRAPELESS_API_KEY") and os.environ.get("SCRAPELESS_KEY"):
        os.environ["SCRAPELESS_API_KEY"] = os.environ["SCRAPELESS_KEY"]
    return Scrapeless()

def _looks_cloudflare(html: str) -> bool:
    if not html or len(html) < 8000:
        return True
    head = html[:4000]
    return any(s in head for s in ("Just a moment", "cf-browser-verification", "cf-challenge"))


async def _fetch_rendered_html(
    url: str,
    ready_selector: str | None = None,
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
    retries: int = 2,
    warmup: bool = True,
) -> str:
    last_error: Exception | None = None
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
                    try:
                        await page.goto("https://www.yellowpages.com/", wait_until="domcontentloaded", timeout=30000)
                        await asyncio.sleep(2.5)
                    except Exception:
                        pass
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                html = ""
                for _ in range(6):
                    if ready_selector:
                        try:
                            await page.wait_for_selector(ready_selector, timeout=5000)
                            break
                        except Exception:
                            pass
                    await asyncio.sleep(2.5)
                    html = await page.content()
                    if html and not _looks_cloudflare(html):
                        break
                if not html:
                    html = await page.content()
                if html and not _looks_cloudflare(html):
                    return html
                last_error = RuntimeError("cloudflare block" if _looks_cloudflare(html) else "empty HTML")
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
# Parsers — mirror the upstream reference's verbatim keys
# ---------------------------------------------------------------------------

def _parse_datetime(value: str) -> str:
    """`08:00-17:00` is already in the right shape; return as-is."""
    return (value or "").strip()

def parse_search(html: str) -> dict[str, Any]:
    sel = Selector(text=html)
    blocks = sel.xpath("//script[@type='application/ld+json']/text()").getall()
    data: list[dict[str, Any]] = []
    # YellowPages now emits the listings as a bare JSON-LD array of
    # LocalBusiness objects; legacy variants used `ItemList` + `itemListElement`.
    for raw in blocks:
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        candidates = payload if isinstance(payload, list) else [payload]
        for node in candidates:
            if not isinstance(node, dict):
                continue
            if node.get("@type") == "LocalBusiness":
                data.append(node)
                continue
            items = node.get("itemListElement")
            if isinstance(items, list):
                for entry in items:
                    item = entry.get("item") if isinstance(entry, dict) else None
                    if isinstance(item, dict):
                        data.append(item)
    total_pages = None
    page_text = sel.css(".pagination>span::text").get()
    if page_text:
        m = re.search(r"of\s+([\d,]+)", page_text)
        if m:
            total = int(m.group(1).replace(",", ""))
            total_pages = max(1, (total + 29) // 30)
    return {"data": data, "total_pages": total_pages}

def _local_business_ld(sel: Selector) -> dict[str, Any] | None:
    for raw in sel.xpath('//script[@type="application/ld+json"]/text()').getall():
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        candidates = payload if isinstance(payload, list) else [payload]
        for c in candidates:
            if not isinstance(c, dict):
                continue
            t = c.get("@type")
            if isinstance(t, str) and re.search(r"LocalBusiness|Plumber|Restaurant|Store|Organization|Service", t):
                return c
    return None


def parse_page(html: str) -> dict[str, Any]:
    sel = Selector(text=html)
    rating_class = sel.css(".ratings div::attr(class)").get() or ""
    rating = ""
    m = re.search(r"result\s+([a-z\s]+?)(?=$|\s\w+$)", rating_class)
    if m:
        rating = m.group(1).strip()
    working_hours: dict[str, str] = {}
    for row in sel.css(".open-details tr"):
        day = (row.css("th::text").get() or "").strip()
        hours = row.css("time::attr(datetime)").get()
        if day and hours:
            working_hours[day] = _parse_datetime(hours)
    phone_href = sel.css(".phone::attr(href)").get() or ""
    phone = phone_href.replace("tel:", "") if phone_href else ""
    out = {
        "name": (sel.css("h1.business-name::text").get() or "").strip(),
        "categories": [c.strip() for c in sel.css(".categories>a::text").getall() if c.strip()],
        "rating": rating,
        "ratingCount": (sel.css(".ratings .count::text").get() or "").strip(),
        "phone": phone,
        "website": sel.css(".website-link::attr(href)").get() or "",
        "address": (sel.css(".address::text").get() or "").strip(),
        "workingHours": working_hours,
    }
    # JSON-LD fallback for layout variants that drop the CSS selectors.
    ld = _local_business_ld(sel)
    if ld:
        if not out["name"] and isinstance(ld.get("name"), str):
            out["name"] = ld["name"]
        if not out["phone"] and isinstance(ld.get("telephone"), str):
            out["phone"] = ld["telephone"]
        if not out["address"] and isinstance(ld.get("address"), dict):
            a = ld["address"]
            out["address"] = ", ".join(
                str(x).strip() for x in (
                    a.get("streetAddress"), a.get("addressLocality"),
                    a.get("addressRegion"), a.get("postalCode"),
                )
                if isinstance(x, str) and x.strip()
            )
        if not out["workingHours"] and isinstance(ld.get("openingHours"), list):
            for spec in ld["openingHours"]:
                if not isinstance(spec, str):
                    continue
                m = re.match(r"^([A-Za-z-]+)\s+(\d{2}:\d{2}-\d{2}:\d{2})$", spec)
                if m:
                    out["workingHours"][m.group(1)] = m.group(2)
                else:
                    out["workingHours"][spec] = spec
    return out

# ---------------------------------------------------------------------------
# Scrape functions
# ---------------------------------------------------------------------------

async def scrape_search(
    query: str,
    location: str | None = None,
    max_pages: int | None = None,
) -> list[dict[str, Any]]:
    """Scrape YellowPages search across pages — returns one dict per page."""
    def url_for(page: int) -> str:
        loc = quote_plus(location) if location else ""
        return (
            "https://www.yellowpages.com/search"
            f"?search_terms={quote_plus(query)}&geo_location_terms={loc}&page={page}"
        )

    first_html = await _fetch_rendered_html(url_for(1), ready_selector=".search-results")
    first = parse_search(first_html)
    pages_out: list[dict[str, Any]] = [first]
    total = first.get("total_pages") or 1
    if max_pages is not None:
        total = min(total, max_pages)
    for p in range(2, total + 1):
        try:
            html = await _fetch_rendered_html(url_for(p), ready_selector=".search-results")
            pages_out.append(parse_search(html))
        except Exception as e:  # noqa: BLE001
            logger.warning("search page {} failed: {}", p, e)
            break
    return pages_out

async def scrape_pages(urls: list[str]) -> list[dict[str, Any]]:
    """Scrape individual YellowPages business detail pages."""
    out: list[dict[str, Any]] = []
    for url in urls:
        html = await _fetch_rendered_html(url, ready_selector="h1.business-name")
        out.append(parse_page(html))
    return out

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
