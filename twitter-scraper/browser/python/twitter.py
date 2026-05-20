"""Twitter (X.com) scraper using the official Scrapeless Python SDK + Playwright over CDP.
function names and emitted field names match verbatim, so downstream code can
Public data only. Tweet detail pages and public profiles render fine without
auth; replies / search / following lists sit behind the login wall and are out
of scope (the upstream reference itself doesn't cover them either).

Under the hood:
- `client.browser.create()` mints a cloud browser session (CDP WS endpoint).
- Playwright connects, navigates to the page, and listens for the background
  `TweetResultByRestId` / `UserTweets` GraphQL XHRs the SPA fires.
- jmespath reduces the verbose payloads to the upstream reference's exact field set.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Optional

import jmespath
from loguru import logger
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

async def _scrape_twitter_app(
    url: str,
    *,
    wait_for_selector: Optional[str] = None,
    xhr_url_substring: str,
    _retries: int = 0,
) -> List[Dict]:
    """Load a Twitter page, scroll, and return matching XHR JSON bodies."""
    if not _retries:
        logger.info("scraping {}", url)
    else:
        logger.info("retrying {}/2 {}", _retries, url)

    client = _client()
    session = client.browser.create(
        ICreateBrowser(proxy_country=DEFAULT_PROXY_COUNTRY, session_ttl=DEFAULT_SESSION_TTL)
    )
    captured: List[Dict] = []
    html = ""
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
        try:
            page = await browser.new_page()

            async def on_response(resp):
                try:
                    if xhr_url_substring in resp.url:
                        body = await resp.json()
                        captured.append(body)
                except Exception:
                    pass

            page.on("response", on_response)
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            if wait_for_selector:
                try:
                    await page.wait_for_selector(wait_for_selector, timeout=15000)
                except Exception as e:
                    logger.warning("wait_for_selector failed: {}", e)
            # mimic the upstream reference's auto_scroll
            for _ in range(5):
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await asyncio.sleep(1.0)
            html = await page.content()
        finally:
            try:
                await browser.close()
            except Exception:
                pass

    if "Something went wrong, but" in html and _retries < 2:
        return await _scrape_twitter_app(
            url,
            wait_for_selector=wait_for_selector,
            xhr_url_substring=xhr_url_substring,
            _retries=_retries + 1,
        )
    return captured

def parse_tweet(data: Dict) -> Dict:
    """Parse X.com (Twitter) tweet JSON dataset for the most important fields"""
    result = jmespath.search(
        """{
        created_at: legacy.created_at,
        attached_urls: legacy.entities.urls[].expanded_url,
        attached_urls2: legacy.entities.url.urls[].expanded_url,
        attached_media: legacy.entities.media[].media_url_https,
        tagged_users: legacy.entities.user_mentions[].screen_name,
        tagged_hashtags: legacy.entities.hashtags[].text,
        favorite_count: legacy.favorite_count,
        bookmark_count: legacy.bookmark_count,
        quote_count: legacy.quote_count,
        reply_count: legacy.reply_count,
        retweet_count: legacy.retweet_count,
        quote_count: legacy.quote_count,
        text: legacy.full_text,
        is_quote: legacy.is_quote_status,
        is_retweet: legacy.retweeted,
        language: legacy.lang,
        user_id: legacy.user_id_str,
        id: legacy.id_str,
        conversation_id: legacy.conversation_id_str,
        source: source,
        views: views.count
    }""",
        data,
    )
    result["poll"] = {}
    poll_data = jmespath.search("card.legacy.binding_values", data) or []
    for poll_entry in poll_data:
        key, value = poll_entry["key"], poll_entry["value"]
        if "choice" in key:
            result["poll"][key] = value["string_value"]
        elif "end_datetime" in key:
            result["poll"]["end"] = value["string_value"]
        elif "last_updated_datetime" in key:
            result["poll"]["updated"] = value["string_value"]
        elif "counts_are_final" in key:
            result["poll"]["ended"] = value["boolean_value"]
        elif "duration_minutes" in key:
            result["poll"]["duration"] = value["string_value"]
    user_data = jmespath.search("core.user_results.result", data)
    if user_data:
        result["user"] = parse_profile(user_data)
    return result

async def scrape_tweet(url: str) -> Dict:
    """
    Scrape a single tweet page for Tweet thread e.g.:
    https://x.com/robinhanson/status/1872047986873885082
    """
    bodies = await _scrape_twitter_app(
        url,
        wait_for_selector="[data-testid='tweet']",
        xhr_url_substring="TweetResultByRestId",
    )
    for body in bodies:
        try:
            return parse_tweet(body["data"]["tweetResult"]["result"])
        except (KeyError, TypeError):
            continue
    raise RuntimeError("Failed to scrape tweet — no TweetResultByRestId XHR captured")

def parse_profile(data: Dict) -> Dict:
    """parse X.com (Twitter) user profile JSON dataset as a flat structure"""
    return {
        "id": data["id"],
        "rest_id": data["rest_id"],
        "verified": data["is_blue_verified"],
        **data["legacy"],
    }

async def scrape_profile(url: str) -> Dict:
    """
    Scrapes X.com (Twitter) user profile page e.g.:
    https://x.com/jack
    returns user data and latest tweets
    """
    bodies = await _scrape_twitter_app(
        url,
        wait_for_selector="[data-testid='primaryColumn']",
        xhr_url_substring="UserTweets",
    )
    for body in bodies:
        try:
            instructions = body["data"]["user"]["result"]["timeline"]["timeline"]["instructions"]
        except (KeyError, TypeError):
            continue
        for instruction in instructions:
            for entry in instruction.get("entries", []):
                item = entry.get("content", {}).get("itemContent", {})
                if item.get("__typename") != "TimelineTweet":
                    continue
                user_result = item["tweet_results"]["result"]["core"]["user_results"]["result"]
                if user_result.get("rest_id"):
                    return parse_profile(user_result)
    raise RuntimeError("Failed to scrape user profile - no matching user data background requests")

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
