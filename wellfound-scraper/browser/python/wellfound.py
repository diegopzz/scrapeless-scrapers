"""Wellfound (formerly AngelList) scraper using the Scrapeless SDK + Playwright/CDP.
function names and emitted field names match verbatim, including the upstream
`remtoe` typo on JobData.

Wellfound is a Next.js + Apollo app: the company graph hydrates into
`<script id="__NEXT_DATA__">` under `props.pageProps.apolloState.data`. We walk
that graph, resolve "Startup:..." nodes, and dereference Apollo refs so the
output matches the upstream reference's CompanyData TypedDict.
"""

from __future__ import annotations

import json
import os
from typing import Any

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
    ready_selector: str | None = "script#__NEXT_DATA__",
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
                if ready_selector:
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
# Apollo graph helpers
# ---------------------------------------------------------------------------

def extract_apollo_state(html: str) -> dict[str, Any]:
    """Return `props.pageProps.apolloState.data` from `__NEXT_DATA__`."""
    sel = Selector(text=html)
    raw = sel.css("script#__NEXT_DATA__::text").get()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    try:
        return data["props"]["pageProps"]["apolloState"]["data"]
    except (KeyError, TypeError):
        return {}

def _is_ref(value: Any) -> bool:
    return isinstance(value, dict) and "__ref" in value and len(value) == 1

def _resolve(value: Any, graph: dict[str, Any]) -> Any:
    if _is_ref(value):
        return _resolve(graph.get(value["__ref"], {}), graph)
    if isinstance(value, list):
        return [_resolve(v, graph) for v in value]
    if isinstance(value, dict):
        return {k: _resolve(v, graph) for k, v in value.items()}
    return value

def parse_company(html: str) -> list[dict[str, Any]]:
    """Wellfound's Apollo cache uses `Startup:` keys on company pages and
    `StartupResult:` keys on search-result (role/location) pages."""
    graph = extract_apollo_state(html)
    out: list[dict[str, Any]] = []
    for key, node in graph.items():
        if not isinstance(node, dict):
            continue
        if not (key.startswith("Startup:") or key.startswith("StartupResult:")):
            continue
        out.append(_resolve(node, graph))
    return out

# ---------------------------------------------------------------------------
# Scrape functions — mirror the upstream reference's exports verbatim
# ---------------------------------------------------------------------------

def _search_url(role: str = "", location: str = "") -> str:
    role = role.strip()
    location = location.strip()
    if role and location:
        return f"https://wellfound.com/role/l/{role}/{location}"
    if role:
        return f"https://wellfound.com/role/{role}"
    if location:
        return f"https://wellfound.com/location/{location}"
    raise ValueError("scrape_search requires at least role or location")

async def scrape_search(
    role: str = "",
    location: str = "",
    max_pages: int | None = None,
) -> list[dict[str, Any]]:
    """Scrape Wellfound role / location listings."""
    base = _search_url(role, location)
    pages = max_pages if max_pages else 1
    out: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        url = base if page == 1 else f"{base}?page={page}"
        try:
            html = await _fetch_rendered_html(url)
            out.extend(parse_company(html))
        except Exception as e:  # noqa: BLE001
            logger.warning("search page {} failed: {}", url, e)
            break
    return out

async def scrape_companies(urls: list[str]) -> list[dict[str, Any]]:
    """Scrape individual Wellfound company pages — accepts full URLs."""
    out: list[dict[str, Any]] = []
    for url in urls:
        html = await _fetch_rendered_html(url)
        companies = parse_company(html)
        # Each page usually carries exactly one Startup node; keep all.
        out.extend(companies)
    return out

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
