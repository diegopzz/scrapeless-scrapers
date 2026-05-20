// Threads.net scraper using @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// function names and emitted field names match verbatim, so downstream code
// can //
// Public data only. Threads gates non-public surfaces behind login — out of scope.
//
// Threads embeds its server-rendered data in
// <script type="application/json" data-sjs> tags. We render the page in a
// Scrapeless cloud browser, then read those scripts and walk them for
// `thread_items` / `user` blobs the same way the upstream reference does.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

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

async function fetchRendered(url, { autoScroll = false, retries = 3 } = {}) {
  let lastError;
  for (let attempt = 0; attempt < retries; attempt++) {
    const { browserWSEndpoint } = await client().browser.create({
      proxyCountry: DEFAULT_PROXY_COUNTRY,
      sessionTTL: DEFAULT_SESSION_TTL,
    });
    const browser = await puppeteer.connect({ browserWSEndpoint });
    try {
      const page = await browser.newPage();
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
      if (autoScroll) {
        for (let i = 0; i < 5; i++) {
          await page.evaluate(() => window.scrollBy(0, window.innerHeight));
          await new Promise((r) => setTimeout(r, 1000));
        }
      }
      const finalUrl = page.url();
      const html = await page.content();
      if (!finalUrl.includes("/accounts/login")) return { finalUrl, html };
      lastError = new Error(`login wall: ${finalUrl}`);
    } catch (e) {
      lastError = e;
    } finally {
      try { await browser.close(); } catch (_) {}
    }
  }
  throw new Error(`encountered endless login requirement redirect loop - does the URL exist? ${lastError?.message}`);
}

// nested_lookup helper — recursively collect all values for a given key
function nestedLookup(obj, key, out = []) {
  if (obj && typeof obj === "object") {
    if (Array.isArray(obj)) {
      for (const v of obj) nestedLookup(v, key, out);
    } else {
      for (const [k, v] of Object.entries(obj)) {
        if (k === key) out.push(v);
        nestedLookup(v, key, out);
      }
    }
  }
  return out;
}

export function parseThread(data) {
  const post = data?.post ?? {};
  const carousel = post.carousel_media ?? [];
  const result = {
    text: post.caption?.text,
    published_on: post.taken_at,
    id: post.id,
    pk: post.pk,
    code: post.code,
    username: post.user?.username,
    user_pic: post.user?.profile_pic_url,
    user_verified: post.user?.is_verified,
    user_pk: post.user?.pk,
    user_id: post.user?.id,
    has_audio: post.has_audio,
    reply_count: post.text_post_app_info?.direct_reply_count,
    like_count: post.like_count,
    images: carousel.map((c) => c?.image_versions2?.candidates?.[1]?.url).filter(Boolean),
    image_count: post.carousel_media_count,
    videos: Array.from(new Set((post.video_versions ?? []).map((v) => v.url))),
  };
  result.url = `https://www.threads.net/@${result.username}/post/${result.code}`;
  result.image_count = (result.images || "").length;
  return result;
}

export function parseProfile(data) {
  const hdVersions = data?.hd_profile_pic_versions ?? [];
  const result = {
    is_private: data?.text_post_app_is_private,
    is_verified: data?.is_verified,
    profile_pic: hdVersions[hdVersions.length - 1]?.url,
    username: data?.username,
    full_name: data?.full_name,
    bio: data?.biography,
    bio_links: (data?.bio_links ?? []).map((b) => b.url),
    followers: data?.follower_count,
  };
  result.url = `https://www.threads.net/@${result.username}`;
  return result;
}

export async function scrapeThread(url) {
  const { finalUrl, html } = await fetchRendered(url);
  if (finalUrl.includes("error=invalid_post")) return {};
  const $ = cheerio.load(html);
  const datasets = [];
  $('script[type="application/json"][data-sjs]').each((_, el) => datasets.push($(el).text()));
  const threadDatasets = datasets.filter((d) => d.includes('"ScheduledServerJS"') && d.includes("thread_items"));
  if (!threadDatasets.length) throw new Error("could not find thread data in page");
  const data = JSON.parse(threadDatasets[threadDatasets.length - 1]);
  const threadItems = nestedLookup(data, "thread_items");
  const threads = threadItems.flat().map(parseThread);
  return { thread: threads[0], replies: threads.slice(1) };
}

export async function scrapeProfile(url) {
  const { html } = await fetchRendered(url, { autoScroll: true });
  const parsed = { user: {}, threads: [] };
  const $ = cheerio.load(html);
  const datasets = [];
  $('script[type="application/json"][data-sjs]').each((_, el) => datasets.push($(el).text()));
  for (const ds of datasets) {
    if (!ds.includes('"ScheduledServerJS"')) continue;
    const isProfile = ds.includes("follower_count");
    const isThreads = ds.includes("thread_items");
    if (!isProfile && !isThreads) continue;
    const data = JSON.parse(ds);
    if (isProfile) {
      const userData = nestedLookup(data, "user");
      if (userData.length) parsed.user = parseProfile(userData[0]);
    }
    if (isThreads) {
      const items = nestedLookup(data, "thread_items");
      parsed.threads.push(...items.flat().map(parseThread));
    }
  }
  return parsed;
}
