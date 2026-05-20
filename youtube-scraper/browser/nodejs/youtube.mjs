// YouTube scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// function names and emitted field names match verbatim.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";
import { JSONPath } from "jsonpath-plus";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 180;

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

// ---------- JSONPath / number helpers ----------

function jpAll(query, data) {
  if (data == null) return [];
  return JSONPath({ path: query, json: data, wrap: true });
}

function jpFirst(query, data) {
  if (data == null) return null;
  const out = JSONPath({ path: query, json: data, wrap: true });
  return out.length ? out[0] : null;
}

export function convertToNumber(value) {
  if (value == null) return null;
  const s = String(value).trim().toUpperCase().replace(/,/g, "");
  if (!s) return null;
  const token = s.split(/\s+/)[0];
  if (token.endsWith("K")) {
    const n = parseFloat(token.slice(0, -1));
    return Number.isFinite(n) ? Math.floor(n * 1_000) : null;
  }
  if (token.endsWith("M")) {
    const n = parseFloat(token.slice(0, -1));
    return Number.isFinite(n) ? Math.floor(n * 1_000_000) : null;
  }
  const n = parseFloat(token);
  return Number.isFinite(n) ? Math.floor(n) : null;
}

// ---------- session plumbing ----------

async function fetchRenderedHtml(url, readySelector, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 1 } = {}) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const { browserWSEndpoint } = await client().browser.create({
      proxyCountry,
      sessionTTL: DEFAULT_SESSION_TTL,
    });
    let browser;
    try {
      browser = await puppeteer.connect({ browserWSEndpoint });
      const page = await browser.newPage();
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
      if (readySelector) {
        try { await page.waitForSelector(readySelector, { timeout: 20000 }); } catch (_) {}
      }
      const html = await page.content();
      if (html) return html;
      lastError = new Error("empty HTML");
    } catch (e) {
      lastError = e;
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
  }
  throw new Error(`giving up after ${retries + 1} attempts: ${lastError?.message}`);
}

async function callYoutubeApi({
  baseUrl,
  continuationToken = null,
  searchQuery = null,
  searchParams = null,
  referer = "https://www.youtube.com/",
  proxyCountry = DEFAULT_PROXY_COUNTRY,
}) {
  const payload = {
    context: {
      client: {
        hl: "en",
        gl: "US",
        clientName: "WEB",
        clientVersion: "2.20241111.07.00",
        platform: "DESKTOP",
        userInterfaceTheme: "USER_INTERFACE_THEME_DARK",
      },
      user: { lockedSafetyMode: false },
      request: { useSsl: true, internalExperimentFlags: [], consistencyTokenJars: [] },
    },
  };
  if (searchQuery != null) {
    payload.query = searchQuery;
    payload.params = searchParams;
  }
  if (continuationToken != null) payload.continuation = continuationToken;

  const { browserWSEndpoint } = await client().browser.create({
    proxyCountry, sessionTTL: DEFAULT_SESSION_TTL,
  });
  let browser;
  try {
    browser = await puppeteer.connect({ browserWSEndpoint });
    const page = await browser.newPage();
    await page.goto(referer, { waitUntil: "domcontentloaded", timeout: 45000 });
    const text = await page.evaluate(async ({ url, body }) => {
      const res = await fetch(url, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-youtube-client-name": "1",
          "x-youtube-client-version": "2.20241111.07.00",
        },
        body: JSON.stringify(body),
        credentials: "include",
      });
      return await res.text();
    }, { url: baseUrl, body: payload });
    try { return JSON.parse(text); } catch { return {}; }
  } finally {
    try { await browser?.close(); } catch (_) {}
  }
}

// ---------- parsers ----------

export function parseYtInitialData(html) {
  const $ = cheerio.load(html);
  let raw = "";
  $("script").each((_, el) => {
    const t = $(el).text();
    if (t.includes("ytInitialData")) { raw = t; return false; }
    return undefined;
  });
  const m = /var ytInitialData = ({.*?});/s.exec(raw);
  if (!m) return {};
  try { return JSON.parse(m[1]); } catch { return {}; }
}

export function parseVideoDetails(html) {
  const $ = cheerio.load(html);
  let raw = "";
  $("script").each((_, el) => {
    const t = $(el).text();
    if (t.includes("ytInitialPlayerResponse")) { raw = t; return false; }
    return undefined;
  });
  const m = /ytInitialPlayerResponse\s*=\s*({.*?});/s.exec(raw);
  if (!m) return {};
  try {
    const data = JSON.parse(m[1]);
    return data.videoDetails ?? {};
  } catch { return {}; }
}

export function parseVideo(html) {
  const videoDetails = parseVideoDetails(html);
  const contentDetails = parseYtInitialData(html);

  const likes = jpAll("$..buttonViewModel", contentDetails)
    .filter((i) => i && i.iconName === "LIKE" && typeof i.title === "string")
    .map((i) => i.title);
  const channelId = jpFirst("$..channelEndpoint.browseEndpoint.canonicalBaseUrl", contentDetails);
  const verifiedBadges = jpAll("$..videoOwnerRenderer..badges[0].metadataBadgeRenderer", contentDetails);
  const verified = verifiedBadges.some((b) => b && b.tooltip === "Verified");

  const thumbnail = videoDetails?.thumbnail?.thumbnails ?? null;

  return {
    video: {
      videoId: videoDetails.videoId ?? null,
      title: videoDetails.title ?? null,
      publishingDate: jpFirst("$..dateText.simpleText", contentDetails),
      lengthSeconds: convertToNumber(videoDetails.lengthSeconds),
      keywords: videoDetails.keywords ?? null,
      description: videoDetails.shortDescription ?? null,
      thumbnail,
      stats: {
        viewCount: convertToNumber(videoDetails.viewCount),
        likeCount: likes.length ? convertToNumber(likes[0]) : null,
        commentCount: convertToNumber(jpFirst("$..contextualInfo.runs[0].text", contentDetails)),
      },
    },
    channel: {
      name: videoDetails.author ?? null,
      identifierId: videoDetails.channelId ?? null,
      id: channelId ? String(channelId).replace(/\//g, "") : null,
      verified,
      channelUrl: channelId ? `https://www.youtube.com${channelId}` : null,
      subscriberCount: jpFirst("$..subscriberCountText.simpleText", contentDetails),
      thumbnails: jpFirst(
        "$..engagementPanelSectionListRenderer..channelThumbnail.thumbnails",
        contentDetails,
      ),
    },
    commentContinuationToken: jpFirst("$..continuationCommand.token", contentDetails),
  };
}

export function parseCommentsApi(data) {
  const continuationTokens = jpAll("$..continuationCommand.token", data);
  const comments = jpAll("$..commentEntityPayload", data);
  const parsed = comments.map((c) => ({
    comment: {
      id: c?.properties?.commentId ?? null,
      text: c?.properties?.content?.content ?? null,
      publishedTime: c?.properties?.publishedTime ?? null,
    },
    author: {
      id: c?.author?.channelId ?? null,
      displayName: c?.author?.displayName ?? null,
      avatarThumbnail: c?.author?.avatarThumbnailUrl ?? null,
      isVerified: c?.author?.isVerified ?? null,
      isCurrentUser: c?.author?.isVerified ?? null,
      isCreator: c?.author?.isVerified ?? null,
    },
    stats: {
      likeCount: c?.toolbar?.likeCountLiked ?? null,
      replyCount: c?.toolbar?.replyCount ?? null,
    },
  }));
  return {
    comments: parsed,
    continuationToken: continuationTokens.length ? continuationTokens[continuationTokens.length - 1] : null,
  };
}

export function parseVideoApi(data) {
  const continuationTokens = jpAll("$..continuationCommand.token", data);
  const reloaded = jpAll("$..reloadContinuationItemsCommand.continuationItems", data);
  const videos = reloaded.length ? reloaded[reloaded.length - 1] : (jpFirst("$..continuationItems", data) ?? []);
  const parsed = [];
  for (const i of videos) {
    if (!i || !i.richItemRenderer) continue;
    const vr = i.richItemRenderer?.content?.videoRenderer;
    if (!vr) continue;
    const result = {
      videoId: vr.videoId ?? null,
      title: vr.title?.runs?.[0]?.text ?? null,
      description: vr.descriptionSnippet?.runs?.[0]?.text ?? null,
      publishedTime: vr.publishedTimeText?.simpleText ?? null,
      lengthText: vr.lengthText?.simpleText ?? null,
      viewCount: vr.viewCountText?.simpleText ?? null,
      thumbnails: vr.thumbnail?.thumbnails ?? [],
    };
    result.url = `https://youtu.be/${result.videoId}`;
    parsed.push(result);
  }
  return {
    videos: parsed,
    continuationToken: continuationTokens.length ? continuationTokens[continuationTokens.length - 1] : null,
  };
}

export function parseSearchResponse(data) {
  const boxes = jpAll("$..videoRenderer", data);
  const results = [];
  for (const i of boxes) {
    if (!i || !i.videoId) continue;
    const result = {
      id: i.videoId,
      title: i.title?.runs?.[0]?.text ?? null,
      description: i.detailedMetadataSnippets?.[0]?.snippetText?.runs?.[0]?.text ?? null,
      publishedTime: i.publishedTimeText?.simpleText ?? null,
      videoLength: i.lengthText?.simpleText ?? null,
      viewCount: i.viewCountText?.simpleText ?? null,
      videoBadges: (i.badges ?? []).map((b) => b?.metadataBadgeRenderer?.label).filter(Boolean),
      channelBadges: (i.ownerBadges ?? []).map((b) => b?.metadataBadgeRenderer?.accessibilityData?.label).filter(Boolean),
      videoThumbnails: i.thumbnail?.thumbnails ?? [],
      channelThumbnails: i.channelThumbnailSupportedRenderers?.channelThumbnailWithLinkRenderer?.thumbnail?.thumbnails ?? null,
    };
    result.url = `https://youtu.be/${result.id}`;
    results.push(result);
  }
  return {
    videos: results,
    continuationToken: jpFirst("$..continuationCommand.token", data),
  };
}

export function parseChannel(html) {
  const data = parseYtInitialData(html);
  const metadata = jpFirst("$..aboutChannelViewModel", data) ?? {};
  const links = [];
  if (Array.isArray(metadata.links)) {
    for (const entry of metadata.links) {
      const inner = entry?.channelExternalLinkViewModel ?? {};
      links.push({
        title: inner?.title?.content ?? null,
        url: inner?.link?.content ?? null,
        favicon: inner?.favicon ?? null,
      });
    }
  }
  return {
    description: metadata.description ?? null,
    url: metadata.displayCanonicalChannelUrl ?? null,
    subscriberCount: metadata.subscriberCountText ?? null,
    videoCount: metadata.videoCountText ?? null,
    viewCount: metadata.viewCountText ?? null,
    joinedDate: metadata.joinedDateText?.content ?? null,
    country: metadata.country ?? null,
    links,
  };
}

// ---------- scrape functions ----------

export async function scrapeVideo(ids) {
  const out = [];
  for (const id of ids) {
    const html = await fetchRenderedHtml(`https://www.youtube.com/watch?v=${id}`, "ytd-watch-flexy");
    out.push(parseVideo(html));
  }
  return out;
}

export async function scrapeComments(videoId, maxScrapePages = null) {
  const comments = [];
  const videoData = await scrapeVideo([videoId]);
  let continuationToken = videoData[0]?.commentContinuationToken ?? null;
  const referer = `https://www.youtube.com/watch?v=${videoId}`;
  let cursor = 0;
  while (continuationToken && (maxScrapePages ? cursor < maxScrapePages : true)) {
    cursor += 1;
    const data = await callYoutubeApi({
      baseUrl: "https://www.youtube.com/youtubei/v1/next?prettyPrint=false",
      continuationToken,
      referer,
    });
    const page = parseCommentsApi(data);
    comments.push(...page.comments);
    continuationToken = page.continuationToken;
  }
  return comments;
}

export async function scrapeChannel(channelIds) {
  const out = [];
  for (const handle of channelIds) {
    const url = `https://www.youtube.com/@${handle}`;
    let lastError;
    for (let attempt = 0; attempt < 2; attempt++) {
      const { browserWSEndpoint } = await client().browser.create({
        proxyCountry: DEFAULT_PROXY_COUNTRY, sessionTTL: DEFAULT_SESSION_TTL,
      });
      let browser;
      try {
        browser = await puppeteer.connect({ browserWSEndpoint });
        const page = await browser.newPage();
        await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
        try {
          await page.waitForSelector("yt-description-preview-view-model button", { timeout: 15000 });
          await page.click("yt-description-preview-view-model button");
          await page.waitForSelector("yt-formatted-string[title='About']", { timeout: 15000 });
        } catch (_) {}
        const html = await page.content();
        out.push(parseChannel(html));
        lastError = null;
        break;
      } catch (e) {
        lastError = e;
      } finally {
        try { await browser?.close(); } catch (_) {}
      }
    }
    if (lastError) throw new Error(`failed to scrape channel ${handle}: ${lastError.message}`);
  }
  return out;
}

export async function scrapeChannelVideos(channelId, sortBy = "Latest", maxScrapePages = null) {
  const referer = `https://www.youtube.com/@${channelId}/videos`;
  const html = await fetchRenderedHtml(referer, "ytd-rich-grid-renderer");
  const initial = parseYtInitialData(html);
  const chips = jpAll("$..chipViewModel", initial);
  const tokens = chips
    .filter((c) => c?.text === sortBy && c?.tapCommand?.innertubeCommand?.continuationCommand?.token)
    .map((c) => c.tapCommand.innertubeCommand.continuationCommand.token);
  if (!tokens.length) return [];
  let continuationToken = tokens[0];

  const videos = [];
  let cursor = 0;
  while (continuationToken && (maxScrapePages ? cursor < maxScrapePages : true)) {
    cursor += 1;
    const data = await callYoutubeApi({
      baseUrl: "https://www.youtube.com/youtubei/v1/browse?prettyPrint=false",
      continuationToken,
      referer,
    });
    const page = parseVideoApi(data);
    videos.push(...page.videos);
    continuationToken = page.continuationToken;
  }
  return videos;
}

export async function scrapeSearch(searchQuery, maxScrapePages = null, searchParams = null) {
  const out = [];
  let data = await callYoutubeApi({
    baseUrl: "https://www.youtube.com/youtubei/v1/search?prettyPrint=false",
    searchQuery,
    searchParams,
  });
  let page = parseSearchResponse(data);
  out.push(...page.videos);
  let continuationToken = page.continuationToken;
  let cursor = 0;
  while (continuationToken && (maxScrapePages ? cursor < maxScrapePages : true)) {
    cursor += 1;
    data = await callYoutubeApi({
      baseUrl: "https://www.youtube.com/youtubei/v1/search?prettyPrint=false",
      continuationToken,
    });
    page = parseSearchResponse(data);
    out.push(...page.videos);
    continuationToken = page.continuationToken;
  }
  return out;
}

export async function scrapeShorts(ids) {
  const out = [];
  for (const id of ids) {
    const html = await fetchRenderedHtml(`https://www.youtube.com/shorts/${id}`, "ytd-player");
    const details = parseVideoDetails(html);
    if (details && details.thumbnail) {
      details.thumbnail = details.thumbnail.thumbnails ?? details.thumbnail;
    }
    out.push(details);
  }
  return out;
}
