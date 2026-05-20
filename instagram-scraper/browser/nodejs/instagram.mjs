// Instagram scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// function names and emitted field names match verbatim, so downstream code
// can //
// Public data only. Anything behind Instagram's login wall (private profiles,
// DMs) is out of scope — match //
// Under the hood:
// - client.browser.create() mints a cloud browser session (CDP WS endpoint).
// - puppeteer-core connects over CDP, then calls Instagram's public GraphQL +
//   i.instagram.com JSON endpoints from inside the page context via
//   page.evaluate(fetch(...)) so the browser's cookies and CSRF token apply.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";

const DEFAULT_PROXY_COUNTRY = "CA";
const DEFAULT_SESSION_TTL = 180;

const INSTAGRAM_APP_ID = "936619743392459";
const INSTAGRAM_DOCUMENT_ID = "8845758582119845";
const INSTAGRAM_ACCOUNT_DOCUMENT_ID = "9310670392322965";
const INSTAGRAM_COMMENTS_DOC_ID = "26248690958161038";

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function newSession(proxyCountry = DEFAULT_PROXY_COUNTRY) {
  const { browserWSEndpoint } = await client().browser.create({
    proxyCountry,
    sessionTTL: DEFAULT_SESSION_TTL,
  });
  const browser = await puppeteer.connect({ browserWSEndpoint });
  const page = await browser.newPage();
  await page.goto("https://www.instagram.com/", { waitUntil: "domcontentloaded", timeout: 30000 });
  return { browser, page };
}

async function fetchJsonInBrowser(page, url, { method = "GET", body = null, extraHeaders = {} } = {}) {
  const headers = { "x-ig-app-id": INSTAGRAM_APP_ID, ...extraHeaders };
  const result = await page.evaluate(
    async ({ url, method, body, headers }) => {
      const res = await fetch(url, {
        method,
        body: body || undefined,
        headers,
        credentials: "include",
      });
      const text = await res.text();
      return { status: res.status, text };
    },
    { url, method, body, headers },
  );
  let text = result.text || "";
  if (text.startsWith("for (;;);")) text = text.slice("for (;;);".length);
  return JSON.parse(text);
}

// ---------------- parsers (verbatim mirror of the upstream reference's jmespath projections) ----------------

export function parseUser(data) {
  return {
    name: data?.full_name ?? null,
    username: data?.username ?? null,
    id: data?.id ?? null,
    category: data?.category_name ?? null,
    business_category: data?.business_category_name ?? null,
    phone: data?.business_phone_number ?? null,
    email: data?.business_email ?? null,
    bio: data?.biography ?? null,
    bio_links: (data?.bio_links ?? []).map((b) => b.url),
    homepage: data?.external_url ?? null,
    followers: data?.edge_followed_by?.count ?? null,
    follows: data?.edge_follow?.count ?? null,
    facebook_id: data?.fbid ?? null,
    is_private: data?.is_private ?? null,
    is_verified: data?.is_verified ?? null,
    profile_image: data?.profile_pic_url_hd ?? null,
    video_count: data?.edge_felix_video_timeline?.count ?? null,
    videos: (data?.edge_felix_video_timeline?.edges ?? []).map((e) => ({
      id: e.node.id,
      title: e.node.title,
      shortcode: e.node.shortcode,
      thumb: e.node.display_url,
      url: e.node.video_url,
      views: e.node.video_view_count,
      tagged: (e.node.edge_media_to_tagged_user?.edges ?? []).map((t) => t.node.user.username),
      captions: (e.node.edge_media_to_caption?.edges ?? []).map((c) => c.node.text),
      comments_count: e.node.edge_media_to_comment?.count,
      comments_disabled: e.node.comments_disabled,
      taken_at: e.node.taken_at_timestamp,
      likes: e.node.edge_liked_by?.count,
      location: e.node.location?.name,
      duration: e.node.video_duration,
    })),
    image_count: data?.edge_owner_to_timeline_media?.count ?? null,
    images: (data?.edge_felix_video_timeline?.edges ?? []).map((e) => ({
      id: e.node.id,
      title: e.node.title,
      shortcode: e.node.shortcode,
      src: e.node.display_url,
      url: e.node.video_url,
      views: e.node.video_view_count,
      tagged: (e.node.edge_media_to_tagged_user?.edges ?? []).map((t) => t.node.user.username),
      captions: (e.node.edge_media_to_caption?.edges ?? []).map((c) => c.node.text),
      comments_count: e.node.edge_media_to_comment?.count,
      comments_disabled: e.node.comments_disabled,
      taken_at: e.node.taken_at_timestamp,
      likes: e.node.edge_liked_by?.count,
      location: e.node.location?.name,
      accesibility_caption: e.node.accessibility_caption,
      duration: e.node.video_duration,
    })),
    saved_count: data?.edge_saved_media?.count ?? null,
    collections_count: data?.edge_saved_media?.count ?? null,
    related_profiles: (data?.edge_related_profiles?.edges ?? []).map((e) => e.node.username),
  };
}

export function parseComments(data) {
  if (data && "edge_media_to_comment" in data) {
    const c = data.edge_media_to_comment;
    return {
      comments_count: c?.count,
      comments_disabled: data.comments_disabled,
      comments_next_page: c?.page_info?.end_cursor,
      comments: (c?.edges ?? []).map((e) => ({
        id: e.node.id,
        text: e.node.text,
        created_at: e.node.created_at,
        owner_id: e.node.owner?.id,
        owner: e.node.owner?.username,
        owner_verified: e.node.owner?.is_verified,
        viewer_has_liked: e.node.viewer_has_liked,
      })),
    };
  }
  const c = data?.edge_media_to_parent_comment;
  return {
    comments_count: c?.count,
    comments_disabled: data?.comments_disabled,
    comments_next_page: c?.page_info?.end_cursor,
    comments: (c?.edges ?? []).map((e) => ({
      id: e.node.id,
      text: e.node.text,
      created_at: e.node.created_at,
      owner: e.node.owner?.username,
      owner_verified: e.node.owner?.is_verified,
      viewer_has_liked: e.node.viewer_has_liked,
      likes: e.node.edge_liked_by?.count,
    })),
  };
}

export function parsePost(data) {
  const result = {
    id: data?.id,
    shortcode: data?.shortcode,
    dimensions: data?.dimensions,
    src: data?.display_url,
    thumbnail_src: data?.thumbnail_src,
    media_preview: data?.media_preview,
    video_url: data?.video_url,
    views: data?.video_view_count,
    likes: data?.edge_media_preview_like?.count,
    location: data?.location?.name,
    taken_at: data?.taken_at_timestamp,
    related: (data?.edge_web_media_to_related_media?.edges ?? []).map((e) => e.node.shortcode),
    type: data?.product_type,
    video_duration: data?.video_duration,
    music: data?.clips_music_attribution_info,
    is_video: data?.is_video,
    tagged_users: (data?.edge_media_to_tagged_user?.edges ?? []).map((e) => e.node.user.username),
    captions: (data?.edge_media_to_caption?.edges ?? []).map((e) => e.node.text),
    related_profiles: (data?.edge_related_profiles?.edges ?? []).map((e) => e.node.username),
  };
  return { ...result, ...(parseComments(data) || {}) };
}

export function parseUserPosts(data) {
  return {
    id: data?.id,
    shortcode: data?.code,
    caption: data?.caption,
    taken_at: data?.taken_at,
    video_versions: data?.video_versions,
    image_versions2: data?.image_versions2,
    original_height: data?.original_height,
    original_width: data?.original_width,
    link: data?.link,
    title: data?.title,
    comment_count: data?.comment_count,
    top_likers: data?.top_likers,
    like_count: data?.like_count,
    usertags: data?.usertags,
    clips_metadata: data?.clips_metadata,
    comments: data?.comments,
  };
}

export function parsePostComment(data) {
  return {
    id: data?.pk,
    text: data?.text,
    created_at: data?.created_at,
    owner: data?.user?.username,
    owner_id: data?.user?.id,
    owner_verified: data?.user?.is_verified,
    owner_profile_pic: data?.user?.profile_pic_url,
    likes: data?.comment_like_count,
    replies_count: data?.child_comment_count,
    parent_comment_id: data?.parent_comment_id,
  };
}

// ---------------- scrape functions (mirror the upstream reference's exports) ----------------

export async function scrapeUser(username) {
  const { browser, page } = await newSession();
  try {
    const data = await fetchJsonInBrowser(
      page,
      `https://i.instagram.com/api/v1/users/web_profile_info/?username=${encodeURIComponent(username)}`,
    );
    return parseUser(data.data.user);
  } finally {
    await browser.close();
  }
}

export async function scrapePost(urlOrShortcode) {
  let shortcode = urlOrShortcode;
  if (urlOrShortcode.includes("http")) {
    shortcode = urlOrShortcode.split("/p/")[1].split("/")[0];
  }
  const variables = JSON.stringify({
    shortcode,
    fetch_tagged_user_count: null,
    hoisted_comment_id: null,
    hoisted_reply_id: null,
  });
  const body = `variables=${variables}&doc_id=${INSTAGRAM_DOCUMENT_ID}`;
  const { browser, page } = await newSession();
  try {
    const data = await fetchJsonInBrowser(page, "https://www.instagram.com/graphql/query", {
      method: "POST",
      body,
      extraHeaders: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    return parsePost(data.data.xdt_shortcode_media);
  } finally {
    await browser.close();
  }
}

export async function* scrapeUserPosts(username, pageSize = 12, maxPages = null) {
  const baseUrl = "https://www.instagram.com/graphql/query/";
  const variables = {
    after: null,
    before: null,
    data: {
      count: pageSize,
      include_reel_media_seen_timestamp: true,
      include_relationship_info: true,
      latest_besties_reel_media: true,
      latest_reel_media: true,
    },
    first: pageSize,
    last: null,
    username: `${username}`,
    __relay_internal__pv__PolarisIsLoggedInrelayprovider: true,
    __relay_internal__pv__PolarisShareSheetV3relayprovider: true,
  };
  let prevCursor = null;
  let pageNumber = 1;
  const { browser, page } = await newSession();
  try {
    while (true) {
      const params = new URLSearchParams({
        doc_id: INSTAGRAM_ACCOUNT_DOCUMENT_ID,
        variables: JSON.stringify(variables),
      });
      const finalUrl = `${baseUrl}?${params.toString()}`;
      const data = await fetchJsonInBrowser(page, finalUrl, {
        extraHeaders: { "content-type": "application/x-www-form-urlencoded" },
      });
      const posts = data.data.xdt_api__v1__feed__user_timeline_graphql_connection;
      for (const edge of posts.edges) yield parseUserPosts(edge.node);
      const pageInfo = posts.page_info;
      if (!pageInfo.has_next_page) break;
      if (pageInfo.end_cursor === prevCursor) break;
      prevCursor = pageInfo.end_cursor;
      variables.after = pageInfo.end_cursor;
      pageNumber += 1;
      if (maxPages && pageNumber > maxPages) break;
    }
  } finally {
    await browser.close();
  }
}

export async function scrapePostComments(shortcode, maxComments = 1000) {
  const comments = [];
  let cursor = null;
  const { browser, page } = await newSession();
  try {
    while (comments.length < maxComments) {
      const variables = {
        after: cursor,
        before: null,
        first: 10,
        last: null,
        media_id: shortcode,
        sort_order: "popular",
        __relay_internal__pv__PolarisIsLoggedInrelayprovider: false,
      };
      const body = `variables=${JSON.stringify(variables)}&doc_id=${INSTAGRAM_COMMENTS_DOC_ID}`;
      const data = await fetchJsonInBrowser(page, "https://www.instagram.com/graphql/query", {
        method: "POST",
        body,
        extraHeaders: { "content-type": "application/x-www-form-urlencoded" },
      });
      if (!data) break;
      const cd = data.data.xdt_api__v1__media__media_id__comments__connection;
      for (const edge of cd.edges) comments.push(parsePostComment(edge.node));
      const pageInfo = cd.page_info;
      if (!pageInfo.has_next_page || !pageInfo.end_cursor) break;
      cursor = pageInfo.end_cursor;
      if (maxComments && comments.length >= maxComments) break;
    }
    return comments;
  } finally {
    await browser.close();
  }
}
