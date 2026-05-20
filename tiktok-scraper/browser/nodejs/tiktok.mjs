// TikTok scraper using @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// function names and emitted field names match verbatim, so downstream code
// can //
// TikTok aggressively fingerprints clients; Scrapeless's cloud browser ships
// with anti-detection defaults. For stubborn pages extend session_ttl rather
// than reducing wait times.
//
// Approach mirrors the upstream reference:
// - Post + profile pages: read the hidden __UNIVERSAL_DATA_FOR_REHYDRATION__ script.
// - Comments / search / channel: render the page, scroll, and capture matching XHRs.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "AU";
const DEFAULT_SESSION_TTL = 300;

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function render(url, { waitForSelector = null, autoScroll = false, preActions = null, renderingWaitMs = 0 } = {}) {
  const { browserWSEndpoint } = await client().browser.create({
    proxyCountry: DEFAULT_PROXY_COUNTRY,
    sessionTTL: DEFAULT_SESSION_TTL,
  });
  const xhrCalls = [];
  const browser = await puppeteer.connect({ browserWSEndpoint });
  try {
    const page = await browser.newPage();
    page.on("response", async (resp) => {
      try {
        const rt = resp.request().resourceType();
        if (rt !== "xhr" && rt !== "fetch") return;
        let bodyText = null;
        try { bodyText = await resp.text(); } catch (_) {}
        xhrCalls.push({ url: resp.url(), response: { body: bodyText } });
      } catch (_) {}
    });
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
    if (waitForSelector) {
      try { await page.waitForSelector(waitForSelector, { timeout: 15000 }); } catch (_) {}
    }
    if (preActions) {
      try { await preActions(page); } catch (_) {}
    }
    if (autoScroll) {
      for (let i = 0; i < 10; i++) {
        const before = await page.evaluate(() => document.body.scrollHeight);
        await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
        await new Promise((r) => setTimeout(r, 3000));
        const after = await page.evaluate(() => document.body.scrollHeight);
        if (after <= before + 10) break;
      }
    }
    if (renderingWaitMs) await new Promise((r) => setTimeout(r, renderingWaitMs));
    const html = await page.content();
    return { html, xhrCalls };
  } finally {
    try { await browser.close(); } catch (_) {}
  }
}

function extractUniversalData(html) {
  const $ = cheerio.load(html);
  const txt = $("script#__UNIVERSAL_DATA_FOR_REHYDRATION__").text();
  return JSON.parse(txt);
}

export function parsePost(response) {
  const universal = extractUniversalData(response.html);
  const item = universal.__DEFAULT_SCOPE__["webapp.video-detail"].itemInfo.itemStruct;
  const v = item.video ?? {};
  const a = item.author ?? {};
  return {
    id: item.id,
    desc: item.desc,
    createTime: item.createTime,
    video: {
      duration: v.duration,
      ratio: v.ratio,
      cover: v.cover,
      playAddr: v.playAddr,
      downloadAddr: v.downloadAddr,
      bitrate: v.bitrate,
    },
    author: {
      id: a.id,
      uniqueId: a.uniqueId,
      nickname: a.nickname,
      avatarLarger: a.avatarLarger,
      signature: a.signature,
      verified: a.verified,
    },
    stats: item.stats,
    locationCreated: item.locationCreated,
    diversificationLabels: item.diversificationLabels,
    suggestedWords: item.suggestedWords,
    contents: (item.contents ?? []).map((c) => ({
      textExtra: (c.textExtra ?? []).map((te) => ({ hashtagName: te.hashtagName })),
    })),
  };
}

export async function scrapePosts(urls) {
  const out = [];
  for (const url of urls) {
    const response = await render(url, { waitForSelector: "#__UNIVERSAL_DATA_FOR_REHYDRATION__" });
    out.push(parsePost(response));
  }
  return out;
}

export function parseComments(response) {
  let data = null;
  for (const xhr of response.xhrCalls) {
    if (!xhr.url.includes("/api/comment/list/") || !xhr.response.body) continue;
    try { data = JSON.parse(xhr.response.body); break; } catch (_) { continue; }
  }
  if (!data) throw new Error("Comment XHR data not found");
  return (data.comments ?? []).map((c) => ({
    text: c.text,
    comment_language: c.comment_language,
    digg_count: c.digg_count,
    reply_comment_total: c.reply_comment_total,
    author_pin: c.author_pin,
    create_time: c.create_time,
    cid: c.cid,
    nickname: c.user?.nickname,
    unique_id: c.user?.unique_id,
    aweme_id: c.aweme_id,
  }));
}

export async function scrapeComments(postUrl) {
  const preActions = async (page) => {
    try {
      await page.waitForSelector("span[data-e2e='comment-icon']", { timeout: 5000 });
      await page.click("span[data-e2e='comment-icon']");
      await page.waitForSelector("div.TUXTabBar", { timeout: 5000 });
    } catch (_) {}
    await new Promise((r) => setTimeout(r, 7000));
  };
  const response = await render(postUrl, { preActions, renderingWaitMs: 5000 });
  return parseComments(response);
}

export function parseProfile(response) {
  const universal = extractUniversalData(response.html);
  return universal.__DEFAULT_SCOPE__["webapp.user-detail"].userInfo;
}

export async function scrapeProfiles(urls) {
  const out = [];
  for (const url of urls) {
    const response = await render(url, { waitForSelector: "#__UNIVERSAL_DATA_FOR_REHYDRATION__" });
    out.push(parseProfile(response));
  }
  return out;
}

export function parseSearch(response) {
  const searchData = [];
  for (const c of response.xhrCalls) {
    if (!c.url.includes("/api/search/general/full/") || !c.response.body) continue;
    try {
      const data = JSON.parse(c.response.body).data ?? [];
      searchData.push(...data);
    } catch (_) {}
  }
  const parsed = [];
  for (const item of searchData) {
    if (item.type !== 1) continue;
    const it = item.item;
    parsed.push({
      id: it.id,
      desc: it.desc,
      createTime: it.createTime,
      video: it.video,
      author: it.author,
      stats: it.stats,
      authorStats: it.authorStats,
      type: item.type,
    });
  }
  return parsed;
}

export async function scrapeSearch(keyword) {
  const url = `https://www.tiktok.com/search?q=${encodeURIComponent(keyword)}`;
  const response = await render(url, {
    waitForSelector: "div[data-e2e='search_top-item']",
    autoScroll: true,
    renderingWaitMs: 15000,
  });
  return parseSearch(response);
}

export function parseChannel(response) {
  const channelData = [];
  for (const c of response.xhrCalls) {
    if (!c.url.includes("/api/post/item_list/") || !c.response.body) continue;
    try {
      const data = JSON.parse(c.response.body).itemList ?? [];
      channelData.push(...data);
    } catch (_) {
      throw new Error("Post data couldn't load");
    }
  }
  return channelData.map((post) => ({
    createTime: post.createTime,
    desc: post.desc,
    id: post.id,
    stats: post.stats,
    contents: (post.contents ?? []).map((c) => ({
      desc: c.desc,
      textExtra: (c.textExtra ?? []).map((te) => ({ hashtagName: te.hashtagName })),
    })),
  }));
}

export async function scrapeChannel(url) {
  const response = await render(url, { autoScroll: true, renderingWaitMs: 15000 });
  return parseChannel(response);
}
