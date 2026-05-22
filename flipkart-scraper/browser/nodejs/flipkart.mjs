// Flipkart scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Surfaces:
//   - scrapeProduct(url)         -> Product dict (fields lifted from schema.org ld+json)
//   - scrapeSearch(url, maxPages) -> array of SearchResult dicts (PLP cards)
//
// Product pages at www.flipkart.com/<slug>/p/<id> ship a schema.org Product ld+json
// array (dynamically injected) after ~12 s of JS hydration. The ld+json contains name,
// sku, brand, description, image[], offers (price, priceCurrency, availability) and
// aggregateRating. No BreadcrumbList is present, so breadcrumb is always [].
//
// Search pages at www.flipkart.com/search?q=<query> render product cards as
// [data-id] elements; the name lives in .RG5Slk (img alt fallback), price in .hZ3P6w,
// rating in .MKiFS6 and the product link in a[href*="/p/"].

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "IN";
const DEFAULT_SESSION_TTL = 300;
const ORIGIN = "https://www.flipkart.com";

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function fetchRenderedHtml(url, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 2, settleMs = 12000 } = {}) {
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
      await page.setExtraHTTPHeaders({ "accept-language": "en-IN,en;q=0.9" });
      await page.setViewport({ width: 1366, height: 900 });
      await page.goto(url, { waitUntil: "load", timeout: 90000 });
      // Flipkart requires ~12 s for JS hydration to inject ld+json and render price
      if (settleMs > 0) await new Promise(r => setTimeout(r, settleMs));
      const html = await page.content();
      if (html && html.length > 10000) return html;
      lastError = new Error(`short HTML len=${html?.length}`);
    } catch (e) {
      lastError = e;
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
  }
  throw new Error(`giving up after ${retries + 1} attempts: ${lastError?.message}`);
}

// ---------- ld+json helpers ----------

function extractLdJsonBlocks(html) {
  const $ = cheerio.load(html);
  const out = [];
  $('script[type="application/ld+json"]').each((_, el) => {
    const txt = $(el).html();
    if (!txt) return;
    try {
      const parsed = JSON.parse(txt);
      // Flipkart wraps the Product in a top-level array
      if (Array.isArray(parsed)) out.push(...parsed);
      else out.push(parsed);
    } catch (_) {}
  });
  return out;
}

function findByType(blocks, type) {
  return blocks.find(b => String(b?.["@type"] ?? "").toLowerCase() === type.toLowerCase()) ?? null;
}

// ---------- product ----------

export function parseProduct(html, url) {
  const blocks = extractLdJsonBlocks(html);
  const prod = findByType(blocks, "Product");
  if (!prod) throw new Error("could not find Product ld+json on page");

  // Flipkart does not ship a BreadcrumbList ld+json block
  const breadcrumb = [];

  const offer = Array.isArray(prod.offers) ? prod.offers[0] : (prod.offers ?? {});
  const rating = prod.aggregateRating ?? {};

  let image = prod.image;
  if (Array.isArray(image)) image = image[0] ?? null;

  return {
    id: String(prod.sku ?? ""),
    name: prod.name ?? "",
    brand: prod.brand?.name ?? (typeof prod.brand === "string" ? prod.brand : null),
    description: prod.description ?? null,
    image: image ?? null,
    price: offer.price != null ? Number(offer.price) : null,
    priceCurrency: offer.priceCurrency ?? "INR",
    availability: offer.availability ?? null,
    ratingValue: rating.ratingValue != null ? Number(rating.ratingValue) : null,
    reviewCount: rating.reviewCount != null ? Number(rating.reviewCount) : null,
    url: url,
    breadcrumb,
  };
}

export async function scrapeProduct(productUrl) {
  const url = productUrl.startsWith("http") ? productUrl : `${ORIGIN}${productUrl.startsWith("/") ? "" : "/"}${productUrl}`;
  const html = await fetchRenderedHtml(url, { settleMs: 12000 });
  return parseProduct(html, url);
}

// ---------- search ----------

export function parseSearch(html) {
  const $ = cheerio.load(html);
  const items = [];

  $("[data-id]").each((_, el) => {
    const $el = $(el);
    const id = $el.attr("data-id") || "";

    // Product link — take path only and strip tracking params
    const link = $el.find('a[href*="/p/"]').first();
    const href = link.attr("href") || "";
    const url = href ? `${ORIGIN}${href.split("?")[0]}` : null;

    // Name: .RG5Slk is the current product title class; img alt is the fallback
    const name = (
      $el.find(".RG5Slk").first().text() ||
      $el.find("img").first().attr("alt") || ""
    ).trim();

    // Image
    const image = $el.find("img").first().attr("src") || null;

    // Price: .hZ3P6w holds the formatted price (e.g. "₹69,900")
    const priceText = $el.find(".hZ3P6w").first().text().trim();
    const priceMatch = priceText.match(/[\d,]+/);
    const price = priceMatch ? parseInt(priceMatch[0].replace(/,/g, ""), 10) : null;

    // Rating: .MKiFS6 holds the numeric rating (e.g. "4.6")
    const ratingText = $el.find(".MKiFS6").first().text().trim();
    const ratingValue = ratingText ? parseFloat(ratingText) : null;

    if (id && (name || url)) {
      items.push({ id, name, url, image, price, priceCurrency: "INR", ratingValue });
    }
  });

  return { results: items };
}

export async function scrapeSearch(searchUrl, maxPages = 1) {
  const firstHtml = await fetchRenderedHtml(searchUrl, { settleMs: 6000 });
  const out = [...parseSearch(firstHtml).results];

  // Flipkart search pagination: &page=2, &page=3, …
  for (let page = 2; page <= maxPages; page++) {
    const u = new URL(searchUrl);
    u.searchParams.set("page", String(page));
    const html = await fetchRenderedHtml(u.toString(), { settleMs: 6000 });
    out.push(...parseSearch(html).results);
  }

  return out;
}
