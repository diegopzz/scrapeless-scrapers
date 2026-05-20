"""Allegro (allegro.pl) scraper using the Scrapeless SDK + Playwright over CDP.
function names and emitted field names match verbatim. Polish/Cyrillic glyphs
in titles, seller names, etc. are preserved as-is.

Allegro embeds state in two flavours of inline `<script>`:
  - `<script data-serialize-box-id="...">{"...": ...}</script>` — many small boxes (price, gallery, seller).
  - `<script>__listing_StoreState=...</script>` — full search listing payload.
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import quote_plus

from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "PL"
DEFAULT_SESSION_TTL = 240
HOME = "https://allegro.pl/"

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
    retries: int = 2,
    warmup: bool = True,
) -> str:
    """Allegro occasionally returns a 404/captcha shell when the proxy IP hits the
    target URL cold; warming up at the homepage first issues the cookies.
    """
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
                await page.set_extra_http_headers({"accept-language": "pl-PL,pl;q=0.9,en;q=0.5"})
                if warmup:
                    try:
                        await page.goto(HOME, wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(2500)
                    except Exception:
                        pass
                await page.goto(url, wait_until="domcontentloaded", timeout=45000, referer=HOME)
                if ready_selector:
                    try:
                        await page.wait_for_selector(ready_selector, timeout=20000)
                    except Exception as e:
                        logger.warning("wait_for_selector failed (continuing): {}", e)
                await page.wait_for_timeout(1500)
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
# Helpers — locate JSON in `data-serialize-box-id` and listing-state scripts
# ---------------------------------------------------------------------------

def _box_payload(sel: Selector, needle: str) -> dict[str, Any] | None:
    """Find the first `<script data-serialize-box-id>` containing `needle`."""
    for script in sel.xpath(
        "//script[@data-serialize-box-id and contains(text(), $needle)]",
        needle=needle,
    ).getall():
        try:
            return json.loads(script)
        except json.JSONDecodeError:
            continue
    return None

def _read_json_object(text: str, start: int) -> str | None:
    """Return the balanced JSON object starting at index `start` (must point at '{')."""
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _listing_state(sel: Selector) -> dict[str, Any] | None:
    """Locate the inline `"__listing_StoreState":{...}` JSON and balance braces.

    Allegro used to ship an assignment form (`__listing_StoreState = {...};`);
    newer pages embed it as a property of a larger JSON state object.
    """
    for script_text in sel.xpath(
        "//script[contains(text(), '__listing_StoreState')]/text()"
    ).getall():
        idx = script_text.find('"__listing_StoreState"')
        if idx == -1:
            continue
        colon = script_text.find(":", idx)
        if colon == -1:
            continue
        cursor = colon + 1
        while cursor < len(script_text) and script_text[cursor].isspace():
            cursor += 1
        if cursor >= len(script_text) or script_text[cursor] != "{":
            continue
        obj = _read_json_object(script_text, cursor)
        if obj is None:
            continue
        try:
            return json.loads(obj)
        except json.JSONDecodeError:
            continue
    return None


def _search_meta(sel: Selector) -> dict[str, Any] | None:
    """`searchMeta` can ship in a `data-serialize-box-id` payload or inline."""
    for raw in sel.xpath(
        "//script[@data-serialize-box-id and contains(text(), 'searchMeta')]/text()"
    ).getall():
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        meta = (
            data.get("props", {}).get("searchMeta")
            if isinstance(data.get("props"), dict)
            else data.get("searchMeta")
        )
        if isinstance(meta, dict):
            return meta
    # Fallback: scan inline scripts for `"searchMeta":{...}`.
    for script_text in sel.xpath("//script/text()").getall():
        idx = script_text.find('"searchMeta"')
        if idx == -1:
            continue
        colon = script_text.find(":", idx)
        if colon == -1:
            continue
        cursor = colon + 1
        while cursor < len(script_text) and script_text[cursor].isspace():
            cursor += 1
        if cursor >= len(script_text) or script_text[cursor] != "{":
            continue
        obj = _read_json_object(script_text, cursor)
        if obj is None:
            continue
        try:
            return json.loads(obj)
        except json.JSONDecodeError:
            continue
    return None

# ---------------------------------------------------------------------------
# Parsers — mirror the upstream reference's verbatim keys
# ---------------------------------------------------------------------------

def _normalise_title(title: Any) -> str:
    if isinstance(title, str):
        return title
    if isinstance(title, dict):
        return title.get("text") or ""
    return ""


def _normalise_price(price: Any) -> dict[str, Any] | None:
    """Listing elements now ship price as `{mainPrice: {amount, currency}}`."""
    if not isinstance(price, dict):
        return None
    main = price.get("mainPrice") if isinstance(price.get("mainPrice"), dict) else price
    if not isinstance(main, dict):
        return None
    amount = main.get("amount")
    currency = main.get("currency")
    if amount is None and currency is None:
        return None
    return {"amount": amount, "currency": currency}


def _first_photo(photos: Any) -> str | None:
    if not isinstance(photos, list) or not photos:
        return None
    p = photos[0]
    if isinstance(p, str):
        return p
    if isinstance(p, dict):
        return p.get("url") or p.get("medium") or p.get("original") or p.get("small")
    return None


def _decanonicalise_url(url: str | None) -> str:
    """Sponsored items wrap the real URL in /events/clicks?redirect=…"""
    from urllib.parse import urlparse, parse_qs, unquote
    if not url:
        return ""
    try:
        u = urlparse(url)
    except Exception:
        return url
    if u.path.startswith("/events/clicks"):
        params = parse_qs(u.query)
        redirect = params.get("redirect", [None])[0]
        if redirect:
            return unquote(redirect)
    return url


def parse_search(html: str) -> dict[str, Any]:
    sel = Selector(text=html)
    state = _listing_state(sel) or {}
    elements = (
        state.get("items", {}).get("elements", [])
        if isinstance(state.get("items"), dict)
        else []
    )
    products: list[dict[str, Any]] = []
    for el in elements:
        if not isinstance(el, dict):
            continue
        price = _normalise_price(el.get("price"))
        products.append({
            # `el.id` is the canonical product UUID; `el.offerId` is the per-listing numeric id.
            "product_id": el.get("productId") or el.get("product_id") or el.get("id") or "",
            "offer_id": el.get("offerId") or el.get("offer_id") or "",
            "title": _normalise_title(el.get("title")),
            "price": price,
            "currency": price.get("currency") if price else None,
            "url": _decanonicalise_url(el.get("url", "")),
            "image": _first_photo(el.get("photos")),
            "seller": el.get("seller"),
            "delivery_info": el.get("deliveryInfo") or el.get("delivery"),
        })
    meta = _search_meta(sel) or (state.get("searchMeta") if isinstance(state.get("searchMeta"), dict) else {})
    return {
        "products": products,
        "products_count": len(products),
        "total_pages": meta.get("lastAvailablePage") if isinstance(meta, dict) else None,
        "total_count": meta.get("totalCount") if isinstance(meta, dict) else None,
    }

def parse_product(html: str) -> dict[str, Any]:
    sel = Selector(text=html)
    price_box = _box_payload(sel, "formattedPrice") or {}
    # The price box wraps the actual price subtree under `.price`; emit just that.
    if isinstance(price_box, dict) and isinstance(price_box.get("price"), dict):
        price = price_box["price"]
    else:
        price = price_box
    gallery = _box_payload(sel, "galleryItems") or _box_payload(sel, "gallery") or {}
    seller = _box_payload(sel, "sellerName") or {}

    # Gallery payload now ships items under `galleryItems` (was `images`).
    items_list = (
        gallery.get("galleryItems") if isinstance(gallery, dict) and isinstance(gallery.get("galleryItems"), list)
        else (gallery.get("images") if isinstance(gallery, dict) and isinstance(gallery.get("images"), list) else [])
    )
    images: list[str] = []
    for img in items_list:
        if isinstance(img, str):
            images.append(img)
        elif isinstance(img, dict):
            url = img.get("original") or img.get("embeded") or img.get("url") or img.get("thumbnail")
            if url:
                images.append(url)

    rating = None
    rating_box = _box_payload(sel, "aggregateRating")
    if isinstance(rating_box, dict):
        agg = rating_box.get("aggregateRating")
        if isinstance(agg, dict) and agg.get("value") is not None:
            rating = str(agg["value"])
    if rating is None:
        for raw in sel.xpath(
            "//script[contains(text(), 'aggregateRating')]/text()"
        ).getall():
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            agg = data.get("aggregateRating") if isinstance(data, dict) else None
            if isinstance(agg, dict) and agg.get("ratingValue") is not None:
                rating = str(agg["ratingValue"])
                break

    title = (sel.css("h1::text").get() or "").strip()
    specifications: list[dict[str, str]] = []
    for row in sel.css("[data-role='product-parameters'] li, .product-parameters li"):
        name = (row.css("span:nth-of-type(1)::text").get() or "").strip()
        value = (row.css("span:nth-of-type(2)::text").get() or "").strip()
        if name:
            specifications.append({"name": name, "value": value})
    # Newer listings expose specs in `productParameters`/`parameters` payloads.
    if not specifications:
        params_box = _box_payload(sel, "productParameters") or _box_payload(sel, "parameters")
        groups: list[Any] = []
        if isinstance(params_box, dict):
            groups = params_box.get("groups") or params_box.get("parameters") or []
        if isinstance(groups, list):
            for group in groups:
                gp = group if isinstance(group, dict) else {}
                items = gp.get("parameters") if isinstance(gp.get("parameters"), list) else gp.get("items") if isinstance(gp.get("items"), list) else []
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    name = it.get("name") or it.get("label")
                    value = it.get("value")
                    if value is None and isinstance(it.get("values"), list):
                        value = ", ".join(str(v) for v in it["values"])
                    if name:
                        specifications.append({"name": str(name), "value": "" if value is None else str(value)})

    shipping_info = _box_payload(sel, "deliveryOptions") or _box_payload(sel, "shipping")

    smart_badge = bool(sel.css("[data-role='smart-badge'], [aria-label*='Smart']")) or "allegro smart!" in html.lower()

    return {
        "title": title,
        "price": price,
        "images": images,
        "shipping_info": shipping_info,
        "rating": rating,
        "specifications": specifications,
        "seller": seller,
        "reviews": [],
        "allegro_smart_badge": smart_badge,
    }

# ---------------------------------------------------------------------------
# Scrape functions
# ---------------------------------------------------------------------------

def _search_url(query: str, page: int) -> str:
    return f"https://allegro.pl/listing?string={quote_plus(query)}&p={page}"

async def scrape_search(
    query: str,
    max_pages: int = 3,
    scrape_all_pages: bool = False,
) -> dict[str, Any]:
    first_html = await _fetch_rendered_html(_search_url(query, 1), ready_selector="article")
    first = parse_search(first_html)
    products = list(first.get("products", []))
    total_pages = first.get("total_pages") or 1
    limit = total_pages if scrape_all_pages else min(max_pages, total_pages)
    pages_scraped = 1
    for p in range(2, limit + 1):
        try:
            html = await _fetch_rendered_html(_search_url(query, p), ready_selector="article")
            page_data = parse_search(html)
            products.extend(page_data.get("products", []))
            pages_scraped += 1
        except Exception as e:  # noqa: BLE001
            logger.warning("search page {} failed: {}", p, e)
            break
    return {
        "products": products,
        "scraped_pages": pages_scraped,
        "products_count": len(products),
        "total_pages": first.get("total_pages"),
        "total_count": first.get("total_count"),
    }

async def scrape_product(urls: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for url in urls:
        html = await _fetch_rendered_html(url, ready_selector="h1")
        out.append(parse_product(html))
    return out

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
