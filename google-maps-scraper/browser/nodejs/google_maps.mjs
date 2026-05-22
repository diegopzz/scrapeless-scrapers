// Google Maps scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Two kinds:
// - places (list): search-results feed on /maps/search/<query> — parsed from
//   [role='feed'] [role='article'] card text, one row per visible card.
// - place (detail): single place panel on /maps/place/<slug>/<coords> — parsed
//   from h1, aria-label anchors (Address/Website/Phone), and div.F7nice.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 240;
const MAPS_BASE = "https://www.google.com/maps";

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function newClient() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function fetchRenderedHtml(url, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 2, settleMs = 8000 } = {}) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const { browserWSEndpoint } = await newClient().browser.create({
      proxyCountry,
      sessionTTL: DEFAULT_SESSION_TTL,
    });
    let browser;
    try {
      browser = await puppeteer.connect({ browserWSEndpoint });
      const page = await browser.newPage();
      await page.setViewport({ width: 1366, height: 900 });
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
      if (settleMs > 0) await new Promise(r => setTimeout(r, settleMs));
      const html = await page.content();
      if (html && html.length > 5000) return html;
      lastError = new Error(`short HTML len=${html?.length}`);
    } catch (e) {
      lastError = e;
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
  }
  throw new Error(`giving up after ${retries + 1} attempts: ${lastError?.message}`);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const RATING_RE = /(\d+(?:[.,]\d+)?)/;
const REVIEW_RE = /([\d,]+)\s*reviews?/i;

function parseRating(text) {
  const m = RATING_RE.exec(text);
  if (m) {
    const v = parseFloat(m[1].replace(",", "."));
    return (v >= 1 && v <= 5) ? v : null;
  }
  return null;
}

function parseReviewCount(text) {
  const m = REVIEW_RE.exec(text);
  return m ? parseInt(m[1].replace(/,/g, ""), 10) : null;
}

function ariaVal($, prefix) {
  let val = null;
  $("[aria-label]").each((_, el) => {
    const label = $(el).attr("aria-label") ?? "";
    if (label.startsWith(prefix)) {
      val = label.slice(prefix.length).trim() || null;
      return false;
    }
  });
  return val;
}

// ---------------------------------------------------------------------------
// Place list
// ---------------------------------------------------------------------------

export function parsePlaces(html, baseUrl = "") {
  const $ = cheerio.load(html);
  const out = [];

  $("[role='feed'] [role='article']").each((_, article) => {
    const link = $(article).find("a.hfpxzc").first();
    const name = link.attr("aria-label")?.trim() ?? "";
    const href = link.attr("href") ?? "";
    if (!name) return;

    const text = $(article).text();
    const lines = text.split("\n").map(l => l.trim()).filter(Boolean);

    let rating = null;
    let category = null;
    let address = null;
    let priceLevel = null;
    let description = null;

    for (const ln of lines) {
      if (!rating) {
        const m = RATING_RE.exec(ln);
        if (m) {
          const v = parseFloat(m[1].replace(",", "."));
          if (v >= 1 && v <= 5) { rating = v; continue; }
        }
      }
      if (ln.includes(" · ")) {
        const parts = ln.split(" · ").map(p => p.trim());
        for (const p of parts) {
          if (!category && /shop|cafe|restaurant|bar|store|market|gym|salon|hotel|diner|bakery|lounge/i.test(p)) {
            category = p;
          } else if (!priceLevel && /^\$[\d–-]/.test(p)) {
            priceLevel = p;
          } else if (!address && /\d+\s+\w/.test(p) && p.length > 6) {
            address = p;
          }
        }
      } else if (!description && ln.length > 15 && !/^(Open|Closed|Opens|Closes)/i.test(ln)) {
        description = ln;
      }
    }

    out.push({
      name,
      category: category ?? null,
      address: address ?? null,
      phone: null,
      website: null,
      rating,
      review_count: null,
      price_level: priceLevel ?? null,
      description: description ?? null,
      url: href.startsWith("http") ? href : `${MAPS_BASE}${href}`,
    });
  });
  return out;
}

export async function scrapePlaces(query, { proxyCountry = DEFAULT_PROXY_COUNTRY } = {}) {
  const url = `${MAPS_BASE}/search/${encodeURIComponent(query)}`;
  const html = await fetchRenderedHtml(url, { proxyCountry });
  return parsePlaces(html, url);
}

// ---------------------------------------------------------------------------
// Place detail
// ---------------------------------------------------------------------------

export function parsePlace(html, url) {
  const $ = cheerio.load(html);

  const name = $("h1").first().text().trim();
  const address = ariaVal($, "Address: ");
  const website = ariaVal($, "Website: ");
  const phone = ariaVal($, "Phone: ");

  const ratingText = $("div.F7nice").first().text().trim();
  const rating = parseRating(ratingText);

  let reviewCount = null;
  $("[aria-label]").each((_, el) => {
    const label = $(el).attr("aria-label") ?? "";
    if (/reviews?/i.test(label)) {
      reviewCount = parseReviewCount(label);
      return false;
    }
  });

  const category = $("button.DkEaL").first().text().trim() || null;

  const bodyText = $("body").text();
  const priceM = /\$[\d–-]+(?:\s*per\s+person)?/.exec(bodyText);
  const priceLevel = priceM ? priceM[0] : null;

  const descM = /(?:Cool|Hip|Trendy|Cozy|Popular|Vibrant|Classic|Modern|Casual)[^.]{10,200}\./.exec(bodyText);
  const description = descM ? descM[0].trim() : null;

  return {
    name,
    category,
    address,
    phone,
    website,
    rating,
    review_count: reviewCount,
    price_level: priceLevel,
    description,
    url,
  };
}

export async function scrapePlace(placeUrl, { proxyCountry = DEFAULT_PROXY_COUNTRY } = {}) {
  const html = await fetchRenderedHtml(placeUrl, { proxyCountry });
  return parsePlace(html, placeUrl);
}
