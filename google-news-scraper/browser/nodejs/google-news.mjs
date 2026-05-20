// GoogleNews scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Target surface: `https://news.google.com/search?q=<query>&hl=en` (and any
// topic page of the same shape). The scraper renders the SPA, waits for the
// article cards to mount, and extracts one row per `<article>` tag.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 180;
// Cards are rendered as `<div class="m5k28">` wrappers (sometimes inside
// `<article>` tags on older variants). We wait for the headline anchor
// class `JtKRv` which is stable across both layouts.
const READY_SELECTOR = "a.JtKRv, article a";

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function fetchRenderedHtml(url, readySelector, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 2 } = {}) {
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
      await page.setViewport({ width: 1366, height: 900 });
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
      try { await page.waitForSelector(readySelector, { timeout: 20000 }); } catch (_) {}
      // Give the SPA a beat to fan out card thumbnails.
      await new Promise((r) => setTimeout(r, 2000));
      const html = await page.content();
      if (html && html.includes("JtKRv")) return html;
      lastError = new Error("no article headlines in HTML");
    } catch (e) {
      lastError = e;
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
    if (attempt < retries) await new Promise((r) => setTimeout(r, 3000 + attempt * 2000));
  }
  throw new Error(`giving up after ${retries + 1} attempts: ${lastError?.message}`);
}

// ---------------- scrape functions ----------------

export async function scrapeNews(query) {
  const url = `https://news.google.com/search?q=${encodeURIComponent(query)}&hl=en-US&gl=US&ceid=US:en`;
  const html = await fetchRenderedHtml(url, READY_SELECTOR);
  return parseNews(html);
}

export async function scrapeTopic(topicId) {
  const url = `https://news.google.com/topics/${topicId}?hl=en-US&gl=US&ceid=US:en`;
  const html = await fetchRenderedHtml(url, READY_SELECTOR);
  return parseNews(html);
}

// ---------------- parser ----------------

export function parseNews(html) {
  const $ = cheerio.load(html);
  const seen = new Set();
  const out = [];
  let position = 0;
  // Iterate over the visible headline anchors. Each `a.JtKRv` is rendered
  // once per card and carries an `aria-label` of the form:
  //   "<title> - <source> - <time> - By <author>"
  // which is by far the cleanest way to recover the per-card fields.
  $("a.JtKRv").each((_, el) => {
    const a = $(el);
    const href = a.attr("href") || "";
    const titleText = normalise(a.text());
    if (!href || !titleText) return;
    const absUrl = href.startsWith("./") ? `https://news.google.com${href.slice(1)}` : href;
    if (seen.has(absUrl)) return;
    seen.add(absUrl);

    const aria = a.attr("aria-label") || "";
    const [, source = "", time = ""] = splitAriaLabel(aria, titleText);

    // Walk up to the card container to pick up the thumbnail.
    let thumbnail = "";
    const card = a.closest("div.m5k28, article, div.IBr9hb, div.XlKvRb");
    if (card.length) {
      card.find("img").each((__, img) => {
        const src = $(img).attr("src") || $(img).attr("data-src") || "";
        if (/^https?:/.test(src)) { thumbnail = src; return false; }
        return undefined;
      });
    }

    position += 1;
    out.push({
      position,
      title: titleText,
      url: absUrl,
      source: source,
      time: time,
      thumbnail: thumbnail,
    });
  });
  return out;
}

// aria-label format: "<title> - <source> - <time> - By <author>"
// where `time` is a relative phrase ("3 hours ago", "Yesterday", "2 days ago", …).
// Returns ["", source, time].
function splitAriaLabel(aria, title) {
  if (!aria) return ["", "", ""];
  // Trim the leading title (may differ by a stray punctuation; do a permissive prefix match).
  let rest = aria;
  if (aria.startsWith(title)) {
    rest = aria.slice(title.length);
  } else {
    const idx = aria.indexOf(" - ");
    if (idx >= 0) rest = aria.slice(idx);
  }
  rest = rest.replace(/^ -\s*/, "");
  const parts = rest.split(" - ");
  return ["", normalise(parts[0] || ""), normalise(parts[1] || "")];
}

function normalise(s) {
  return String(s || "").replace(/\s+/g, " ").trim();
}
