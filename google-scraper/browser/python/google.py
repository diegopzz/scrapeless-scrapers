"""Google scraper using the official Scrapeless Python SDK.
function names and emitted field names match verbatim.

Two surfaces:
- SERP + keyword suggestions: `client.deepserp.scrape(actor="scraper.google.search", ...)`.
- Google Maps places: `client.browser.create(...)` + Playwright over CDP (the maps
  place panel only renders inside a real browser).
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import asdict
from typing import Any, Dict, List
from urllib.parse import urlparse

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser, ScrapingTaskRequest

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 180
GOOGLE_SERP_ACTOR = "scraper.google.search"

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

def _deepserp_search(query: str, *, start: int = 0, hl: str = "en", gl: str = "us") -> Dict[str, Any]:
    """One Deep SerpApi call against the Google search actor."""
    client = _client()
    payload = {"q": query, "hl": hl, "gl": gl}
    if start:
        payload["start"] = start
    request = ScrapingTaskRequest(actor=GOOGLE_SERP_ACTOR, input=payload)
    result = client.deepserp.scrape(request=request)
    # SDK normally hands back a dict; tolerate the .data wrapper just in case.
    if isinstance(result, dict) and "data" in result and isinstance(result["data"], dict):
        return result["data"]
    return result if isinstance(result, dict) else {}

async def _fetch_rendered_html(
    url: str,
    ready_selector: str,
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
    retries: int = 1,
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
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                try:
                    await page.wait_for_selector(ready_selector, timeout=15000)
                except Exception as e:
                    logger.warning("wait_for_selector failed (continuing): {}", e)
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
# Scrape functions — mirror the upstream reference's exports verbatim
# ---------------------------------------------------------------------------

async def scrape_serp(query: str, max_pages: int | None = None) -> List[Dict[str, Any]]:
    """Scrape Google organic search results across `max_pages` pages."""
    pages = max_pages or 1
    out: List[Dict[str, Any]] = []
    position = 0
    for page_idx in range(pages):
        data = await asyncio.to_thread(_deepserp_search, query, start=page_idx * 10)
        for item in _extract_organic(data):
            position += 1
            url = item.get("url") or item.get("link") or ""
            out.append(
                {
                    "position": position,
                    "title": (item.get("title") or "").strip(),
                    "url": url,
                    "origin": item.get("origin") or item.get("source") or "",
                    "domain": _domain_of(url),
                    "description": (item.get("description") or item.get("snippet") or "").strip(),
                    "date": item.get("date") or "",
                }
            )
    return out

async def scrape_keywords(query: str) -> Dict[str, List[str]]:
    """Scrape "Searches related to …" and "People also ask" off the SERP."""
    data = await asyncio.to_thread(_deepserp_search, query)
    return {
        "related_search": _extract_related(data),
        "people_ask_for": _extract_paa(data),
    }

async def scrape_google_map_places(urls: List[str]) -> List[Dict[str, Any]]:
    """Scrape a list of Google Maps place URLs into structured place rows."""
    out: List[Dict[str, Any]] = []
    for url in urls:
        html = await _fetch_rendered_html(url, ready_selector="h1")
        out.append(_parse_place(html))
    return out

# ---------------------------------------------------------------------------
# Deep SerpApi response shape helpers
# ---------------------------------------------------------------------------

def _extract_organic(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ("organic_results", "organic", "results"):
        if isinstance(data.get(key), list):
            return data[key]
    return []

def _extract_related(data: Dict[str, Any]) -> List[str]:
    for key in ("related_searches", "related_search"):
        items = data.get(key)
        if isinstance(items, list):
            out: List[str] = []
            for it in items:
                if isinstance(it, str):
                    out.append(it.strip())
                elif isinstance(it, dict):
                    val = it.get("query") or it.get("name") or it.get("text") or ""
                    if val:
                        out.append(val.strip())
            return [v for v in out if v]
    return []

def _extract_paa(data: Dict[str, Any]) -> List[str]:
    for key in ("related_questions", "people_also_ask", "people_ask_for"):
        items = data.get(key)
        if isinstance(items, list):
            out: List[str] = []
            for it in items:
                if isinstance(it, str):
                    out.append(it.strip())
                elif isinstance(it, dict):
                    val = it.get("question") or it.get("title") or it.get("query") or ""
                    if val:
                        out.append(val.strip())
            return [v for v in out if v]
    return []

def _domain_of(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        host = ""
    if host.startswith("www."):
        host = host[4:]
    return host

# ---------------------------------------------------------------------------
# Maps place parser
# ---------------------------------------------------------------------------

_STARS_RE = re.compile(r"\d+(?:[,.]\d+)?")

def _aria_with_label(sel: Selector, label: str) -> str:
    raw = sel.xpath(f"//*[starts-with(@aria-label, '{label}')]/@aria-label").get() or ""
    return raw.replace(label, "", 1).strip()

def _aria_contains(sel: Selector, needle: str) -> str:
    return sel.xpath(f"//*[contains(@aria-label, '{needle}')]/@aria-label").get() or ""

def _star_bucket(sel: Selector, bucket: str) -> str:
    raw = sel.xpath(f"//*[contains(@aria-label, '{bucket}')]/@aria-label").get() or ""
    nums = _STARS_RE.findall(raw)
    return nums[-1] if nums else ""

def _parse_place(html: str) -> Dict[str, Any]:
    sel = Selector(text=html)
    stars_label = _aria_contains(sel, " stars")
    stars_match = _STARS_RE.search(stars_label)
    return {
        "name": "".join(sel.css("h1 ::text").getall()).strip(),
        "category": (sel.xpath("//button[contains(@jsaction, 'category')]//text()").get() or "").strip(),
        "address": _aria_with_label(sel, "Address: "),
        "website": _aria_with_label(sel, "Website: "),
        "phone": _aria_with_label(sel, "Phone: "),
        "review_count": _aria_contains(sel, " reviews"),
        "stars": stars_match.group(0) if stars_match else "",
        "5_stars": _star_bucket(sel, "5 stars"),
        "4_stars": _star_bucket(sel, "4 stars"),
        "3_stars": _star_bucket(sel, "3 stars"),
        "2_stars": _star_bucket(sel, "2 stars"),
        "1_stars": _star_bucket(sel, "1 stars"),
    }

def to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
