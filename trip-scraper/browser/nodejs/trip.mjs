// Trip.com scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Two surfaces:
// - `scrapeSearch(cityId, checkin, checkout, maxPages)` — `div.hotel-card` items from
//   the city hotel list (`https://www.trip.com/hotels/list?city=<id>`).
// - `scrapeHotel(hotelId, checkin, checkout)` — single property detail page.
//
// Trip.com is less aggressive on anti-bot than Expedia/Priceline, so a single
// goto + selector wait + scroll is usually enough.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 240;

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function fetchRenderedHtml(url, readySelector, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 1, scroll = true } = {}) {
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
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
      if (readySelector) {
        try { await page.waitForSelector(readySelector, { timeout: 25000 }); } catch (_) {}
      }
      if (scroll) {
        try {
          await page.evaluate(async () => {
            await new Promise((r) => {
              let y = 0;
              const i = setInterval(() => {
                window.scrollBy(0, 700);
                y += 700;
                if (y >= document.body.scrollHeight) { clearInterval(i); r(); }
              }, 250);
            });
          });
        } catch (_) {}
        await new Promise((r) => setTimeout(r, 2000));
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

function parseIntOrNull(text) {
  if (!text) return null;
  const m = /([\d,]+)/.exec(text);
  if (!m) return null;
  const n = parseInt(m[1].replace(/,/g, ""), 10);
  return Number.isFinite(n) ? n : null;
}

function detailUrl(hotelId, checkin, checkout) {
  const params = new URLSearchParams({ hotelId: String(hotelId) });
  if (checkin) params.set("checkIn", checkin);
  if (checkout) params.set("checkOut", checkout);
  return `https://www.trip.com/hotels/detail/?${params.toString()}`;
}

// ---------------- search ----------------

export function parseSearch(html, { checkin = "", checkout = "" } = {}) {
  const $ = cheerio.load(html);
  const out = [];
  // Trip ships two layouts: the older `.hotel-card` and the newer
  // `.compressmeta-hotel-wrap-v8` ("version B"). Match on both via an id-anchored
  // selector with the listing root class.
  $("[id][class*='hotel-card'], [id][class*='compressmeta-hotel-wrap']").each((_, el) => {
    const $c = $(el);
    const id = $c.attr("id") || "";
    if (!/^\d+$/.test(id)) return;
    const name = (
      $c.find(".list-card-title .name").first().text().trim()
      || $c.find(".list-card-title").first().text().trim()
      || $c.find(".hotel-title").first().text().trim()
      || $c.find(".name").first().text().trim()
    );
    // Score: a `.real` block whose text is a plain number (e.g. "9.4").
    let score = null;
    $c.find(".real").each((__, r) => {
      if (score) return;
      const t = $(r).text().trim();
      if (/^\d+(\.\d+)?$/.test(t)) score = t;
    });
    if (!score) score = $c.find(".score").first().text().trim() || null;
    // Word-form review tag near the score.
    const wordEl = $c.find(".describe, .review-rt, .outstanding").first().text();
    const wordMatch = wordEl ? /\b(Outstanding|Excellent|Very Good|Good|Pleasant|Fair|Wonderful|Fabulous|Exceptional)\b/i.exec(wordEl) : null;
    const reviewWord = wordMatch ? wordMatch[1] : null;
    const reviewBlock = $c.find(".count, .review-rt").text();
    const reviewCountMatch = reviewBlock ? /([\d,]+)\s+reviews?/i.exec(reviewBlock) : null;
    const reviewCount = reviewCountMatch ? parseIntOrNull(reviewCountMatch[1]) : null;
    // Price: `.real.labelColor` carries the headline price in version B;
    // older layout uses `.price-line`.
    const price = (
      $c.find(".real.labelColor").first().text().trim()
      || $c.find(".price-line").first().text().trim()
      || null
    );
    const totalPrice = $c.find(".price-explain").first().text().trim() || null;
    const tags = [];
    $c.find(".member-reward-tag, .encourage-tag, .highlight-tag, .hotel-tag").each((__, t) => {
      const txt = $(t).text().trim();
      if (txt && !tags.includes(txt)) tags.push(txt);
    });
    const locText = (
      $c.find(".transport, [class*='location'], [class*='landmark']").first().text().trim().replace(/\s+/g, " ")
      || null
    );
    const image = $c.find(".multi-images img, img.m-lazyImg__img").first().attr("src") || null;
    out.push({
      id,
      name,
      url: detailUrl(id, checkin, checkout),
      score,
      reviewWord,
      reviewCount,
      price,
      totalPrice,
      tags,
      location: locText,
      image,
    });
  });
  return out;
}

export async function scrapeSearch(cityId = "53", checkin = "", checkout = "", maxPages = 1, { proxyCountry = DEFAULT_PROXY_COUNTRY } = {}) {
  const out = [];
  for (let page = 1; page <= maxPages; page++) {
    const params = new URLSearchParams({ city: String(cityId) });
    if (checkin) params.set("checkin", checkin);
    if (checkout) params.set("checkout", checkout);
    if (page > 1) params.set("p", String(page));
    const url = `https://www.trip.com/hotels/list?${params.toString()}`;
    const html = await fetchRenderedHtml(url, "[id][class*='hotel-card'], [id][class*='compressmeta-hotel-wrap']", { proxyCountry });
    const items = parseSearch(html, { checkin, checkout });
    if (!items.length && page > 1) break;
    out.push(...items);
  }
  return out;
}

// ---------------- hotel ----------------

export function parseHotel(html, hotelId, url) {
  const $ = cheerio.load(html);
  // Title can live in `h1.hotelTitle__hotelName`, `.headInfo .name`, or just `h1`.
  const name = (
    $("h1.headInfo .name").first().text().trim()
    || $("h1[class*='hotelName']").first().text().trim()
    || $("h1").first().text().trim()
    || $(".hotel-name").first().text().trim()
  );
  const address = $("[class*='address']").first().text().trim() || null;
  const score = $("[class*='real']").filter((_, el) => /^[0-9.]+$/.test($(el).text().trim())).first().text().trim()
    || $(".score").first().text().trim()
    || null;
  const reviewBlock = $("[class*='comment-num'], [class*='reviewCount']").first().text();
  const reviewCount = parseIntOrNull(reviewBlock);
  const description = (
    $("[class*='introduction']").first().text().trim()
    || $("[class*='hotel-description']").first().text().trim()
    || ""
  );
  const amenities = [];
  $("[class*='facilities'] li, [class*='amenities'] li, [class*='hotelFacility'] li").each((_, el) => {
    const t = $(el).text().trim();
    if (t) amenities.push(t);
  });
  const images = [];
  $("img").each((_, el) => {
    const src = $(el).attr("src") || $(el).attr("data-src");
    if (src && /tripcdn\.com|ak-d\.tripcdn/.test(src) && /hotel|images/i.test(src) && !images.includes(src)) {
      images.push(src);
    }
  });
  const price = $("[class*='price'] [class*='real']").first().text().trim() || null;
  return {
    id: String(hotelId),
    url,
    name,
    address,
    score,
    reviewCount,
    description,
    amenities,
    images: images.slice(0, 30),
    price,
  };
}

export async function scrapeHotel(hotelId, checkin = "", checkout = "", { proxyCountry = DEFAULT_PROXY_COUNTRY } = {}) {
  const url = detailUrl(hotelId, checkin, checkout);
  const html = await fetchRenderedHtml(url, "h1, [class*='headInfo'], [class*='hotelName']", { proxyCountry });
  return parseHotel(html, hotelId, url);
}
