// Expedia scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Two surfaces:
// - `scrapeSearch(destination, checkin, checkout, maxPages)` — `[data-stid="lodging-card-responsive"]`
//   cards on `/Hotel-Search`.
// - `scrapeHotel(hotelUrl)` — hotel detail page.
//
// Expedia ships an aggressive "Bot or Not?" interstitial on cold visits to
// `/Hotel-Search`. We warm up on the homepage first so the session has the
// cookies it expects before we navigate to the search URL.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 300;
const HOMEPAGE_URL = "https://www.expedia.com/";

const TRANSIENT_NET_ERRORS = [
  "ERR_TUNNEL_CONNECTION_FAILED",
  "ERR_CONNECTION_CLOSED",
  "ERR_CONNECTION_RESET",
  "ERR_TIMED_OUT",
  "net::",
];

function isTransientError(err) {
  const msg = String(err?.message ?? err ?? "");
  return TRANSIENT_NET_ERRORS.some((s) => msg.includes(s));
}

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function withWarmedBrowser(fn, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 3, label = "navigation" } = {}) {
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
      // Warm up against the homepage so Expedia drops the interstitial.
      try {
        await page.goto(HOMEPAGE_URL, { waitUntil: "domcontentloaded", timeout: 60000 });
        // Linger longer on the homepage so the session collects the cookies
        // Expedia inspects on /Hotel-Search.
        await new Promise((r) => setTimeout(r, 4500));
        try { await page.evaluate(() => window.scrollBy(0, 600)); } catch (_) {}
        await new Promise((r) => setTimeout(r, 2500));
        try { await page.evaluate(() => window.scrollBy(0, 600)); } catch (_) {}
        await new Promise((r) => setTimeout(r, 1500));
      } catch (_) {}
      const result = await fn(page, browser);
      // If the page ended up on the "Bot or Not?" interstitial, treat as a
      // soft failure and retry on a fresh session.
      try {
        const title = (await page.title()) || "";
        if (/bot or not/i.test(title)) {
          lastError = new Error(`hit anti-bot interstitial (title="${title}")`);
        } else {
          return result;
        }
      } catch (_) {
        return result;
      }
    } catch (e) {
      lastError = e;
      if (!isTransientError(e) && !/bot or not/i.test(String(e?.message)) && attempt === retries) throw e;
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
    if (attempt < retries) {
      await new Promise((r) => setTimeout(r, 6000 * Math.pow(1.5, attempt)));
    }
  }
  throw new Error(`${label}: giving up after ${retries + 1} attempts: ${lastError?.message ?? lastError}`);
}

function abs(rel) {
  if (!rel) return "";
  if (rel.startsWith("http")) return rel;
  return `https://www.expedia.com${rel.startsWith("/") ? "" : "/"}${rel}`;
}

function decodeHtmlEntities(s) {
  if (!s) return s;
  return s
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#x27;/g, "'")
    .replace(/&#39;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");
}

function extractHotelId(url) {
  if (!url) return "";
  const m = /\.h(\d+)\.Hotel-Information/.exec(url);
  return m ? m[1] : "";
}

// ---------------- search ----------------

export function parseSearch(html) {
  const $ = cheerio.load(html);
  const out = [];
  $("div[data-stid='lodging-card-responsive']").each((_, el) => {
    const $c = $(el);
    const name = decodeHtmlEntities($c.find("h3.uitk-heading").first().text().trim()
      || $c.find("h3").first().text().trim());
    let href = $c.find("a.uitk-card-link").first().attr("href")
      || $c.find("a[href*='Hotel-Information']").first().attr("href")
      || "";
    href = decodeHtmlEntities(href);
    const url = abs(href);
    const id = extractHotelId(href);
    // Price: first $-amount in the price-summary block.
    let price = null;
    const priceBlock = $c.find("[data-test-id='price-summary-message-line']").first().text();
    const pm = priceBlock ? /\$[\d,]+/.exec(priceBlock) : null;
    if (pm) price = pm[0];
    // Reviews aria-label
    let review = null;
    $c.find("[aria-label]").each((__, e) => {
      const a = $(e).attr("aria-label") || "";
      if (/out of \d+/i.test(a) && !review) review = a;
    });
    const image = $c.find("img").first().attr("src") || null;
    if (name && id) {
      out.push({ id, name, url, price, review, image });
    }
  });
  return out;
}

export async function scrapeSearch(
  destination = "New York",
  checkin = "2026-06-15",
  checkout = "2026-06-16",
  maxPages = 1,
  { proxyCountry = DEFAULT_PROXY_COUNTRY } = {}
) {
  const params = new URLSearchParams({
    destination,
    startDate: checkin,
    endDate: checkout,
    rooms: "1",
    adults: "2",
  });
  const out = [];
  for (let page = 1; page <= maxPages; page++) {
    if (page > 1) params.set("pageIndex", String(page));
    const url = `https://www.expedia.com/Hotel-Search?${params.toString()}`;
    const cards = await withWarmedBrowser(async (page) => {
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
      try { await page.waitForSelector("div[data-stid='lodging-card-responsive']", { timeout: 30000 }); } catch (_) {}
      try {
        await page.evaluate(async () => {
          await new Promise((r) => {
            let y = 0;
            const i = setInterval(() => {
              window.scrollBy(0, 800);
              y += 800;
              if (y >= document.body.scrollHeight) { clearInterval(i); r(); }
            }, 350);
          });
        });
      } catch (_) {}
      await new Promise((r) => setTimeout(r, 2500));
      const html = await page.content();
      return parseSearch(html);
    }, { proxyCountry, label: `scrape_search page=${page}` });
    if (!cards.length && page > 1) break;
    out.push(...cards);
  }
  return out;
}

// ---------------- hotel ----------------

export function parseHotel(html, url) {
  const $ = cheerio.load(html);
  const name = decodeHtmlEntities(
    $("h1.uitk-heading").first().text().trim()
    || $("h1").first().text().trim()
    || $("meta[property='og:title']").attr("content") || ""
  );
  // Address: aria-label / data-stid markers
  const address = $("[data-stid='content-hotel-address']").first().text().trim()
    || $("[data-stid='content-hotel-address-link']").first().text().trim()
    || $("button[aria-label*='address']").first().text().trim()
    || null;
  const description = (
    $("div[data-stid='content-section-section-content']").first().text().trim()
    || $("section[data-stid='content-section-about-this-property']").first().text().trim()
    || $("meta[property='og:description']").attr("content") || ""
  );
  const amenities = [];
  $("[data-stid*='amenity'] li, [data-stid='content-amenities-list'] li").each((_, el) => {
    const t = $(el).text().trim();
    if (t) amenities.push(t);
  });
  const images = [];
  $("img").each((_, el) => {
    const src = $(el).attr("src") || $(el).attr("data-src");
    if (src && /\/(media|images|gold|hotels)\//i.test(src) && !images.includes(src)) {
      images.push(src);
    }
  });
  let review = null;
  $("[aria-label]").each((_, e) => {
    const a = $(e).attr("aria-label") || "";
    if (/out of \d+/i.test(a) && !review) review = a;
  });
  const price = $("[data-test-id='price-summary'] span, [data-stid='price-and-discount']").first().text().trim() || null;
  return {
    id: extractHotelId(url),
    url,
    name,
    address,
    description,
    amenities,
    images: images.slice(0, 30),
    review,
    price,
  };
}

export async function scrapeHotel(hotelUrl, { proxyCountry = DEFAULT_PROXY_COUNTRY } = {}) {
  return withWarmedBrowser(async (page) => {
    await page.goto(hotelUrl, { waitUntil: "domcontentloaded", timeout: 60000 });
    try { await page.waitForSelector("h1", { timeout: 30000 }); } catch (_) {}
    try { await page.evaluate(() => window.scrollBy(0, 1200)); } catch (_) {}
    await new Promise((r) => setTimeout(r, 2500));
    const html = await page.content();
    return parseHotel(html, hotelUrl);
  }, { proxyCountry, label: "scrape_hotel" });
}
