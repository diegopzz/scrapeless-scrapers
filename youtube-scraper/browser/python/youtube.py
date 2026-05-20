"""Youtube scraper using the official Scrapeless Python SDK + Playwright over CDP.
function names and emitted field names match verbatim, so downstream code
can Under the hood:
- `client.browser.create()` mints a cloud browser session, returning a CDP WS endpoint.
- Playwright connects over CDP, drives the page, returns rendered HTML or runs
  in-page `fetch()` against the internal `youtubei/v1` API (cookies + visitor
  data inherited from the live page).
- We parse `ytInitialData` / `ytInitialPlayerResponse` embedded JSON the same
  way the upstream reference does — with `jmespath` and JSONPath helpers.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Literal, Optional

import jmespath
from jsonpath_ng.ext import parse
from loguru import logger
from parsel import Selector
from playwright.async_api import async_playwright
from scrapeless import Scrapeless
from scrapeless.types import ICreateBrowser

DEFAULT_PROXY_COUNTRY = "US"
DEFAULT_SESSION_TTL = 180

# ---------------------------------------------------------------------------
# JSONPath helpers — same shape as the upstream reference's jp_all / jp_first
# ---------------------------------------------------------------------------

def jp_all(query: str, data: Any) -> List[Any]:
    return [match.value for match in parse(query).find(data)]

def jp_first(query: str, data: Any) -> Optional[Any]:
    matches = parse(query).find(data)
    return matches[0].value if matches else None

def convert_to_number(value: Any) -> Optional[int]:
    if value is None:
        return None
    raw = str(value).strip().upper().replace(",", "")
    if not raw:
        return None
    # Strip a trailing word like " VIEWS", " COMMENTS" etc.
    first_token = raw.split()[0] if raw.split() else raw
    if first_token.endswith("K"):
        try:
            return int(float(first_token[:-1]) * 1_000)
        except ValueError:
            return None
    if first_token.endswith("M"):
        try:
            return int(float(first_token[:-1]) * 1_000_000)
        except ValueError:
            return None
    try:
        return int(float(first_token))
    except ValueError:
        return None

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
    ready_selector: Optional[str] = None,
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
    retries: int = 1,
) -> str:
    """Mint a session, goto, optionally wait for stable marker, return HTML."""
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
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                if ready_selector:
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

async def _call_youtube_api(
    base_url: str,
    continuation_token: Optional[str] = None,
    search_query: Optional[str] = None,
    search_params: Optional[str] = None,
    referer: str = "https://www.youtube.com/",
    *,
    proxy_country: str = DEFAULT_PROXY_COUNTRY,
) -> Dict[str, Any]:
    """POST to the internal youtubei/v1 endpoint from a real YouTube page context.

    Mirrors the upstream reference's `call_youtube_api` but uses the browser's in-page fetch
    so we inherit cookies and the visitor data set during the bootstrap navigation.
    """
    payload: Dict[str, Any] = {
        "context": {
            "client": {
                "hl": "en",
                "gl": "US",
                "clientName": "WEB",
                "clientVersion": "2.20241111.07.00",
                "platform": "DESKTOP",
                "userInterfaceTheme": "USER_INTERFACE_THEME_DARK",
            },
            "user": {"lockedSafetyMode": False},
            "request": {
                "useSsl": True,
                "internalExperimentFlags": [],
                "consistencyTokenJars": [],
            },
        }
    }
    if search_query is not None:
        payload["query"] = search_query
        payload["params"] = search_params
    if continuation_token is not None:
        payload["continuation"] = continuation_token

    client = _client()
    session = client.browser.create(
        ICreateBrowser(proxy_country=proxy_country, session_ttl=DEFAULT_SESSION_TTL)
    )
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
        try:
            page = await browser.new_page()
            # Bootstrap a real YouTube tab so cookies + INNERTUBE_API_KEY are real.
            await page.goto(referer, wait_until="domcontentloaded", timeout=45000)
            result = await page.evaluate(
                """async ({ url, payload }) => {
                    const res = await fetch(url, {
                        method: "POST",
                        headers: {
                            "content-type": "application/json",
                            "x-youtube-client-name": "1",
                            "x-youtube-client-version": "2.20241111.07.00",
                        },
                        body: JSON.stringify(payload),
                        credentials: "include",
                    });
                    return await res.text();
                }""",
                {"url": base_url, "payload": payload},
            )
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                logger.warning("youtubei response was not JSON; first 200 chars: {}", result[:200])
                return {}
        finally:
            try:
                await browser.close()
            except Exception:
                pass

# ---------------------------------------------------------------------------
# Parsers — mirror the upstream reference's output dicts verbatim
# ---------------------------------------------------------------------------

def parse_yt_initial_data(html: str) -> Dict[str, Any]:
    """parse ytInitialData script from YouTube pages"""
    sel = Selector(text=html)
    raw = sel.xpath("//script[contains(text(),'ytInitialData')]/text()").get() or ""
    m = re.search(r"var ytInitialData = ({.*?});", raw, re.DOTALL)
    if not m:
        return {}
    return json.loads(m.group(1))

def parse_video_details(html: str) -> Dict[str, Any]:
    """parse video metadata from YouTube video page"""
    sel = Selector(text=html)
    raw = sel.xpath("//script[contains(text(),'ytInitialPlayerResponse')]/text()").get() or ""
    m = re.search(r"ytInitialPlayerResponse\s*=\s*({.*?});", raw, re.DOTALL)
    if not m:
        return {}
    data = json.loads(m.group(1))
    return data.get("videoDetails") or {}

def parse_video(html: str) -> Dict[str, Any]:
    """parse video metadata from YouTube video page"""
    video_details = parse_video_details(html)
    content_details = parse_yt_initial_data(html)

    likes = [
        i["title"]
        for i in jp_all("$..buttonViewModel", content_details)
        if isinstance(i, dict) and i.get("iconName") == "LIKE" and "title" in i
    ]
    channel_id = jp_first(
        "$..channelEndpoint.browseEndpoint.canonicalBaseUrl", content_details
    )
    verified_badges = jp_all(
        "$..videoOwnerRenderer..badges[0].metadataBadgeRenderer", content_details
    )
    verified = bool(
        verified_badges
        and any(
            isinstance(b, dict) and b.get("tooltip") == "Verified"
            for b in verified_badges
        )
    )

    thumbnail = (video_details.get("thumbnail") or {}).get("thumbnails")

    return {
        "video": {
            "videoId": video_details.get("videoId"),
            "title": video_details.get("title"),
            "publishingDate": jp_first("$..dateText.simpleText", content_details),
            "lengthSeconds": convert_to_number(video_details.get("lengthSeconds")),
            "keywords": video_details.get("keywords"),
            "description": video_details.get("shortDescription"),
            "thumbnail": thumbnail,
            "stats": {
                "viewCount": convert_to_number(video_details.get("viewCount")),
                "likeCount": convert_to_number(likes[0]) if likes else None,
                "commentCount": convert_to_number(
                    jp_first("$..contextualInfo.runs[0].text", content_details)
                ),
            },
        },
        "channel": {
            "name": video_details.get("author"),
            "identifierId": video_details.get("channelId"),
            "id": channel_id.replace("/", "") if channel_id else None,
            "verified": verified,
            "channelUrl": (
                f"https://www.youtube.com{channel_id}" if channel_id else None
            ),
            "subscriberCount": jp_first(
                "$..subscriberCountText.simpleText", content_details
            ),
            "thumbnails": jp_first(
                "$..engagementPanelSectionListRenderer..channelThumbnail.thumbnails",
                content_details,
            ),
        },
        "commentContinuationToken": jp_first(
            "$..continuationCommand.token", content_details
        ),
    }

def parse_comments_api(data: Dict[str, Any]) -> Dict[str, Any]:
    """parse comments API response for comment data"""
    parsed_comments: List[Dict[str, Any]] = []
    continuation_tokens = jp_all("$..continuationCommand.token", data)
    comments = jp_all("$..commentEntityPayload", data)
    for comment in comments:
        result = jmespath.search(
            """{
                comment: {
                    id: properties.commentId,
                    text: properties.content.content,
                    publishedTime: properties.publishedTime
                },
                author: {
                    id: author.channelId,
                    displayName: author.displayName,
                    avatarThumbnail: author.avatarThumbnailUrl,
                    isVerified: author.isVerified,
                    isCurrentUser: author.isVerified,
                    isCreator: author.isVerified
                },
                stats: {
                    likeCount: toolbar.likeCountLiked,
                    replyCount: toolbar.replyCount
                }
            }""",
            comment,
        )
        parsed_comments.append(result)

    return {
        "comments": parsed_comments,
        "continuationToken": continuation_tokens[-1] if continuation_tokens else None,
    }

def parse_video_api(data: Dict[str, Any]) -> Dict[str, Any]:
    """parse video data from YouTube channel-browse API response"""
    parsed_videos: List[Dict[str, Any]] = []
    continuation_tokens = jp_all("$..continuationCommand.token", data)
    reloaded = jp_all("$..reloadContinuationItemsCommand.continuationItems", data)
    videos = reloaded[-1] if reloaded else (jp_first("$..continuationItems", data) or [])
    for i in videos:
        if "richItemRenderer" not in i:
            continue
        result = jmespath.search(
            """{
            videoId: videoId,
            title: title.runs[0].text,
            description: descriptionSnippet.runs[0].text,
            publishedTime: publishedTimeText.simpleText,
            lengthText: lengthText.simpleText,
            viewCount: viewCountText.simpleText,
            thumbnails: thumbnail.thumbnails
            }""",
            i["richItemRenderer"]["content"]["videoRenderer"],
        )
        result["url"] = f"https://youtu.be/{result['videoId']}"
        parsed_videos.append(result)

    return {
        "videos": parsed_videos,
        "continuationToken": continuation_tokens[-1] if continuation_tokens else None,
    }

def parse_search_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """parse search results from the YouTube API response"""
    results: List[Dict[str, Any]] = []
    search_boxes = jp_all("$..videoRenderer", data)
    for i in search_boxes:
        if "videoId" not in i:
            continue
        result = jmespath.search(
            """{
            id: videoId,
            title: title.runs[0].text,
            description: detailedMetadataSnippets[0].snippetText.runs[0].text,
            publishedTime: publishedTimeText.simpleText,
            videoLength: lengthText.simpleText,
            viewCount: viewCountText.simpleText,
            videoBadges: badges[].metadataBadgeRenderer.label,
            channelBadges: ownerBadges[].metadataBadgeRenderer.accessibilityData.label,
            videoThumbnails: thumbnail.thumbnails,
            channelThumbnails: channelThumbnailSupportedRenderers.channelThumbnailWithLinkRenderer.thumbnail.thumbnails
            }""",
            i,
        )
        result["url"] = f"https://youtu.be/{result['id']}"
        results.append(result)

    return {
        "videos": results,
        "continuationToken": jp_first("$..continuationCommand.token", data),
    }

def parse_channel(html: str) -> Dict[str, Any]:
    """parse channel metadata from a rendered YouTube channel page.

    the upstream reference captures the `youtubei/v1/browse` XHR call to read the
    `aboutChannelViewModel`; we read the same payload from `ytInitialData`
    embedded in the HTML, which carries the same nested object after the
    "About" panel has been opened in-page.
    """
    data = parse_yt_initial_data(html)
    metadata = jp_first("$..aboutChannelViewModel", data) or {}

    links: List[Dict[str, Any]] = []
    if isinstance(metadata.get("links"), list):
        for entry in metadata["links"]:
            inner = entry.get("channelExternalLinkViewModel") or {}
            links.append(
                {
                    "title": (inner.get("title") or {}).get("content"),
                    "url": (inner.get("link") or {}).get("content"),
                    "favicon": inner.get("favicon"),
                }
            )
    result = jmespath.search(
        """{
        description: description,
        url: displayCanonicalChannelUrl,
        subscriberCount: subscriberCountText,
        videoCount: videoCountText,
        viewCount: viewCountText,
        joinedDate: joinedDateText.content,
        country: country
        }""",
        metadata,
    ) or {}
    result["links"] = links
    return result

# ---------------------------------------------------------------------------
# Scrape functions — mirror the upstream reference's exports verbatim
# ---------------------------------------------------------------------------

async def scrape_video(ids: List[str]) -> List[Dict[str, Any]]:
    """scrape video metadata from YouTube videos"""
    logger.info("scraping {} video metadata from video pages", len(ids))
    data: List[Dict[str, Any]] = []
    for video_id in ids:
        html = await _fetch_rendered_html(
            f"https://www.youtube.com/watch?v={video_id}",
            ready_selector="ytd-watch-flexy",
        )
        data.append(parse_video(html))
    logger.success("scraped {} video metadata from video pages", len(data))
    return data

async def scrape_comments(video_id: str, max_scrape_pages: Optional[int] = None) -> List[Dict[str, Any]]:
    """scrape comments from a YouTube video"""
    comments: List[Dict[str, Any]] = []
    cursor = 0
    logger.info("scraping video page for the comments continuation token")
    video_data = await scrape_video([video_id])
    continuation_token = video_data[0].get("commentContinuationToken")

    referer = f"https://www.youtube.com/watch?v={video_id}"
    while continuation_token and (
        cursor < max_scrape_pages if max_scrape_pages else True
    ):
        cursor += 1
        logger.info("scraping comments page with index {}", cursor)
        api_data = await _call_youtube_api(
            base_url="https://www.youtube.com/youtubei/v1/next?prettyPrint=false",
            continuation_token=continuation_token,
            referer=referer,
        )
        page = parse_comments_api(api_data)
        comments.extend(page["comments"])
        continuation_token = page["continuationToken"]

    logger.success("scraped {} comments for the video {}", len(comments), video_id)
    return comments

async def scrape_channel(channel_ids: List[str]) -> List[Dict[str, Any]]:
    """scrape channel metadata from YouTube channel pages.

    The "About" view-model is rendered after a click; we click the description
    preview before reading HTML, """
    out: List[Dict[str, Any]] = []
    logger.info("scraping {} channels", len(channel_ids))
    for channel_id in channel_ids:
        url = f"https://www.youtube.com/@{channel_id}"
        last_error: Optional[Exception] = None
        for attempt in range(2):
            client = _client()
            session = client.browser.create(
                ICreateBrowser(proxy_country=DEFAULT_PROXY_COUNTRY, session_ttl=DEFAULT_SESSION_TTL)
            )
            async with async_playwright() as pw:
                browser = await pw.chromium.connect_over_cdp(session.browser_ws_endpoint)
                try:
                    page = await browser.new_page()
                    await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    try:
                        await page.wait_for_selector(
                            "yt-description-preview-view-model button", timeout=15000
                        )
                        await page.click("yt-description-preview-view-model button")
                        await page.wait_for_selector(
                            "yt-formatted-string[title='About']", timeout=15000
                        )
                    except Exception as e:
                        logger.warning("about-panel open failed (continuing): {}", e)
                    html = await page.content()
                    out.append(parse_channel(html))
                    last_error = None
                    break
                except Exception as e:  # noqa: BLE001
                    last_error = e
                    logger.warning("channel attempt {} failed: {}", attempt + 1, e)
                finally:
                    try:
                        await browser.close()
                    except Exception:
                        pass
        if last_error is not None:
            raise RuntimeError(f"failed to scrape channel {channel_id}: {last_error}")
    logger.success("scraped {} channel info", len(out))
    return out

async def scrape_channel_videos(
    channel_id: str,
    sort_by: Literal["Latest", "Popular", "Oldest"] = "Latest",
    max_scrape_pages: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """scrape video metadata from YouTube channel page"""
    referer = f"https://www.youtube.com/@{channel_id}/videos"
    html = await _fetch_rendered_html(referer, ready_selector="ytd-rich-grid-renderer")
    initial = parse_yt_initial_data(html)
    chips = jp_all("$..chipViewModel", initial)
    sort_tokens = [
        c["tapCommand"]["innertubeCommand"]["continuationCommand"]["token"]
        for c in chips
        if c.get("text") == sort_by
        and "tapCommand" in c
        and "innertubeCommand" in c["tapCommand"]
        and "continuationCommand" in c["tapCommand"]["innertubeCommand"]
    ]
    if not sort_tokens:
        logger.warning("no continuation token for sort={}; returning empty", sort_by)
        return []
    continuation_token = sort_tokens[0]

    videos: List[Dict[str, Any]] = []
    cursor = 0
    while continuation_token and (
        cursor < max_scrape_pages if max_scrape_pages else True
    ):
        cursor += 1
        logger.info("scraping video page with index {}", cursor)
        api_data = await _call_youtube_api(
            base_url="https://www.youtube.com/youtubei/v1/browse?prettyPrint=false",
            continuation_token=continuation_token,
            referer=referer,
        )
        page = parse_video_api(api_data)
        videos.extend(page["videos"])
        continuation_token = page["continuationToken"]
    logger.success("scraped {} video for the channel {}", len(videos), channel_id)
    return videos

async def scrape_search(
    search_query: str,
    max_scrape_pages: Optional[int] = None,
    search_params: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """scrape search results from a YouTube search query"""
    cursor = 0
    search_data: List[Dict[str, Any]] = []
    api_data = await _call_youtube_api(
        base_url="https://www.youtube.com/youtubei/v1/search?prettyPrint=false",
        search_query=search_query,
        search_params=search_params,
    )
    page = parse_search_response(api_data)
    search_data.extend(page["videos"])
    continuation_token = page["continuationToken"]
    while continuation_token and (
        cursor < max_scrape_pages if max_scrape_pages else True
    ):
        cursor += 1
        logger.info("scraping search page with index {}", cursor)
        api_data = await _call_youtube_api(
            base_url="https://www.youtube.com/youtubei/v1/search?prettyPrint=false",
            continuation_token=continuation_token,
        )
        page = parse_search_response(api_data)
        search_data.extend(page["videos"])
        continuation_token = page["continuationToken"]
    logger.success("scraped {} video for the query {}", len(search_data), search_query)
    return search_data

async def scrape_shorts(ids: List[str]) -> List[Dict[str, Any]]:
    """scrape metadata from YouTube shorts"""
    out: List[Dict[str, Any]] = []
    logger.info("scraping {} short video metadata from short pages", len(ids))
    for short_id in ids:
        html = await _fetch_rendered_html(
            f"https://www.youtube.com/shorts/{short_id}",
            ready_selector="ytd-player",
        )
        details = parse_video_details(html)
        if details:
            thumb = details.get("thumbnail") or {}
            details["thumbnail"] = thumb.get("thumbnails")
        out.append(details)
    logger.success("scraped {} video metadata from short pages", len(out))
    return out

def to_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
