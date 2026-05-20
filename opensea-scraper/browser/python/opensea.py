"""OpenSea scraper using the official Scrapeless Python SDK + Playwright over CDP.

OpenSea ships its page data inside Next.js + urql hydration blobs of the
form:

    (window[Symbol.for("urql_transport")] ??= []).push({"rehydrate": {...}})

The scraper renders the page in Scrapeless's Scraping Browser, harvests
every ``urql_transport`` push, and folds the GraphQL responses into either
a ``Collection`` or an ``Asset`` dataclass.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable
from urllib.parse import quote

from loguru import logger
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 240


@dataclass
class Collection:
    slug: str
    name: str
    url: str
    description: str = ""
    chain: str = ""
    total_supply: int | None = None
    floor_price: float | None = None
    floor_currency: str = ""
    floor_price_usd: float | None = None
    volume_native: float | None = None
    volume_usd: float | None = None
    image: str = ""


@dataclass
class Trait:
    trait_type: str
    value: str


@dataclass
class Asset:
    chain: str
    contract: str
    token_id: str
    name: str
    url: str
    collection_slug: str = ""
    collection_name: str = ""
    owner: str = ""
    owner_address: str = ""
    rarity_rank: int | None = None
    image: str = ""
    traits: list[Trait] = field(default_factory=list)
    best_offer: float | None = None
    best_offer_currency: str = ""


def _client() -> Scrapeless:
    if not os.environ.get("SCRAPELESS_API_KEY") and not os.environ.get("SCRAPELESS_KEY"):
        raise RuntimeError(
            "SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com"
        )
    if not os.environ.get("SCRAPELESS_API_KEY") and os.environ.get("SCRAPELESS_KEY"):
        os.environ["SCRAPELESS_API_KEY"] = os.environ["SCRAPELESS_KEY"]
    return Scrapeless()


async def _fetch_rendered_html(
    url: str, *, proxy_country: str = DEFAULT_PROXY_COUNTRY, retries: int = 1,
    settle_seconds: float = 6.0,
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
                page = await browser.new_page(viewport={"width": 1440, "height": 900})
                await page.goto(url, wait_until="networkidle", timeout=60000)
                await asyncio.sleep(settle_seconds)
                html = await page.content()
                if html and "urql_transport" in html:
                    return html
                last_error = RuntimeError("no urql_transport blob in HTML")
            except Exception as e:  # noqa: BLE001
                last_error = e
                logger.warning("attempt {} failed: {}", attempt + 1, e)
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass
        if attempt < retries:
            await asyncio.sleep(3)
    raise RuntimeError(f"giving up after {retries + 1} attempts: {last_error}")


# ---------------------------------------------------------------------------
# Scrape functions
# ---------------------------------------------------------------------------


async def scrape_collection(slug: str) -> Collection:
    url = f"https://opensea.io/collection/{quote(slug, safe='')}"
    html = await _fetch_rendered_html(url)
    return parse_collection(html, slug, url)


async def scrape_asset(chain: str, contract: str, token_id: str) -> Asset:
    url = f"https://opensea.io/item/{quote(chain, safe='')}/{contract}/{quote(str(token_id), safe='')}"
    html = await _fetch_rendered_html(url)
    return parse_asset(html, chain, contract, str(token_id), url)


# ---------------------------------------------------------------------------
# Hydration extraction
# ---------------------------------------------------------------------------


_NEEDLE = 'Symbol.for("urql_transport")'


def extract_urql_payloads(html: str) -> list[dict]:
    """Every payload arrives in a ``<script>`` body containing::

        (window[Symbol.for("urql_transport")] ??= []).push({...})

    We scan for the ``push(`` call, then balance braces to capture the JSON.
    """
    out: list[dict] = []
    cursor = 0
    while True:
        idx = html.find(_NEEDLE, cursor)
        if idx < 0:
            break
        open_idx = html.find("push(", idx)
        if open_idx < 0:
            break
        start = open_idx + len("push(")
        slice_ = _balanced_json(html, start)
        if slice_:
            try:
                out.append(json.loads(slice_))
            except json.JSONDecodeError:
                pass
        cursor = open_idx + 5
    return out


def _balanced_json(html: str, start_idx: int) -> str | None:
    i = start_idx
    while i < len(html) and html[i] != "{":
        i += 1
    if i >= len(html):
        return None
    start = i
    depth = 0
    in_str: str | None = None
    while i < len(html):
        ch = html[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == in_str:
                in_str = None
        elif ch in ('"', "'"):
            in_str = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return html[start:i + 1]
        i += 1
    return None


def _walk(obj: Any) -> Iterable[Any]:
    if obj is None or not isinstance(obj, (dict, list)):
        return
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    else:
        for v in obj:
            yield from _walk(v)


def _find_first(obj: Any, predicate) -> dict | None:
    for node in _walk(obj):
        if predicate(node):
            return node
    return None


def _find_all(obj: Any, predicate) -> list[dict]:
    return [node for node in _walk(obj) if predicate(node)]


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def _num_or_none(v) -> float | None:
    if v is None:
        return None
    try:
        n = float(v)
        return n if n == n else None  # NaN guard
    except (TypeError, ValueError):
        return None


def parse_collection(html: str, slug: str, url: str) -> Collection:
    payloads = extract_urql_payloads(html)

    merged: dict[str, Any] = {}
    for p in payloads:
        for node in _find_all(p, lambda n: isinstance(n, dict) and n.get("__typename") == "Collection" and n.get("slug") == slug):
            for k, v in node.items():
                if v is not None and merged.get(k) is None:
                    merged[k] = v

    floor = (merged.get("floorPrice") or {})
    floor_pp = floor.get("pricePerItem") if isinstance(floor.get("pricePerItem"), dict) else floor
    floor_token = (floor_pp or {}).get("token") or (floor_pp or {}).get("tokenPrice") or {}
    floor_price = floor_token.get("unit") if isinstance(floor_token, dict) else None
    floor_currency = floor_token.get("symbol", "") if isinstance(floor_token, dict) else ""
    floor_price_usd = (floor_pp or {}).get("usd") if isinstance(floor_pp, dict) else None

    chain = ""
    if isinstance(merged.get("chain"), dict):
        chain = merged["chain"].get("identifier", "")
    elif isinstance(merged.get("contracts"), list) and merged["contracts"]:
        chain = (merged["contracts"][0].get("chain") or {}).get("identifier", "")

    volume_native = None
    volume_usd = None
    for p in payloads:
        vol_node = _find_first(p, lambda n: isinstance(n, dict) and isinstance(n.get("volume"), dict))
        if not vol_node:
            continue
        vol = vol_node["volume"]
        native = vol.get("native") if isinstance(vol.get("native"), dict) else None
        if native and "unit" in native:
            volume_native = native["unit"]
        elif "unit" in vol:
            volume_native = vol["unit"]
        if "usd" in vol:
            volume_usd = vol["usd"]
        if volume_native is not None:
            break

    total_supply = merged.get("totalSupply")
    if total_supply is None:
        best = 0
        for p in payloads:
            for node in _walk(p):
                if isinstance(node, dict) and isinstance(node.get("totalSupply"), int) and node["totalSupply"] > best:
                    best = node["totalSupply"]
        if best > 1:
            total_supply = best

    overview = merged.get("overview") or {}
    modules = overview.get("modules") if isinstance(overview, dict) else None
    name = ""
    description = ""
    image = ""
    if isinstance(modules, list):
        for m in modules:
            if isinstance(m, dict):
                if not name and m.get("title"):
                    name = str(m["title"]).strip()
                if not description and m.get("description"):
                    description = str(m["description"]).strip()
                if not image and isinstance(m.get("media"), list) and m["media"]:
                    img = m["media"][0].get("imageUrl") if isinstance(m["media"][0], dict) else None
                    if img:
                        image = img
    if not name:
        name = str(merged.get("name") or slug)
    if not description:
        description = str(merged.get("description") or "")
    if not image:
        image = str(merged.get("imageUrl") or "")

    return Collection(
        slug=slug,
        name=name.strip(),
        url=url,
        description=description.strip(),
        chain=chain or "",
        total_supply=int(total_supply) if isinstance(total_supply, int) else None,
        floor_price=_num_or_none(floor_price),
        floor_currency=str(floor_currency or ""),
        floor_price_usd=_num_or_none(floor_price_usd),
        volume_native=_num_or_none(volume_native),
        volume_usd=_num_or_none(volume_usd),
        image=image,
    )


def parse_asset(html: str, chain: str, contract: str, token_id: str, url: str) -> Asset:
    payloads = extract_urql_payloads(html)

    item: dict | None = None
    for p in payloads:
        node = _find_first(p, lambda n: isinstance(n, dict) and n.get("__typename") == "Item"
                           and str(n.get("tokenId")) == str(token_id))
        if node and (item is None or len(node) > len(item)):
            item = node
    if item is None:
        for p in payloads:
            node = _find_first(p, lambda n: isinstance(n, dict) and n.get("__typename") == "Item")
            if node:
                item = node
                break

    if item is None:
        return Asset(chain=chain, contract=contract, token_id=str(token_id), name="", url=url)

    attrs = item.get("attributes") if isinstance(item.get("attributes"), list) else []
    traits = [
        Trait(
            trait_type=str(a.get("traitType") or a.get("trait_type") or "").strip(),
            value=str(a.get("value") or "").strip(),
        )
        for a in attrs if isinstance(a, dict)
    ]

    best_offer = item.get("bestOffer") or {}
    best_pp = best_offer.get("pricePerItem") if isinstance(best_offer.get("pricePerItem"), dict) else best_offer
    offer_token = (best_pp or {}).get("token") or {}

    chain_id = (item.get("chain") or {}).get("identifier") if isinstance(item.get("chain"), dict) else None

    return Asset(
        chain=str(chain_id or chain),
        contract=contract,
        token_id=str(item.get("tokenId") or token_id),
        name=str(item.get("name") or "").strip(),
        url=url,
        collection_slug=str((item.get("collection") or {}).get("slug") or ""),
        collection_name=str((item.get("collection") or {}).get("name") or ""),
        owner=str((item.get("owner") or {}).get("displayName") or ""),
        owner_address=str((item.get("owner") or {}).get("address") or ""),
        rarity_rank=int((item.get("rarity") or {}).get("rank")) if isinstance((item.get("rarity") or {}).get("rank"), int) else None,
        image=str(item.get("imageUrl") or item.get("originalImageUrl") or ""),
        traits=traits,
        best_offer=_num_or_none(offer_token.get("unit") if isinstance(offer_token, dict) else None),
        best_offer_currency=str(offer_token.get("symbol", "") if isinstance(offer_token, dict) else ""),
    )


def to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
