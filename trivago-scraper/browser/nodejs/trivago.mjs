// Trivago scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Two surfaces:
// - `scrapeSearch(destinationUrl, maxPages)` — parses the JSON-LD `ItemList`
//   that Trivago server-renders on every odr/srl destination page.
// - `scrapeDestination(destinationUrl)` — adds breadcrumb + FAQ context from
//   the same SSR payload.
//
// Trivago is anti-bot-heavy in the DOM (results are progressively loaded via
// GraphQL after JS hydration) but the JSON-LD `ItemList` is rendered server
// side, so we get a stable list of hotels with rating/review data without
// needing to chase the GraphQL XHR.

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
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
      if (readySelector) {
        try { await page.waitForSelector(readySelector, { timeout: 20000 }); } catch (_) {}
      }
      // Trivago's JSON-LD ships server side, but a brief wait lets the SSR
      // module accommodation-list block finish painting too.
      await new Promise((r) => setTimeout(r, 3000));
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

function safeJsonParse(s) {
  try { return JSON.parse(s); } catch (_) { return null; }
}

function extractJsonLdBlocks(html) {
  const $ = cheerio.load(html);
  const blocks = [];
  $("script[type='application/ld+json']").each((_, el) => {
    const raw = $(el).contents().text();
    if (!raw) return;
    const parsed = safeJsonParse(raw);
    if (parsed) blocks.push(parsed);
  });
  return blocks;
}

function findHotelItemList(blocks) {
  for (const b of blocks) {
    if (b && b["@type"] === "ItemList" && Array.isArray(b.itemListElement)) {
      return b;
    }
  }
  return null;
}

function findFaqList(blocks) {
  for (const b of blocks) {
    if (b && b["@type"] === "FAQPage" && Array.isArray(b.mainEntity)) {
      return b.mainEntity.map((q) => ({
        question: q?.name ?? null,
        answer: q?.acceptedAnswer?.text ?? null,
      })).filter((q) => q.question);
    }
  }
  return [];
}

function findBreadcrumbs(blocks) {
  for (const b of blocks) {
    if (b && b["@type"] === "BreadcrumbList" && Array.isArray(b.itemListElement)) {
      return b.itemListElement
        .map((li) => li?.item?.name ?? null)
        .filter((x) => !!x);
    }
  }
  return [];
}

function toNumberOrNull(v) {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : parseFloat(v);
  return Number.isFinite(n) ? n : null;
}

function toIntOrNull(v) {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? Math.round(v) : parseInt(String(v).replace(/,/g, ""), 10);
  return Number.isFinite(n) ? n : null;
}

function mapHotelItem(el) {
  const item = el?.item || el || {};
  const rating = item.aggregateRating || {};
  return {
    position: toIntOrNull(el?.position) ?? 0,
    name: item.name || "",
    url: item.url || "",
    address: item.address || null,
    image: item.image || null,
    description: item.description || null,
    priceRange: item.priceRange || null,
    ratingValue: toNumberOrNull(rating.ratingValue),
    reviewCount: toIntOrNull(rating.reviewCount),
    bestRating: toNumberOrNull(rating.bestRating),
    worstRating: toNumberOrNull(rating.worstRating),
  };
}

// ---------------- search ----------------

export function parseSearch(html) {
  const blocks = extractJsonLdBlocks(html);
  const list = findHotelItemList(blocks);
  if (!list) return [];
  return list.itemListElement
    .filter((el) => el?.item?.["@type"] === "Hotel")
    .map(mapHotelItem)
    .filter((h) => h.name);
}

export async function scrapeSearch(destinationUrl, maxPages = 1, { proxyCountry = DEFAULT_PROXY_COUNTRY } = {}) {
  const out = [];
  for (let page = 1; page <= maxPages; page++) {
    const url = page === 1 ? destinationUrl : appendOffset(destinationUrl, (page - 1) * 25);
    const html = await fetchRenderedHtml(url, "script[type='application/ld+json']", { proxyCountry });
    const items = parseSearch(html);
    if (!items.length && page > 1) break;
    out.push(...items);
  }
  return out;
}

function appendOffset(url, offset) {
  try {
    const u = new URL(url);
    u.searchParams.set("offset", String(offset));
    return u.toString();
  } catch (_) {
    return url + (url.includes("?") ? "&" : "?") + `offset=${offset}`;
  }
}

// ---------------- destination ----------------

export function parseDestination(html, url) {
  const $ = cheerio.load(html);
  const blocks = extractJsonLdBlocks(html);
  const list = findHotelItemList(blocks);
  const breadcrumbs = findBreadcrumbs(blocks);
  const faq = findFaqList(blocks);
  const titleText = $("title").first().text().trim() || "";
  // Best-effort destination name from breadcrumb tail or H1.
  let name = breadcrumbs.length ? breadcrumbs[breadcrumbs.length - 1] : "";
  if (!name) name = $("h1").first().text().trim() || titleText.split("|")[0].trim();
  const totalHotels = list ? toIntOrNull(list.numberOfItems) ?? list.itemListElement.length : null;
  const topHotels = list
    ? list.itemListElement
        .filter((el) => el?.item?.["@type"] === "Hotel")
        .map(mapHotelItem)
        .filter((h) => h.name)
    : [];
  return {
    url,
    name,
    breadcrumbs,
    totalHotels,
    faq,
    topHotels,
  };
}

export async function scrapeDestination(destinationUrl, { proxyCountry = DEFAULT_PROXY_COUNTRY } = {}) {
  const html = await fetchRenderedHtml(destinationUrl, "script[type='application/ld+json']", { proxyCountry });
  return parseDestination(html, destinationUrl);
}
