"""LinkedIn scraper using the official Scrapeless Python SDK + Playwright over CDP.
**Public surfaces only.** LinkedIn aggressively walls off logged-in content;
this scraper only touches:
  - public profile pages              -> https://linkedin.com/in/<slug>
  - public company pages              -> https://linkedin.com/company/<id> (and /life)
  - the unauthenticated jobs guest API -> /jobs-guest/jobs/api/seeMoreJobPostings/search
  - job posting pages                  -> /jobs/view/<id>
  - articles                           -> /pulse/<slug>
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import quote

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

async def _fetch_rendered_html(
    url: str,
    ready_selector: str | None = None,
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

def _strip_text(value: str | None) -> str:
    return (value or "").strip()

def _find_ld_node(graph: list[dict[str, Any]], type_name: str) -> dict[str, Any] | None:
    for node in graph:
        t = node.get("@type")
        if t == type_name or (isinstance(t, list) and type_name in t):
            return node
    return None

# ---------------------------------------------------------------------------
# Parsers — mirror the upstream reference's keys verbatim
# ---------------------------------------------------------------------------

def parse_profile(html: str) -> dict[str, Any]:
    sel = Selector(text=html)
    blocks = sel.xpath("//script[@type='application/ld+json']/text()").getall()
    graph: list[dict[str, Any]] = []
    for raw in blocks:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and "@graph" in data:
            graph.extend(data["@graph"])
        elif isinstance(data, list):
            graph.extend(data)
        elif isinstance(data, dict):
            graph.append(data)
    profile = _find_ld_node(graph, "Person") or {}
    posts = [n for n in graph if (
        n.get("@type") == "Article"
        or (isinstance(n.get("@type"), list) and "Article" in n["@type"])
    )]
    return {"profile": profile, "posts": posts}

def parse_company(html: str) -> dict[str, Any]:
    sel = Selector(text=html)
    blocks = sel.xpath("//script[@type='application/ld+json']/text()").getall()
    org: dict[str, Any] = {}
    for raw in blocks:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            t = data.get("@type")
            if t == "Organization" or (isinstance(t, list) and "Organization" in t):
                org = data
                break
            if "@graph" in data:
                cand = _find_ld_node(data["@graph"], "Organization")
                if cand:
                    org = cand
                    break

    out: dict[str, Any] = {
        "name": org.get("name", ""),
        "url": org.get("url", ""),
        "mainAddress": org.get("address"),
        "description": org.get("description"),
        "numberOfEmployees": org.get("numberOfEmployees"),
        "logo": org.get("logo"),
    }
    # Lift the about-us key/value pairs (Industry, Company size, etc.).
    for row in sel.xpath("//div[contains(@data-test-id, 'about-us')]//dl/div"):
        key = _strip_text(row.xpath(".//dt//text()").get())
        val = _strip_text(" ".join(row.xpath(".//dd//text()").getall()))
        if key:
            out[key] = val

    # /life surface extras — only present if URL ends in /life.
    leaders = []
    for li in sel.xpath("//section[@data-test-id='leaders-at']//li"):
        leaders.append({
            "name": _strip_text(li.xpath(".//h3//text()").get()),
            "linkedinProfileLink": li.xpath(".//a/@href").get() or "",
        })
    if leaders:
        out["leaders"] = leaders

    def _page_list(xp: str) -> list[dict[str, Any]]:
        items = []
        for li in sel.xpath(xp):
            items.append({
                "name": _strip_text(li.xpath(".//h3//text()").get()),
                "industry": _strip_text(li.xpath(".//p[1]//text()").get()),
                "address": _strip_text(li.xpath(".//p[2]//text()").get()),
                # the upstream reference emits this key with a typo — preserve it.
                "linkeinUrl": li.xpath(".//a/@href").get() or "",
            })
        return items

    aff = _page_list("//section[@data-test-id='affiliated-pages']/div/div/ul/li")
    sim = _page_list("//section[@data-test-id='similar-pages']/div/div/ul/li")
    if aff:
        out["affiliatedPages"] = aff
    if sim:
        out["similarPages"] = sim
    return out

def parse_job_search(html: str) -> dict[str, Any]:
    sel = Selector(text=html)
    # Current public layout: ul.jobs-search__results-list > li > div.base-search-card
    cards = sel.xpath(
        "//ul[contains(@class, 'jobs-search__results-list')]/li[.//div[contains(@class, 'base-search-card')] or .//h3]"
    )
    if not cards:
        cards = sel.xpath("//section[contains(@class, 'results-list')]/ul/li")
    if not cards:
        cards = sel.xpath("//li[contains(@class, 'jobs-search-results__list-item') or contains(@class, 'result-card')]")
    if not cards:
        cards = sel.xpath("//div[contains(@class, 'base-search-card') or contains(@class, 'job-search-card')]")
    data = []
    for li in cards:
        title = _strip_text(li.xpath(".//h3//text()").get())
        company = _strip_text(li.xpath(".//h4//text()").get())
        if not title and not company:
            continue
        data.append({
            "title": title,
            "company": company,
            "address": _strip_text(li.xpath(".//*[contains(@class, 'job-search-card__location')]//text()").get()),
            "timeAdded": li.xpath(".//time/@datetime").get() or "",
            "jobUrl": li.xpath(".//a[contains(@class, 'base-card__full-link')]/@href").get()
                      or li.xpath(".//a/@href").get() or "",
            "companyUrl": li.xpath(".//h4//a/@href").get() or "",
        })
    total_text = sel.xpath("//span[contains(@class, 'results-context-header__job-count')]//text()").get()
    total = None
    if total_text:
        try:
            total = int("".join(c for c in total_text if c.isdigit()))
        except ValueError:
            total = None
    return {"data": data, "total_results": total}

def parse_job_page(html: str) -> dict[str, Any]:
    sel = Selector(text=html)
    blocks = sel.xpath("//script[@type='application/ld+json']/text()").getall()
    payload: dict[str, Any] = {}
    for raw in blocks:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            t = data.get("@type")
            if t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t):
                payload = data
                break
    bullets = sel.xpath("//div[contains(@class, 'show-more')]/ul/li/text()").getall()
    if bullets:
        payload["jobDescription"] = [_strip_text(b) for b in bullets if _strip_text(b)]
    return payload

def parse_article_page(html: str) -> dict[str, Any]:
    sel = Selector(text=html)
    blocks = sel.xpath("//script[@type='application/ld+json']/text()").getall()
    payload: dict[str, Any] = {}
    for raw in blocks:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            t = data.get("@type")
            if t == "Article" or (isinstance(t, list) and "Article" in t):
                payload = data
                break
    spans = sel.xpath(
        "//article/div[@data-test-id='article-content-blocks']/div/p/span/text()"
    ).getall()
    if spans:
        payload["articleBody"] = "\n".join(_strip_text(s) for s in spans if _strip_text(s))
    return payload

# ---------------------------------------------------------------------------
# Scrape functions — mirror the upstream reference's exports verbatim
# ---------------------------------------------------------------------------

async def scrape_profile(urls: list[str]) -> list[dict[str, Any]]:
    """Scrape public LinkedIn profile pages."""
    out = []
    for url in urls:
        html = await _fetch_rendered_html(url, ready_selector="script[type='application/ld+json']")
        out.append(parse_profile(html))
    return out

async def scrape_company(urls: list[str]) -> list[dict[str, Any]]:
    """Scrape public LinkedIn company pages."""
    out = []
    for url in urls:
        html = await _fetch_rendered_html(url, ready_selector="script[type='application/ld+json']")
        out.append(parse_company(html))
    return out

async def scrape_job_search(
    keyword: str, location: str, max_pages: int | None = None
) -> list[dict[str, Any]]:
    """Scrape the LinkedIn jobs guest API."""
    first_url = (
        f"https://www.linkedin.com/jobs/search?keywords={quote(keyword)}"
        f"&location={quote(location)}"
    )
    first_html = await _fetch_rendered_html(first_url, ready_selector="section.results-list, ul")
    first_page = parse_job_search(first_html)
    pages: list[dict[str, Any]] = [first_page]
    pages_to_fetch = max_pages if max_pages else 1
    # Guest pagination uses /jobs-guest/jobs/api/seeMoreJobPostings/search?...&start=N
    for i in range(1, pages_to_fetch):
        start = i * 25
        url = (
            "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
            f"?keywords={quote(keyword)}&location={quote(location)}&start={start}"
        )
        try:
            html = await _fetch_rendered_html(url)
            pages.append(parse_job_search(html))
        except Exception as e:  # noqa: BLE001
            logger.warning("job-search pagination failed at start={}: {}", start, e)
            break
    return pages

async def scrape_jobs(urls: list[str]) -> list[dict[str, Any]]:
    """Scrape LinkedIn job pages."""
    out = []
    for url in urls:
        html = await _fetch_rendered_html(url, ready_selector="script[type='application/ld+json']")
        out.append(parse_job_page(html))
    return out

async def scrape_articles(urls: list[str]) -> list[dict[str, Any]]:
    """Scrape LinkedIn articles (`/pulse/...`)."""
    out = []
    for url in urls:
        html = await _fetch_rendered_html(url, ready_selector="script[type='application/ld+json']")
        out.append(parse_article_page(html))
    return out

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
