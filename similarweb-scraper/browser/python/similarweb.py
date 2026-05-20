"""Similarweb scraper using the official Scrapeless Python SDK + Playwright over CDP.
function names and emitted field names match verbatim.

Similarweb is a React SPA with strong anti-bot. The richest payload lives in
`window.__APP_DATA__` (a JSON blob embedded in a script tag) — more stable than
the rendered DOM. All targets render via `client.browser.create(...)` + CDP and
parse the embedded JSON.
"""

from __future__ import annotations

import base64
import gzip
import json
import os
import re
from dataclasses import asdict
from typing import Any, Dict, List

import jmespath
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
    wait_for_global: str | None = None,
    eval_global: str | None = None,
):
    """Fetch rendered HTML over CDP.

    If `eval_global` is provided, returns a tuple `(html, evaluated)`; otherwise
    returns just the HTML string. The hidden-data extraction path uses
    `eval_global` to grab the JS global directly (more reliable than regex on the
    rendered HTML).
    """
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
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                try:
                    await page.wait_for_selector(ready_selector, timeout=20000)
                except Exception as e:
                    logger.warning("wait_for_selector failed (continuing): {}", e)
                if wait_for_global:
                    try:
                        await page.wait_for_function(f"!!window.{wait_for_global}", timeout=15000)
                    except Exception as e:
                        logger.warning("wait_for_function({}) failed (continuing): {}", wait_for_global, e)
                evaluated = None
                if eval_global:
                    try:
                        evaluated = await page.evaluate(eval_global)
                    except Exception as e:
                        logger.warning("page.evaluate failed (continuing): {}", e)
                html = await page.content()
                if html:
                    if eval_global is not None:
                        return html, evaluated
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

async def _fetch_raw_response(url: str, *, proxy_country: str = DEFAULT_PROXY_COUNTRY) -> bytes:
    """Fetch raw bytes (e.g. .xml.gz). Uses Playwright's APIRequestContext to skip rendering."""
    client = _client()
    session = client.browser.create(
        ICreateBrowser(proxy_country=proxy_country, session_ttl=DEFAULT_SESSION_TTL)
    )
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
        try:
            ctx = await browser.new_context()
            response = await ctx.request.get(url, timeout=45000)
            return await response.body()
        finally:
            try:
                await browser.close()
            except Exception:
                pass

# ---------------------------------------------------------------------------
# Embedded-JSON helpers
# ---------------------------------------------------------------------------

_APP_DATA_RE = re.compile(r"window\.__APP_DATA__\s*=\s*(\{.*?\})\s*;\s*window\.__APP_META__", re.DOTALL)

def _extract_balanced_json(text: str, start_idx: int) -> str | None:
    """Walk a balanced JSON object starting at text[start_idx] (must be '{')."""
    if text[start_idx] != "{":
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start_idx, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == "\\":
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start_idx : i + 1]
    return None

def parse_hidden_data(html: str) -> Dict[str, Any]:
    """Extract the `window.__APP_DATA__` JSON payload."""
    m = _APP_DATA_RE.search(html)
    if m:
        return json.loads(m.group(1))
    # Balanced-brace fallback: handles the case where __APP_META__ is missing.
    marker_idx = html.find("__APP_DATA__")
    if marker_idx == -1:
        raise RuntimeError("could not locate window.__APP_DATA__")
    brace_idx = html.find("{", marker_idx)
    if brace_idx == -1:
        raise RuntimeError("could not locate window.__APP_DATA__")
    slice_ = _extract_balanced_json(html, brace_idx)
    if not slice_:
        raise RuntimeError("could not locate window.__APP_DATA__")
    return json.loads(slice_)

# ---------------------------------------------------------------------------
# Scrape functions — mirror the upstream reference's exports verbatim
# ---------------------------------------------------------------------------

def _pick_hidden_data(evaluated: Any, html: str) -> Dict[str, Any]:
    """Prefer the live JS global; fall back to the regex/HTML path when the
    global is missing OR shallow (e.g. layout.data not yet populated)."""
    if (
        isinstance(evaluated, dict)
        and isinstance(evaluated.get("layout"), dict)
        and isinstance(evaluated["layout"].get("data"), dict)
        and len(evaluated["layout"]["data"]) > 0
    ):
        return evaluated
    return parse_hidden_data(html)

async def scrape_website(domains: List[str]) -> List[Dict[str, Any]]:
    """Scrape Similarweb's website overview page for each domain."""
    out: List[Dict[str, Any]] = []
    for domain in domains:
        url = f"https://www.similarweb.com/website/{domain}/"
        html, evaluated = await _fetch_rendered_html(
            url,
            ready_selector='[data-test-id="website-name"], h1',
            wait_for_global="__APP_DATA__",
            eval_global="window.__APP_DATA__ || null",
        )
        data = _pick_hidden_data(evaluated, html)
        out.append(jmespath.search("layout.data", data) or {})
    return out

async def scrape_website_compare(first_domain: str, second_domain: str) -> Dict[str, Dict[str, Any]]:
    """Scrape Similarweb's compare page and return JMESPath-extracted subsets per domain."""
    url = f"https://www.similarweb.com/website/{first_domain}/vs/{second_domain}/"
    html, evaluated = await _fetch_rendered_html(
        url,
        ready_selector='[data-test-id="website-name"], h1',
        wait_for_global="__APP_DATA__",
        eval_global="window.__APP_DATA__ || null",
    )
    data = _pick_hidden_data(evaluated, html)
    layout = jmespath.search("layout.data", data) or {}
    compare = jmespath.search("compareCompetitor", layout) or layout
    subset_query = "{overview: overview, traffic: traffic, trafficSources: trafficSources, ranking: ranking, demographics: demographics, geography: geography}"
    first = jmespath.search(subset_query, compare.get(first_domain, compare)) or {}
    second = jmespath.search(subset_query, compare.get(second_domain, {})) or {}
    return {first_domain: first, second_domain: second}

async def scrape_sitemaps(url: str) -> List[str]:
    """Download a Similarweb sitemap (.xml.gz), gunzip, return `<loc>` URLs."""
    body = await _fetch_raw_response(url)
    try:
        decompressed = gzip.decompress(body)
    except OSError:
        # Some endpoints return base64-wrapped gzip; tolerate it.
        decompressed = gzip.decompress(base64.b64decode(body))
    sel = Selector(text=decompressed.decode("utf-8", errors="ignore"), type="xml")
    return sel.xpath("//url/loc/text()").getall()

async def scrape_trendings(urls: List[str]) -> List[Dict[str, Any]]:
    """Scrape Similarweb trending-category pages via the embedded JSON-LD block."""
    out: List[Dict[str, Any]] = []
    for url in urls:
        html = await _fetch_rendered_html(url, ready_selector="script#dataset-json-ld")
        sel = Selector(text=html)
        raw = sel.xpath("//script[@id='dataset-json-ld']/text()").get() or "{}"
        try:
            doc = json.loads(raw)
        except json.JSONDecodeError:
            doc = {}
        main = doc.get("mainEntity") or {}
        out.append(
            {
                "name": main.get("name") or "",
                "url": url,
                "list": main.get("itemListElement") or [],
            }
        )
    return out

def to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
