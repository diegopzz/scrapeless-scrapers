// Redbubble scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Surfaces:
//   - scrapeProduct(urls)         -> array of Product dicts (PDP fields lifted from JSON-LD + __NEXT_DATA__)
//   - scrapeSearch(query, maxPages) -> array of SearchResult dicts (PLP cards from __NEXT_DATA__)
//
// Redbubble pages are Next.js-rendered, so `__NEXT_DATA__` is the source of truth.
// We fall back to JSON-LD ItemList on the search page and to JSON-LD Product on the PDP.

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
        try { await page.waitForSelector(readySelector, { timeout: 15000 }); } catch (_) {}
      }
      const html = await page.content();
      if (html && html.toLowerCase().includes("<html")) return html;
      lastError = new Error("empty HTML");
    } catch (e) {
      lastError = e;
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
  }
  throw new Error(`giving up after ${retries + 1} attempts: ${lastError?.message}`);
}

// ---------------- helpers ----------------

function clean(value) {
  if (value == null) return null;
  const v = String(value).replace(/\s+/g, " ").trim();
  return v || null;
}

function readNextData($) {
  const raw = $('script#__NEXT_DATA__').first().contents().text();
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

function* iterJsonldNodes($) {
  const blocks = $('script[type="application/ld+json"]')
    .map((_, el) => $(el).contents().text())
    .get();
  for (const raw of blocks) {
    if (!raw || !raw.trim()) continue;
    let data;
    try { data = JSON.parse(raw); } catch { continue; }
    const nodes = Array.isArray(data) ? data : [data];
    for (const node of nodes) {
      if (node && typeof node === "object") yield node;
    }
  }
}

function typeMatches(node, wanted) {
  const t = node["@type"];
  if (typeof t === "string") return t === wanted;
  if (Array.isArray(t)) return t.includes(wanted);
  return false;
}

// PDP URL example: https://www.redbubble.com/i/sticker/<slug>-by-<artist>/<workId>/<token>
const PDP_URL_RE = /\/i\/([^/]+)\/([^/]+?)(?:-by-([^/]+))?\/(\d+)\/[a-z0-9]+/i;

function parsePdpUrl(url) {
  if (!url) return { medium: null, artist: null, workId: null };
  const m = String(url).match(PDP_URL_RE);
  if (!m) return { medium: null, artist: null, workId: null };
  return { medium: m[1] || null, artist: m[3] || null, workId: m[4] || null };
}

function shortAvailability(value) {
  if (typeof value !== "string") return null;
  return value.includes("/") ? value.split("/").pop() : value;
}

function toNumber(value) {
  if (value == null) return null;
  const n = parseFloat(String(value).replace(/[^\d.\-]/g, ""));
  return Number.isFinite(n) ? n : null;
}

// ---------------- parsers ----------------

export function parseProduct(html, url) {
  const $ = cheerio.load(html);
  const next = readNextData($);
  const pp = next?.props?.pageProps ?? {};

  let ld = {};
  for (const node of iterJsonldNodes($)) {
    if (typeMatches(node, "Product")) { ld = node; break; }
  }

  const offer = (ld.offers && typeof ld.offers === "object")
    ? (Array.isArray(ld.offers) ? (ld.offers[0] ?? {}) : ld.offers)
    : {};
  const rating = (ld.aggregateRating && typeof ld.aggregateRating === "object") ? ld.aggregateRating : {};

  let images = [];
  if (typeof ld.image === "string") images = [ld.image];
  else if (Array.isArray(ld.image)) images = ld.image.filter(Boolean).map(String);

  const { medium, artist, workId } = parsePdpUrl(url);
  const item = pp.initialInventoryItem ?? {};
  const reviewSummary = pp.reviewSummary ?? {};

  // Prefer __NEXT_DATA__ price (numeric) over JSON-LD price (string in some locales)
  const price = toNumber(item?.price?.amount ?? offer.price);
  const currency = item?.price?.currency ?? offer.priceCurrency ?? null;

  let ratingValue = rating.ratingValue != null ? Number(rating.ratingValue) : null;
  if (ratingValue == null && reviewSummary.rating != null) {
    ratingValue = Number(reviewSummary.rating);
  }
  let reviewCount = rating.ratingCount != null ? parseInt(rating.ratingCount, 10) : null;
  if (reviewCount == null && rating.reviewCount != null) {
    reviewCount = parseInt(rating.reviewCount, 10);
  }
  if (reviewCount == null && reviewSummary.count != null) {
    reviewCount = parseInt(reviewSummary.count, 10);
  }

  return {
    id: workId || (item?.workId != null ? String(item.workId) : ""),
    url,
    name: clean(ld.name) || "",
    description: clean(ld.description),
    medium,
    artist,
    price: Number.isFinite(price) ? price : null,
    priceCurrency: currency,
    availability: shortAvailability(offer.availability),
    images,
    rating: Number.isFinite(ratingValue) ? ratingValue : null,
    reviewCount: Number.isFinite(reviewCount) ? reviewCount : null,
  };
}

export function parseSearch(html) {
  const $ = cheerio.load(html);
  const next = readNextData($);
  const results = next?.props?.pageProps?.results ?? [];
  const items = [];

  for (const row of results) {
    const inv = row?.inventoryItem ?? {};
    const work = inv.work ?? {};
    const url = inv.productPageUrl || (inv.productPageUrls?.url ?? "");
    const { medium, artist, workId } = parsePdpUrl(url);
    const id = workId || (inv.workId != null ? String(inv.workId) : (work.id ?? ""));
    const previews = inv.previewSet?.previews ?? [];
    const image = previews.length ? String(previews[0].url ?? "") || null : null;
    const price = toNumber(inv.price?.amount);
    items.push({
      id: String(id || ""),
      url: url || "",
      name: clean(work.title) || "",
      artist: artist || clean(work.artistUsername) || null,
      medium,
      image,
      price: Number.isFinite(price) ? price : null,
      priceCurrency: inv.price?.currency ?? null,
    });
  }

  if (!items.length) {
    // DOM fallback — pull anchors + nearby price strings.
    $('a[href*="/i/"]').each((_, el) => {
      const href = $(el).attr("href") || "";
      if (!/\/i\/[^/]+\//.test(href)) return;
      const abs = href.startsWith("http") ? href : `https://www.redbubble.com${href}`;
      const { medium, artist, workId } = parsePdpUrl(abs);
      if (!workId) return;
      if (items.find((x) => x.id === workId)) return;
      const card = $(el).closest("div");
      const name = clean(card.find("h3, h2").first().text()) ||
        clean($(el).attr("aria-label")) || "";
      const priceText = clean(card.find('[class*="Price_"]').first().text());
      const price = toNumber(priceText);
      const image = card.find("img").first().attr("src") || null;
      items.push({
        id: workId,
        url: abs,
        name,
        artist,
        medium,
        image: image || null,
        price: Number.isFinite(price) ? price : null,
        priceCurrency: priceText && priceText.includes("$") ? "USD" : null,
      });
    });
  }

  return items;
}

// ---------------- scrape functions ----------------

export async function scrapeProduct(urls) {
  const list = Array.isArray(urls) ? urls : [urls];
  const out = [];
  for (const url of list) {
    const html = await fetchRenderedHtml(url, 'script[type="application/ld+json"]');
    out.push(parseProduct(html, url));
  }
  return out;
}

export async function scrapeSearch(query, maxPages = 1) {
  const base = `https://www.redbubble.com/shop/${encodeURIComponent(query)}`;
  const out = [];
  for (let page = 1; page <= maxPages; page++) {
    const url = page === 1 ? base : `${base}?page=${page}`;
    const html = await fetchRenderedHtml(url, 'script#__NEXT_DATA__');
    out.push(...parseSearch(html));
  }
  return out;
}
