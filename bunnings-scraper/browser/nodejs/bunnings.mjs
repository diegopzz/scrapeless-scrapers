// Bunnings scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Bunnings ships every product page with a schema.org `ld+json` Product blob plus a
// BreadcrumbList ld+json. The keyword search page is a Coveo SPA, so the result tiles
// (`[data-testid="productTileContainer"]`) are parsed after the front-end renders.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "AU";
const DEFAULT_SESSION_TTL = 240;
const ORIGIN = "https://www.bunnings.com.au";
const SEARCH_BASE = `${ORIGIN}/search/products`;

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function fetchRenderedHtml(url, readySelector, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 2, settleMs = 6000 } = {}) {
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
        try { await page.waitForSelector(readySelector, { timeout: 60000 }); } catch (_) {}
      }
      if (settleMs > 0) await new Promise(r => setTimeout(r, settleMs));
      const html = await page.content();
      const title = await page.title();
      if (title.includes("Access Denied") || title.includes("Cloudflare") || html.length < 5000) {
        lastError = new Error(`blocked (title=${title}, len=${html.length})`);
        continue;
      }
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

function extractLdJsonBlocks(html) {
  const $ = cheerio.load(html);
  const out = [];
  $('script[type="application/ld+json"]').each((_, el) => {
    const txt = $(el).html();
    if (!txt) return;
    try { out.push(JSON.parse(txt)); } catch (_) { /* skip malformed */ }
  });
  return out;
}

function findProductLd(blocks) {
  for (const b of blocks) {
    const t = b?.["@type"];
    if (t === "Product" || (Array.isArray(t) && t.includes("Product"))) return b;
  }
  return null;
}

function findBreadcrumbLd(blocks) {
  for (const b of blocks) {
    if (b?.["@type"] === "BreadcrumbList") return b;
  }
  return null;
}

// ---------------- product ----------------

export function parseProduct(html, url) {
  const blocks = extractLdJsonBlocks(html);
  const prod = findProductLd(blocks);
  if (!prod) throw new Error("could not find Product ld+json on page");

  const breadcrumbLd = findBreadcrumbLd(blocks);
  const breadcrumb = (breadcrumbLd?.itemListElement ?? []).map((b) => ({
    name: b?.name ?? null,
    url: b?.item ?? null,
    position: b?.position ?? null,
  }));

  let warranty = null;
  const ap = prod.additionalProperty;
  if (ap) {
    const list = Array.isArray(ap) ? ap : [ap];
    const w = list.find((p) => (p?.name ?? "").toLowerCase().includes("warranty"));
    if (w) warranty = w.value ?? null;
  }

  const offer = Array.isArray(prod.offers) ? prod.offers[0] : prod.offers;

  return {
    sku: String(prod.sku ?? ""),
    name: prod.name ?? "",
    brand: prod.brand?.name ?? null,
    brandLogo: prod.brand?.logo ?? null,
    description: prod.description ?? null,
    category: prod.category ?? null,
    image: prod.image ?? null,
    price: offer?.price ? String(offer.price) : null,
    priceCurrency: offer?.priceCurrency ?? null,
    url: prod.url ?? url,
    warranty,
    breadcrumb,
  };
}

export async function scrapeProduct(productUrl) {
  const url = productUrl.startsWith("http") ? productUrl : `${ORIGIN}${productUrl.startsWith("/") ? "" : "/"}${productUrl}`;
  const html = await fetchRenderedHtml(url, 'script[type="application/ld+json"]');
  return parseProduct(html, url);
}

// ---------------- search ----------------

export function parseSearch(html) {
  const $ = cheerio.load(html);
  const out = [];
  $("[data-testid='productTileContainer']").each((_, el) => {
    const $t = $(el);
    const a = $t.find("a").first();
    let href = a.attr("href") ?? "";
    if (href && !href.startsWith("http")) href = `${ORIGIN}${href.startsWith("/") ? "" : "/"}${href}`;
    const m = href.match(/_p(\d+)/);
    const sku = m ? m[1] : "";
    const title = $t.find(".product-title").first().text().trim() || a.attr("title") || "";
    const price = $t.find("[data-testid='price-link']").first().text().trim() || null;
    const image = $t.find("img.product-tile-image").attr("src") || null;
    const rating = $t.find("[role='img'][aria-label*='Rating']").attr("aria-label") || null;
    if (!title || !href) return;
    out.push({ sku, title, url: href, price, image, rating });
  });
  return out;
}

export async function scrapeSearch(query, maxPages = 1) {
  const out = [];
  for (let page = 1; page <= maxPages; page++) {
    const url = `${SEARCH_BASE}?q=${encodeURIComponent(query)}${page > 1 ? `&page=${page}` : ""}`;
    const html = await fetchRenderedHtml(url, "[data-testid='productTileContainer']");
    out.push(...parseSearch(html));
  }
  return out;
}
