// Craigslist scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Under the hood:
// - `client.browser.create()` mints a cloud session on Scrapeless's Scraping Browser,
//   returning a CDP WebSocket endpoint (`browserWSEndpoint`).
// - puppeteer-core connects to that WebSocket, drives the page, returns rendered HTML.
// - cheerio parses the HTML into objects matching DATA_MODEL.md.
//
// Two surfaces:
// - `scrapeSearch(city, category, query, maxPages)` — gallery cards from a city search page.
// - `scrapeListing(url)` — standalone listing detail page (`/<area>/<cat>/d/<slug>/<id>.html`).
//
// Craigslist is light on anti-bot but rate-limits aggressively, so we sleep between page hits.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 180;
const SEARCH_PAGE_SLEEP_MS = 4500;

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

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
      // Craigslist gallery cards lazy-render after the static <ol> is rewritten by JS.
      try {
        await page.evaluate(() => window.scrollBy(0, 800));
      } catch (_) {}
      await new Promise((r) => setTimeout(r, 2500));
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

function abs(base, rel) {
  try { return new URL(rel, base).toString(); } catch (_) { return rel; }
}

// ---------------- search ----------------

export function parseSearch(html, baseUrl) {
  const $ = cheerio.load(html);
  const out = [];
  $(".cl-search-result").each((_, el) => {
    const $li = $(el);
    const id = $li.attr("data-pid") || "";
    if (!id) return;
    const title = $li.find("a.posting-title span.label").first().text().trim()
      || $li.attr("title")
      || "";
    const href = $li.find("a.posting-title").first().attr("href")
      || $li.find("a.main").first().attr("href")
      || "";
    const url = href ? abs(baseUrl, href) : "";
    const price = $li.find("span.priceinfo").first().text().trim() || null;
    const location = $li.find("span.result-location").first().text().trim() || null;
    const postedAt = $li.find("span.result-posted-date").first().text().trim() || null;
    const image = $li.find("div.swipe img").first().attr("src") || null;
    if (id && title) {
      out.push({ id, title, url, price, location, postedAt, image });
    }
  });
  return out;
}

export async function scrapeSearch(city = "newyork", category = "sss", query = "", maxPages = 1, { proxyCountry = DEFAULT_PROXY_COUNTRY } = {}) {
  const base = `https://${city}.craigslist.org/search/${category}`;
  const out = [];
  for (let page = 0; page < maxPages; page++) {
    const params = new URLSearchParams();
    if (query) params.set("query", query);
    if (page > 0) params.set("s", String(page * 120));
    const url = params.toString() ? `${base}?${params.toString()}` : base;
    const html = await fetchRenderedHtml(url, ".cl-search-result, ol.cl-static-search-results", { proxyCountry });
    const items = parseSearch(html, url);
    if (!items.length && page > 0) break;
    out.push(...items);
    if (page + 1 < maxPages) await new Promise((r) => setTimeout(r, SEARCH_PAGE_SLEEP_MS));
  }
  return out;
}

// ---------------- listing ----------------

function extractListingId(url) {
  const m = /\/(\d+)\.html/.exec(url);
  return m ? m[1] : "";
}

export function parseListing(html, url) {
  const $ = cheerio.load(html);
  const titleTextOnly = $("#titletextonly").first().text().trim();
  const price = $("h1.postingtitle span.price, span.price").first().text().trim() || null;
  // Location: parenthetical inside the postingtitle, e.g. " (Lower East Side)".
  const titleHtml = $("h1.postingtitle").html() || "";
  const locMatch = /\(([^()]+)\)\s*</.exec(titleHtml);
  const location = locMatch ? locMatch[1].trim() : null;
  const postedAt = $("time.date.timeago").first().attr("datetime") || null;
  // Strip the QR/print scaffolding from the body, take the first meaningful text.
  const $body = $("#postingbody").clone();
  $body.find("div.print-information, div.notices, .reply-button-row").remove();
  const description = $body.text().replace(/^\s*QR Code Link to This Post\s*/i, "").trim();
  const attributes = [];
  $("p.attrgroup span").each((_, el) => {
    const t = $(el).text().trim();
    if (t) attributes.push(t);
  });
  const images = [];
  $("#thumbs a").each((_, el) => {
    const href = $(el).attr("href");
    if (href) images.push(href);
  });
  if (!images.length) {
    $("div.slide.first img, div.slide img").each((_, el) => {
      const src = $(el).attr("src");
      if (src) images.push(src);
    });
  }
  const latitude = $("div#map").attr("data-latitude") || null;
  const longitude = $("div#map").attr("data-longitude") || null;
  const crumbs = $("ul.breadcrumbs li").map((_, el) => $(el).text().trim()).get();
  const section = crumbs.length >= 2 ? crumbs[1] : null;
  const category = crumbs.length >= 3 ? crumbs[2] : null;
  return {
    id: extractListingId(url),
    url,
    title: titleTextOnly,
    price,
    location,
    postedAt,
    description,
    attributes,
    images,
    latitude,
    longitude,
    section,
    category,
  };
}

export async function scrapeListing(url, { proxyCountry = DEFAULT_PROXY_COUNTRY } = {}) {
  const html = await fetchRenderedHtml(url, "#titletextonly, h1.postingtitle", { proxyCountry });
  return parseListing(html, url);
}
