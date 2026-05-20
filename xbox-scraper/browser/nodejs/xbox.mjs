// Xbox scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// xbox.com store pages ship a single `application/ld+json` script that wraps
// every node under `@graph`. The Product/VideoGame entry inside it carries the
// full structured payload (offers, ratings, videos, ESRB rating). The /games
// hub pages (e.g. /en-us/games/all-games) render game tiles as simple
// `<a href="/games/store/<slug>/<storeId>">` anchors that we lift directly
// from the SSR HTML.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 240;
const ORIGIN = "https://www.xbox.com";
const ALL_GAMES_PATH = "/en-us/games/all-games";

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function fetchRenderedHtml(url, readySelector, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 2, settleMs = 4000 } = {}) {
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
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 90000 });
      if (readySelector) {
        try { await page.waitForSelector(readySelector, { timeout: 45000 }); } catch (_) {}
      }
      if (settleMs > 0) await new Promise(r => setTimeout(r, settleMs));
      const html = await page.content();
      if (html && html.length > 5000) return html;
      lastError = new Error(`empty/short HTML len=${html?.length}`);
    } catch (e) {
      lastError = e;
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
  }
  throw new Error(`giving up after ${retries + 1} attempts: ${lastError?.message}`);
}

function extractLdGraph(html) {
  const $ = cheerio.load(html);
  const out = [];
  $('script[type="application/ld+json"]').each((_, el) => {
    const txt = $(el).html();
    if (!txt) return;
    try {
      const obj = JSON.parse(txt);
      if (Array.isArray(obj["@graph"])) out.push(...obj["@graph"]);
      else out.push(obj);
    } catch (_) {}
  });
  return out;
}

function findProductNode(graph) {
  for (const n of graph) {
    const t = n?.["@type"];
    if (t === "Product" || (Array.isArray(t) && t.includes("Product"))) return n;
  }
  return null;
}

function abs(u) {
  if (!u) return null;
  if (u.startsWith("//")) return `https:${u}`;
  if (u.startsWith("/")) return `${ORIGIN}${u}`;
  return u;
}

// ---------------- product ----------------

const STORE_ID_RE = /\/games\/store\/[^/]+\/([A-Za-z0-9]+)/;

export function parseProduct(html, url) {
  const graph = extractLdGraph(html);
  const prod = findProductNode(graph);
  if (!prod) throw new Error("could not find Product node in ld+json @graph");

  const idMatch = url.match(STORE_ID_RE);
  const id = idMatch ? idMatch[1] : "";

  const offersRaw = Array.isArray(prod.offers) ? prod.offers : (prod.offers ? [prod.offers] : []);
  const firstOffer = offersRaw[0] ?? {};

  const images = Array.isArray(prod.image) ? prod.image : (prod.image ? [prod.image] : []);
  const videosRaw = Array.isArray(prod.video) ? prod.video : (prod.video ? [prod.video] : []);
  const videos = videosRaw.map((v) => ({
    name: v?.name ?? null,
    thumbnailUrl: v?.thumbnailUrl ?? null,
    contentUrl: v?.contentUrl ?? null,
  }));

  const rating = prod.aggregateRating ?? {};

  return {
    id,
    name: prod.name ?? "",
    description: prod.description ?? null,
    url: prod.url ?? url,
    image: images[0] ?? null,
    publisher: prod.publisher?.name ?? null,
    developer: prod.creator?.name ?? null,
    brand: prod.brand?.name ?? null,
    genre: Array.isArray(prod.genre) ? prod.genre : (prod.genre ? [prod.genre] : []),
    platforms: Array.isArray(prod.gamePlatform) ? prod.gamePlatform : (prod.gamePlatform ? [prod.gamePlatform] : []),
    contentRating: prod.contentRating ?? null,
    releaseDate: prod.datePublished ?? null,
    ratingValue: rating.ratingValue != null ? Number(rating.ratingValue) : null,
    ratingCount: rating.ratingCount != null ? Number(rating.ratingCount) : null,
    price: firstOffer.price != null ? String(firstOffer.price) : null,
    priceCurrency: firstOffer.priceCurrency ?? null,
    availability: firstOffer.availability ?? null,
    isFree: prod.isAccessibleForFree ?? null,
    featureList: prod.featureList ?? null,
    videos,
  };
}

export async function scrapeProduct(productUrl) {
  const url = productUrl.startsWith("http") ? productUrl : `${ORIGIN}${productUrl.startsWith("/") ? "" : "/"}${productUrl}`;
  const html = await fetchRenderedHtml(url, 'script[type="application/ld+json"]');
  return parseProduct(html, url);
}

// ---------------- search ----------------

const TILE_RE = /\/games\/store\/([^/?#]+)\/([A-Za-z0-9]{6,})/i;

function aria_to_parts(label) {
  if (!label) return { name: null, badge: null };
  // Pattern: "BADGE. Name. Description... Opens in a new tab"
  // Strip the trailing "Opens in a new tab"
  const cleaned = label.replace(/\.\s*Opens in a new tab\s*$/i, "").trim();
  const parts = cleaned.split(". ");
  if (parts.length >= 2 && /^[A-Z0-9 +!&'-]+$/.test(parts[0])) {
    return { badge: parts[0].trim(), name: parts[1].trim() };
  }
  return { badge: null, name: parts[0]?.trim() ?? null };
}

export function parseSearch(html) {
  const $ = cheerio.load(html);
  const seen = new Set();
  const out = [];
  $("a[href*='/games/store/']").each((_, el) => {
    const $a = $(el);
    let href = $a.attr("href") || "";
    const m = href.match(TILE_RE);
    if (!m) return;
    // Skip top-nav promo links that point to game-pass with `?icid=CNav...`
    if (href.includes("?icid=CNav")) return;
    const id = m[2];
    if (seen.has(id)) return;
    seen.add(id);

    if (!href.startsWith("http")) href = abs(href);

    const aria = $a.attr("aria-label") || "";
    const innerTitle =
      $a.find("h3, h2, span.c-meta-h3").first().text().trim() ||
      $a.find("[class*='title' i], [class*='Title']").first().text().trim() ||
      "";

    const { badge, name } = aria_to_parts(aria);
    const finalName = innerTitle || name || m[1].replace(/-/g, " ");
    if (!finalName) return;

    const img = $a.find("img").attr("src") || $a.parent().find("img").attr("src") || null;

    out.push({
      id,
      slug: m[1],
      name: finalName,
      url: href,
      image: img,
      badge: badge,
    });
  });
  return out;
}

export async function scrapeSearch(query, maxPages = 1) {
  // Xbox.com doesn't ship a true search SERP; /games/all-games is the discovery
  // hub. We support a `query` only as a label; pagination is honored when the
  // hub renders it as `?page=N` (newer iterations of the all-games index).
  const out = [];
  const _ = query; // kept for API parity
  for (let page = 1; page <= maxPages; page++) {
    const url = `${ORIGIN}${ALL_GAMES_PATH}${page > 1 ? `?page=${page}` : ""}`;
    const html = await fetchRenderedHtml(url, "a[href*='/games/store/']");
    out.push(...parseSearch(html));
  }
  return out;
}
