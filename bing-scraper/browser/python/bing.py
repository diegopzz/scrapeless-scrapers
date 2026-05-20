"""Bing scraper using the official Scrapeless Python SDK + Playwright over CDP.
function names and emitted field names match verbatim.

Bing has no Scrapeless Deep SerpApi actor as of writing, so both targets use
the browser pattern: `client.browser.create(...)` -> Playwright over CDP ->
render `https://www.bing.com/search?q=...` -> parse with parsel.
"""

from __future__ import annotations

import os
import re
from dataclasses import asdict
from typing import Any, Dict, List
from urllib.parse import quote_plus, urlparse

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
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
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

async def scrape_search(query: str, max_pages: int | None = None) -> List[Dict[str, Any]]:
    """Scrape Bing organic search results across `max_pages` pages."""
    pages = max_pages or 1
    out: List[Dict[str, Any]] = []
    position = 0
    for page_idx in range(pages):
        first = page_idx * 10 + 1  # Bing uses 1-indexed `first` parameter (1, 11, 21, ...)
        url = f"https://www.bing.com/search?q={quote_plus(query)}&first={first}"
        html = await _fetch_rendered_html(url, ready_selector="li.b_algo")
        for item in _parse_search(html):
            position += 1
            item["position"] = position
            out.append(item)
    return out

async def scrape_keywords(query: str) -> List[str]:
    """Scrape Bing's related-keyword suggestions.

    Bing's classic `li.b_ans` related-searches block was replaced by Copilot
    in 2024. The autosuggest endpoint (which powers the homepage search box)
    still returns the same related-keyword list as escaped HTML inside a
    `<pre>` element, which we unescape and parse for the `query` attribute.
    """
    url = (
        "https://www.bing.com/AS/Suggestions"
        f"?qry={quote_plus(query)}&cvid=test&cp={len(query)}"
        "&msbqf=false&cc=us&FORM=BESBTB"
    )
    html = await _fetch_rendered_html(url, ready_selector="pre")
    return _parse_keywords(html)

# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _domain_of(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        host = ""
    if host.startswith("www."):
        host = host[4:]
    return host

def _parse_search(html: str) -> List[Dict[str, Any]]:
    sel = Selector(text=html)
    out: List[Dict[str, Any]] = []
    for card in sel.xpath("//li[@class='b_algo']"):
        url = card.xpath(".//h2/a/@href").get() or ""
        title = "".join(card.xpath(".//h2/a//text()").getall()).strip()
        origin = "".join(card.xpath(".//cite//text()").getall()).strip()
        description = "".join(card.xpath(".//div[contains(@class,'b_caption')]/p//text()").getall()).strip()
        # Bing renders the date as a leading "<date> - " prefix on the snippet.
        date = ""
        m = re.match(r"^(.*?)\s+[·—\-]\s+(.*)$", description)
        if m and len(m.group(1)) <= 40:
            date = m.group(1).strip()
            description = m.group(2).strip()
        out.append(
            {
                "position": 0,  # filled in by caller
                "title": title,
                "url": url,
                "origin": origin,
                "domain": _domain_of(url),
                "description": description,
                "date": date,
            }
        )
    return out

def _parse_keywords(html: str) -> List[str]:
    sel = Selector(text=html)
    seen: List[str] = []
    # Classic Bing related-searches block (older SERPs).
    for raw in sel.xpath("//li[@class='b_ans']/div/ul/li//text()").getall():
        v = (raw or "").strip()
        if v and v not in seen:
            seen.append(v)
    if seen:
        return seen
    # Autosuggest endpoint: HTML is escaped inside a <pre> block.
    pre = "".join(sel.xpath("//pre//text()").getall()) or "".join(sel.xpath("//body//text()").getall())
    if not pre:
        return seen
    unescaped = (
        pre.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&amp;", "&")
    )
    inner = Selector(text=unescaped)
    for q in inner.xpath("//li[@query]/@query").getall():
        if q and q not in seen:
            seen.append(q)
    return seen

def to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
