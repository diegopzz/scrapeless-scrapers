// GameStop scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// GameStop runs on Salesforce Commerce Cloud. Detail pages ship a schema.org
// Product `ld+json` (plus a BreadcrumbList ld+json). Category / search tiles use
// the `.product-tile[data-pid]` markup and stamp a full structured payload into
// the `data-gtmdata` attribute on each tile's primary link.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 240;
const ORIGIN = "https://www.gamestop.com";
const SEARCH_BASE = `${ORIGIN}/search/`;

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

function extractLdJsonBlocks(html) {
  const $ = cheerio.load(html);
  const out = [];
  $('script[type="application/ld+json"]').each((_, el) => {
    const txt = $(el).html();
    if (!txt) return;
    try { out.push(JSON.parse(txt)); } catch (_) {}
  });
  return out;
}

function findByType(blocks, typeName) {
  for (const b of blocks) {
    const t = b?.["@type"];
    if (t === typeName || (Array.isArray(t) && t.includes(typeName))) return b;
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

export function parseProduct(html, url) {
  const blocks = extractLdJsonBlocks(html);
  const prod = findByType(blocks, "Product");
  if (!prod) throw new Error("could not find Product ld+json on page");

  const breadcrumbLd = findByType(blocks, "BreadcrumbList");
  const breadcrumb = (breadcrumbLd?.itemListElement ?? []).map((b) => ({
    name: b?.name ?? null,
    url: b?.item ?? null,
    position: b?.position ?? null,
  }));

  const offersRaw = Array.isArray(prod.offers) ? prod.offers : (prod.offers ? [prod.offers] : []);
  const offers = offersRaw.map((o) => ({
    name: o?.name ?? null,
    sku: o?.sku != null ? String(o.sku) : null,
    price: o?.price != null ? String(o.price) : null,
    priceCurrency: o?.priceCurrency ?? null,
    availability: o?.availability ?? null,
  }));
  const firstOffer = offers[0] ?? {};

  // id: try the `productid` meta or the URL trailing /<id>.html
  const $ = cheerio.load(html);
  let id = $("[data-product-id]").first().attr("data-product-id") || "";
  if (!id) {
    const m = url.match(/\/(\d+)\.html/);
    if (m) id = m[1];
  }

  return {
    id: String(id),
    name: prod.name ?? "",
    brand: prod.brand ?? null,
    description: prod.description ?? null,
    platform: prod.gamePlatform ?? null,
    category: prod.category ?? null,
    genre: prod.genre ?? null,
    contentRating: prod.contentRating ?? null,
    producer: prod.producer ?? null,
    publisher: prod.publisher ?? null,
    image: prod.image ?? null,
    url: prod.url ?? url,
    price: firstOffer.price ?? null,
    priceCurrency: firstOffer.priceCurrency ?? null,
    availability: firstOffer.availability ?? null,
    offers,
    breadcrumb,
  };
}

export async function scrapeProduct(productUrl) {
  const url = productUrl.startsWith("http") ? productUrl : `${ORIGIN}${productUrl.startsWith("/") ? "" : "/"}${productUrl}`;
  const html = await fetchRenderedHtml(url, 'script[type="application/ld+json"]');
  return parseProduct(html, url);
}

// ---------------- search ----------------

function parseGtmData(raw) {
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

export function parseSearch(html) {
  const $ = cheerio.load(html);
  const out = [];
  $(".product-tile").each((_, el) => {
    const $t = $(el);
    const id = $t.attr("data-pid") || $t.attr("id") || "";
    const a = $t.find("a.pdp-link, a.product-tile-link").first();
    const gtm = parseGtmData(a.attr("data-gtmdata") || "");
    let url = a.attr("href") || "";
    if (url && !url.startsWith("http")) url = abs(url);
    const name = gtm?.name ?? a.attr("aria-label") ?? a.attr("title") ?? "";
    if (!id || !url || !name) return;
    const platforms = Array.isArray(gtm?.productPlatform) ? gtm.productPlatform : [];
    out.push({
      id: String(id),
      name,
      url,
      price: gtm?.price?.base != null ? String(gtm.price.base) : null,
      salePrice: gtm?.price?.sale != null ? String(gtm.price.sale) : null,
      platform: platforms[0] ?? null,
      image: gtm?.image?.base ?? null,
      ratingPercent: gtm?.ratings?.percentage != null ? String(gtm.ratings.percentage) : null,
      ratingCount: gtm?.ratings?.count != null ? String(gtm.ratings.count) : null,
      available: gtm?.availability?.available ?? null,
      isDigital: gtm?.availability?.isDigitalProduct ?? null,
    });
  });
  return out;
}

export async function scrapeSearch(query, maxPages = 1) {
  const out = [];
  for (let page = 1; page <= maxPages; page++) {
    const url = `${SEARCH_BASE}?q=${encodeURIComponent(query)}${page > 1 ? `&start=${(page - 1) * 20}&sz=20` : ""}`;
    const html = await fetchRenderedHtml(url, ".product-tile");
    out.push(...parseSearch(html));
  }
  return out;
}

export async function scrapeCategory(categoryUrl) {
  const url = categoryUrl.startsWith("http") ? categoryUrl : `${ORIGIN}${categoryUrl.startsWith("/") ? "" : "/"}${categoryUrl}`;
  const html = await fetchRenderedHtml(url, ".product-tile");
  return parseSearch(html);
}
