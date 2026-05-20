"""Crunchbase scraper using the official Scrapeless Python SDK + Playwright over CDP.
function names and emitted field names match verbatim.

Crunchbase is an Angular app. State arrives as JSON inside
`<script id="ng-state">` (newer pages) or `<script id="client-app-state">`
(legacy). Both targets parse that embedded payload — the rendered DOM is
unstable.
"""

from __future__ import annotations

import json
import os
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
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                try:
                    await page.wait_for_selector(ready_selector, timeout=20000)
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
# Angular state extraction
# ---------------------------------------------------------------------------

def _parse_ng_state(html: str) -> Dict[str, Any]:
    """Extract the JSON blob from `script#ng-state` or `script#client-app-state`."""
    sel = Selector(text=html)
    raw = sel.xpath("//script[@id='ng-state']/text()").get()
    if not raw:
        raw = sel.xpath("//script[@id='client-app-state']/text()").get()
    if not raw:
        raise RuntimeError("could not locate Angular state script (ng-state / client-app-state)")
    return json.loads(raw)

def _walk_http_state(state: Dict[str, Any], key_substr: str) -> List[Dict[str, Any]]:
    """Crunchbase keeps API responses in an HttpState cache. Find all entries whose
    cache key contains `key_substr` and return their parsed bodies."""
    http_state = state.get("HttpState") or {}
    matches: List[Dict[str, Any]] = []
    for cache_key, payload in http_state.items():
        if key_substr in cache_key and isinstance(payload, dict):
            body = payload.get("body") or payload.get("data") or payload
            if isinstance(body, dict):
                matches.append(body)
    return matches

# ---------------------------------------------------------------------------
# Field reducers — mirror the upstream reference's JMESPath-style reductions
# ---------------------------------------------------------------------------

_ORG_FIELDS = (
    "id name logo description linkedin facebook twitter email phone website "
    "ipo_status rank_org_company semrush_global_rank semrush_visits_latest_month "
    "semrush_id categories legal_name operating_status last_funding_type "
    "founded_on location_groups trademarks trademark_popular_class patents "
    "patent_popular_category investments investors acquisitions contacts "
    "funding_total_usd stock_symbol exits similar_orgs current_positions "
    "investors_lead investments_lead funding_rounds event_appearances advisors "
    "buildwith_tech_used timeline events similar"
).split()

def _reduce_org(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Pick the """
    if not isinstance(raw, dict):
        return {}
    # Crunchbase wraps the org under `properties` or `cards` depending on the route.
    candidate = raw.get("properties") or raw.get("cards") or raw
    if not isinstance(candidate, dict):
        return {}
    flat: Dict[str, Any] = {}
    # Hoist nested `cards` (sections) up to the top.
    cards = raw.get("cards") if isinstance(raw.get("cards"), dict) else {}
    for section in cards.values():
        if isinstance(section, dict):
            flat.update(section)
    # Properties section takes precedence.
    props = raw.get("properties") if isinstance(raw.get("properties"), dict) else {}
    flat.update(props)
    # Reduce to the canonical key set.
    return {k: flat.get(k) for k in _ORG_FIELDS if k in flat}

def _reduce_employees(employees_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = jmespath.search("entities[*].properties || entities || items[*] || []", employees_payload)
    out: List[Dict[str, Any]] = []
    if not isinstance(items, list):
        return out
    for item in items:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "name": item.get("name") or item.get("first_name", "") + " " + item.get("last_name", ""),
                "linkedin": item.get("linkedin") or item.get("linkedin_url"),
                "job_levels": item.get("job_levels"),
                "job_departments": item.get("job_departments"),
            }
        )
    return out

_PERSON_FIELDS = (
    "name title description type gender location_groups location current_jobs "
    "past_jobs linkedin twitter facebook current_advisor_jobs founded_orgs "
    "portfolio_orgs rank_principal_investor education timeline investments exits"
).split()

def _reduce_person(raw: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    candidate = raw.get("properties") or raw
    cards = raw.get("cards") if isinstance(raw.get("cards"), dict) else {}
    flat: Dict[str, Any] = {}
    for section in cards.values():
        if isinstance(section, dict):
            flat.update(section)
    if isinstance(candidate, dict):
        flat.update(candidate)
    return {k: flat.get(k) for k in _PERSON_FIELDS if k in flat}

# ---------------------------------------------------------------------------
# Scrape functions — mirror the upstream reference's exports verbatim
# ---------------------------------------------------------------------------

async def scrape_company(url: str) -> Dict[str, Any]:
    """Scrape a Crunchbase organization page; return `{organization, employees}`."""
    html = await _fetch_rendered_html(url, ready_selector="script#ng-state, script#client-app-state")
    state = _parse_ng_state(html)
    org_payloads = _walk_http_state(state, "entities/organizations/")
    organization = _reduce_org(org_payloads[0]) if org_payloads else {}
    employees_payloads = _walk_http_state(state, "/data/searches/contacts")
    employees = _reduce_employees(employees_payloads[0]) if employees_payloads else []
    return {"organization": organization, "employees": employees}

async def scrape_person(url: str) -> Dict[str, Any]:
    """Scrape a Crunchbase /person/<slug> page."""
    html = await _fetch_rendered_html(url, ready_selector="script#ng-state, script#client-app-state")
    state = _parse_ng_state(html)
    person_payloads = _walk_http_state(state, "data/entities")
    return _reduce_person(person_payloads[0]) if person_payloads else {}

def to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
