"""GooglePlay scraper using the official Scrapeless Python SDK + Playwright over CDP.

Target surface: ``https://play.google.com/store/apps/details?id=<package>``.
The page embeds a ``SoftwareApplication`` JSON-LD blob with the cleanest
representation of name/rating/description/icon. Install band, latest
update, screenshots and categories come from the rendered DOM.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import quote_plus

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 180
READY_SELECTOR = "script[type='application/ld+json']"


@dataclass
class App:
    id: str
    name: str
    url: str
    developer: str = ""
    rating: float | None = None
    rating_count: int | None = None
    price: str = ""
    installs: str = ""
    description: str = ""
    categories: list[str] = field(default_factory=list)
    latest_update: str = ""
    screenshots: list[str] = field(default_factory=list)
    icon: str = ""


def _client() -> Scrapeless:
    if not os.environ.get("SCRAPELESS_API_KEY") and not os.environ.get("SCRAPELESS_KEY"):
        raise RuntimeError(
            "SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com"
        )
    if not os.environ.get("SCRAPELESS_API_KEY") and os.environ.get("SCRAPELESS_KEY"):
        os.environ["SCRAPELESS_API_KEY"] = os.environ["SCRAPELESS_KEY"]
    return Scrapeless()


async def _fetch_rendered_html(
    url: str, ready_selector: str = READY_SELECTOR, *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY, retries: int = 1,
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
                page = await browser.new_page(viewport={"width": 1366, "height": 900})
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                try:
                    await page.wait_for_selector(ready_selector, timeout=15000)
                except Exception as e:
                    logger.warning("ready selector not seen (continuing): {}", e)
                await asyncio.sleep(1.5)
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
# Scrape functions
# ---------------------------------------------------------------------------


async def scrape_app(package_id: str) -> App:
    url = f"https://play.google.com/store/apps/details?id={quote_plus(package_id)}&hl=en_US&gl=US"
    html = await _fetch_rendered_html(url)
    return parse_app(html, package_id, url)


async def scrape_apps(package_ids: list[str]) -> list[App]:
    return [await scrape_app(p) for p in package_ids]


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def _find_software_application_ld(sel: Selector) -> dict | None:
    for raw in sel.css("script[type='application/ld+json']::text").getall():
        raw = (raw or "").strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        items = parsed if isinstance(parsed, list) else [parsed]
        for obj in items:
            if not isinstance(obj, dict):
                continue
            t = obj.get("@type", "")
            if isinstance(t, str) and "application" in t.lower():
                return obj
            if isinstance(t, list) and any("application" in str(x).lower() for x in t):
                return obj
    return None


def _read_install_band(sel: Selector) -> str:
    for node in sel.css("div, span"):
        txt = ("".join(node.css("::text").getall())).strip()
        if txt == "Downloads":
            parent = node.xpath("..")
            if parent:
                first_child = parent[0].xpath("./*[1]")
                if first_child:
                    v = "".join(first_child[0].css("*::text").getall()).strip()
                    if v and re.search(r"[\d+]", v):
                        return f"{v} Downloads"
    body_text = " ".join(sel.css("body *::text").getall())
    m = re.search(r"(\d[\d,]*\+)\s+(downloads|installs)", body_text, re.IGNORECASE)
    return f"{m.group(1)} {m.group(2)}" if m else ""


def _read_latest_update(sel: Selector) -> str:
    for node in sel.css("div, span"):
        txt = ("".join(node.css("::text").getall())).strip()
        if re.match(r"^Updated(?: on)?$", txt, re.IGNORECASE):
            sib = node.xpath("following-sibling::*[1]")
            if sib:
                v = "".join(sib[0].css("*::text").getall()).strip()
                if v:
                    return v
    return sel.css("[itemprop='datePublished']::attr(content)").get(default="")


def _read_categories(sel: Selector, ld: dict | None) -> list[str]:
    cats: list[str] = []
    if ld:
        cat = ld.get("applicationCategory")
        if isinstance(cat, str):
            cats.append(cat.strip())
        elif isinstance(cat, list):
            cats.extend(str(c).strip() for c in cat)
    for a in sel.css("a[href*='/store/apps/category/']"):
        t = ("".join(a.css("*::text").getall())).strip()
        if t and not re.match(r"^(view all|see more)$", t, re.IGNORECASE):
            cats.append(t)
    out: list[str] = []
    seen: set[str] = set()
    for c in cats:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _read_screenshots(sel: Selector) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for img in sel.css("img[src*='play-lh.googleusercontent.com']"):
        src = (img.attrib.get("src", "") or "").split("=")[0]
        if not src or src in seen:
            continue
        seen.add(src)
        out.append(src)
    return out[1:21]


def _read_price(sel: Selector, ld: dict | None) -> str:
    offers = (ld or {}).get("offers") if ld else None
    offer_list = offers if isinstance(offers, list) else ([offers] if offers else [])
    for o in offer_list:
        if not isinstance(o, dict):
            continue
        price = o.get("price")
        currency = o.get("priceCurrency")
        if price in ("0", 0, "0.00"):
            return "Free"
        if price and currency:
            return f"{currency} {price}"
        if price:
            return str(price)
    btn = sel.css("button[aria-label^='Install']::text").get(default="").strip()
    return btn


def _read_developer(sel: Selector) -> str:
    return (
        "".join(sel.css(
            "a[href*='/store/apps/dev']::text, a[href*='/store/apps/developer']::text"
        ).getall()).strip()
    )


def _read_meta_title(sel: Selector) -> str:
    return (
        sel.css("meta[property='og:title']::attr(content)").get()
        or sel.css("meta[name='twitter:title']::attr(content)").get()
        or sel.css("title::text").get(default="").strip()
    ) or ""


def _read_meta_description(sel: Selector) -> str:
    return (
        sel.css("meta[name='description']::attr(content)").get()
        or sel.css("meta[property='og:description']::attr(content)").get()
        or ""
    )


def _read_icon(sel: Selector) -> str:
    return (
        sel.css("meta[property='og:image']::attr(content)").get()
        or sel.css("img[alt='Icon image']::attr(src)").get()
        or ""
    )


def _to_float(v) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _to_int(v) -> int | None:
    try:
        return int(str(v)) if v is not None else None
    except (TypeError, ValueError):
        return None


def parse_app(html: str, package_id: str, url: str) -> App:
    sel = Selector(text=html)
    ld = _find_software_application_ld(sel) or {}
    rating = (ld.get("aggregateRating") or {}) if isinstance(ld.get("aggregateRating"), dict) else {}
    author = ld.get("author")
    developer = ""
    if isinstance(author, dict):
        developer = str(author.get("name", "")).strip()
    elif isinstance(author, str):
        developer = author.strip()
    if not developer:
        developer = _read_developer(sel)

    name = str(ld.get("name") or _read_meta_title(sel) or "").strip()
    description = str(ld.get("description") or _read_meta_description(sel) or "").strip()
    icon_raw = ld.get("image") or ld.get("logo") or _read_icon(sel) or ""
    icon = str(icon_raw).strip()

    return App(
        id=package_id,
        name=name,
        url=url,
        developer=developer,
        rating=_to_float(rating.get("ratingValue")),
        rating_count=_to_int(rating.get("ratingCount") or rating.get("reviewCount")),
        price=_read_price(sel, ld),
        installs=_read_install_band(sel),
        description=description,
        categories=_read_categories(sel, ld),
        latest_update=_read_latest_update(sel),
        screenshots=_read_screenshots(sel),
        icon=icon,
    )


def to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
