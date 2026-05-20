"""Instagram scraper using the official Scrapeless Python SDK + Playwright over CDP.
Public data only. Anything behind Instagram's login wall (private profiles,
DMs, full comment threads on certain posts) is out of scope — match the upstream reference's
own scope. Under the hood:

- `client.browser.create()` mints a cloud browser session (CDP WS endpoint).
- Playwright connects over CDP, then calls Instagram's public GraphQL +
  `i.instagram.com` JSON endpoints from inside the browser context via
  `page.evaluate(fetch(...))` so requests carry the right session cookies and
  `x-ig-app-id` header.
- jmespath reduces the verbose payloads to the same field names the upstream reference emits.
"""

from __future__ import annotations

import json
import os
from typing import Any, AsyncIterator, Dict, Optional
from urllib.parse import urlencode

import jmespath
from loguru import logger
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "CA"  # the upstream reference default; change for relevant results
DEFAULT_SESSION_TTL = 180

INSTAGRAM_APP_ID = "936619743392459"
INSTAGRAM_DOCUMENT_ID = "8845758582119845"
INSTAGRAM_ACCOUNT_DOCUMENT_ID = "9310670392322965"
INSTAGRAM_COMMENTS_DOC_ID = "26248690958161038"

def _client() -> Scrapeless:
    if not os.environ.get("SCRAPELESS_API_KEY") and not os.environ.get("SCRAPELESS_KEY"):
        raise RuntimeError(
            "SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com"
        )
    if not os.environ.get("SCRAPELESS_API_KEY") and os.environ.get("SCRAPELESS_KEY"):
        os.environ["SCRAPELESS_API_KEY"] = os.environ["SCRAPELESS_KEY"]
    return Scrapeless()

async def _new_session(proxy_country: str = DEFAULT_PROXY_COUNTRY):
    """Mint a Scrapeless browser session and return (playwright, browser, page)."""
    client = _client()
    session = client.browser.create(
        ICreateBrowser(proxy_country=proxy_country, session_ttl=DEFAULT_SESSION_TTL)
    )
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
    page = await browser.new_page()
    # Warm cookies + UA by hitting the homepage first.
    await page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=30000)
    return pw, browser, page

async def _fetch_json_in_browser(
    page,
    url: str,
    method: str = "GET",
    body: str | None = None,
    extra_headers: Dict[str, str] | None = None,
) -> Any:
    """Run fetch() inside the live browser context so cookies + CSRF are honored."""
    js = """
    async ({url, method, body, headers}) => {
        const res = await fetch(url, {
            method,
            body: body || undefined,
            headers: headers || {},
            credentials: 'include',
        });
        const text = await res.text();
        return { status: res.status, text };
    }
    """
    headers = {"x-ig-app-id": INSTAGRAM_APP_ID}
    if extra_headers:
        headers.update(extra_headers)
    result = await page.evaluate(js, {"url": url, "method": method, "body": body, "headers": headers})
    text = result.get("text") or ""
    if text.startswith("for (;;);"):
        text = text[len("for (;;);"):]
    return json.loads(text)

# ---------------------------------------------------------------------------
# Parsers — verbatim mirror of the upstream reference's jmespath projections.
# ---------------------------------------------------------------------------

def parse_user(data: Dict) -> Dict:
    """Reduce the user data to the relevant fields"""
    logger.debug("parsing user data {}", data.get("username"))
    result = jmespath.search(
        """{
        name: full_name,
        username: username,
        id: id,
        category: category_name,
        business_category: business_category_name,
        phone: business_phone_number,
        email: business_email,
        bio: biography,
        bio_links: bio_links[].url,
        homepage: external_url,
        followers: edge_followed_by.count,
        follows: edge_follow.count,
        facebook_id: fbid,
        is_private: is_private,
        is_verified: is_verified,
        profile_image: profile_pic_url_hd,
        video_count: edge_felix_video_timeline.count,
        videos: edge_felix_video_timeline.edges[].node.{
            id: id,
            title: title,
            shortcode: shortcode,
            thumb: display_url,
            url: video_url,
            views: video_view_count,
            tagged: edge_media_to_tagged_user.edges[].node.user.username,
            captions: edge_media_to_caption.edges[].node.text,
            comments_count: edge_media_to_comment.count,
            comments_disabled: comments_disabled,
            taken_at: taken_at_timestamp,
            likes: edge_liked_by.count,
            location: location.name,
            duration: video_duration
        },
        image_count: edge_owner_to_timeline_media.count,
        images: edge_felix_video_timeline.edges[].node.{
            id: id,
            title: title,
            shortcode: shortcode,
            src: display_url,
            url: video_url,
            views: video_view_count,
            tagged: edge_media_to_tagged_user.edges[].node.user.username,
            captions: edge_media_to_caption.edges[].node.text,
            comments_count: edge_media_to_comment.count,
            comments_disabled: comments_disabled,
            taken_at: taken_at_timestamp,
            likes: edge_liked_by.count,
            location: location.name,
            accesibility_caption: accessibility_caption,
            duration: video_duration
        },
        saved_count: edge_saved_media.count,
        collections_count: edge_saved_media.count,
        related_profiles: edge_related_profiles.edges[].node.username
    }""",
        data,
    )
    return result

def parse_comments(data: Dict) -> Dict:
    """Parse the comments data from the post dataset"""
    if "edge_media_to_comment" in data:
        return jmespath.search(
            """{
                comments_count: edge_media_to_comment.count,
                comments_disabled: comments_disabled,
                comments_next_page: edge_media_to_comment.page_info.end_cursor,
                comments: edge_media_to_comment.edges[].node.{
                    id: id,
                    text: text,
                    created_at: created_at,
                    owner_id: owner.id,
                    owner: owner.username,
                    owner_verified: owner.is_verified,
                    viewer_has_liked: viewer_has_liked
                }
            }""",
            data,
        )
    return jmespath.search(
        """{
            comments_count: edge_media_to_parent_comment.count,
            comments_disabled: comments_disabled,
            comments_next_page: edge_media_to_parent_comment.page_info.end_cursor,
            comments: edge_media_to_parent_comment.edges[].node.{
                id: id,
                text: text,
                created_at: created_at,
                owner: owner.username,
                owner_verified: owner.is_verified,
                viewer_has_liked: viewer_has_liked,
                likes: edge_liked_by.count
            }
        }""",
        data,
    )

def parse_post(data: Dict) -> Dict:
    """Reduce post dataset to the most important fields"""
    logger.debug("parsing post data {}", data.get("shortcode"))
    result = jmespath.search(
        """{
        id: id,
        shortcode: shortcode,
        dimensions: dimensions,
        src: display_url,
        thumbnail_src: thumbnail_src,
        media_preview: media_preview,
        video_url: video_url,
        views: video_view_count,
        likes: edge_media_preview_like.count,
        location: location.name,
        taken_at: taken_at_timestamp,
        related: edge_web_media_to_related_media.edges[].node.shortcode,
        type: product_type,
        video_duration: video_duration,
        music: clips_music_attribution_info,
        is_video: is_video,
        tagged_users: edge_media_to_tagged_user.edges[].node.user.username,
        captions: edge_media_to_caption.edges[].node.text,
        related_profiles: edge_related_profiles.edges[].node.username
    }""",
        data,
    )
    comments_data = parse_comments(data)
    if comments_data:
        result.update(comments_data)
    return result

def parse_user_posts(data: Dict) -> Dict:
    """Reduce users posts' dataset to the most important fields"""
    logger.debug("parsing post data {}", data.get("code"))
    return jmespath.search(
        """{
        id: id,
        shortcode: code,
        caption: caption,
        taken_at: taken_at,
        video_versions: video_versions,
        image_versions2: image_versions2,
        original_height: original_height,
        original_width: original_width,
        link: link,
        title: title,
        comment_count: comment_count,
        top_likers: top_likers,
        like_count: like_count,
        usertags: usertags,
        clips_metadata: clips_metadata,
        comments: comments
    }""",
        data,
    )

def parse_post_comment(data: Dict) -> Dict:
    """Reduce post comment dataset to the most important fields"""
    logger.debug("parsing comment data {}", data.get("pk"))
    return jmespath.search(
        """{
        id: pk,
        text: text,
        created_at: created_at,
        owner: user.username,
        owner_id: user.id,
        owner_verified: user.is_verified,
        owner_profile_pic: user.profile_pic_url,
        likes: comment_like_count,
        replies_count: child_comment_count,
        parent_comment_id: parent_comment_id
    }""",
        data,
    )

# ---------------------------------------------------------------------------
# Scrape functions — # ---------------------------------------------------------------------------

async def scrape_user(username: str) -> Dict:
    """Scrape instagram user's data"""
    logger.info("scraping instagram user {}", username)
    pw, browser, page = await _new_session()
    try:
        data = await _fetch_json_in_browser(
            page,
            f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}",
        )
        return parse_user(data["data"]["user"])
    finally:
        await browser.close()
        await pw.stop()

async def scrape_post(url_or_shortcode: str) -> Dict:
    """Scrape single Instagram post data"""
    if "http" in url_or_shortcode:
        shortcode = url_or_shortcode.split("/p/")[-1].split("/")[0]
    else:
        shortcode = url_or_shortcode
    logger.info("scraping instagram post: {}", shortcode)
    variables = json.dumps(
        {
            "shortcode": shortcode,
            "fetch_tagged_user_count": None,
            "hoisted_comment_id": None,
            "hoisted_reply_id": None,
        },
        separators=(",", ":"),
    )
    body = f"variables={variables}&doc_id={INSTAGRAM_DOCUMENT_ID}"
    pw, browser, page = await _new_session()
    try:
        data = await _fetch_json_in_browser(
            page,
            "https://www.instagram.com/graphql/query",
            method="POST",
            body=body,
            extra_headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        return parse_post(data["data"]["xdt_shortcode_media"])
    finally:
        await browser.close()
        await pw.stop()

async def scrape_user_posts(
    username: str,
    page_size: int = 12,
    max_pages: Optional[int] = None,
) -> AsyncIterator[Dict]:
    """Scrape all posts of an instagram user given the username"""
    base_url = "https://www.instagram.com/graphql/query/"
    variables = {
        "after": None,
        "before": None,
        "data": {
            "count": page_size,
            "include_reel_media_seen_timestamp": True,
            "include_relationship_info": True,
            "latest_besties_reel_media": True,
            "latest_reel_media": True,
        },
        "first": page_size,
        "last": None,
        "username": f"{username}",
        "__relay_internal__pv__PolarisIsLoggedInrelayprovider": True,
        "__relay_internal__pv__PolarisShareSheetV3relayprovider": True,
    }
    prev_cursor: Optional[str] = None
    _page_number = 1
    pw, browser, page = await _new_session()
    try:
        while True:
            params = {
                "doc_id": INSTAGRAM_ACCOUNT_DOCUMENT_ID,
                "variables": json.dumps(variables, separators=(",", ":")),
            }
            final_url = f"{base_url}?{urlencode(params)}"
            data = await _fetch_json_in_browser(
                page,
                final_url,
                extra_headers={"content-type": "application/x-www-form-urlencoded"},
            )
            posts = data["data"]["xdt_api__v1__feed__user_timeline_graphql_connection"]
            for post in posts["edges"]:
                yield parse_user_posts(post["node"])
            page_info = posts["page_info"]
            if not page_info["has_next_page"]:
                logger.info(f"scraping posts page {_page_number}")
                break
            if page_info["end_cursor"] == prev_cursor:
                logger.warning("found no new posts, breaking")
                break
            prev_cursor = page_info["end_cursor"]
            variables["after"] = page_info["end_cursor"]
            _page_number += 1
            if max_pages and _page_number > max_pages:
                break
    finally:
        await browser.close()
        await pw.stop()

async def scrape_post_comments(shortcode: str, max_comments: int = 1000) -> list:
    """Scrape all comments from an Instagram post given the post ID"""
    logger.info("scraping instagram post comments: {}", shortcode)
    comments: list = []
    cursor: Optional[str] = None
    pw, browser, page = await _new_session()
    try:
        while len(comments) < max_comments:
            variables = {
                "after": cursor,
                "before": None,
                "first": 10,
                "last": None,
                "media_id": shortcode,
                "sort_order": "popular",
                "__relay_internal__pv__PolarisIsLoggedInrelayprovider": False,
            }
            body = (
                "variables="
                + json.dumps(variables, separators=(",", ":"))
                + f"&doc_id={INSTAGRAM_COMMENTS_DOC_ID}"
            )
            data = await _fetch_json_in_browser(
                page,
                "https://www.instagram.com/graphql/query",
                method="POST",
                body=body,
                extra_headers={"content-type": "application/x-www-form-urlencoded"},
            )
            if not data:
                logger.warning("empty response from comments API, stopping pagination")
                break
            comment_data = data["data"]["xdt_api__v1__media__media_id__comments__connection"]
            for edge in comment_data["edges"]:
                comments.append(parse_post_comment(edge["node"]))
            page_info = comment_data["page_info"]
            if not page_info["has_next_page"] or not page_info.get("end_cursor"):
                break
            cursor = page_info["end_cursor"]
            logger.info(f"scraped {len(comments)} comments")
            if max_comments and len(comments) >= max_comments:
                break
        return comments
    finally:
        await browser.close()
        await pw.stop()

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
