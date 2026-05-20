// Nordstrom scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
//
// (Folder name keeps the upstream typo "nordstorm" — the site itself is nordstrom.com.)

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

async function fetchRenderedHtml(url, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 1 } = {}) {
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
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
      try {
        await page.waitForFunction(
          "!!document.documentElement.outerHTML.match(/__INITIAL_CONFIG__/)",
          { timeout: 15000 },
        );
      } catch (_) {}
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

// ---------------- helpers ----------------

function nestedLookup(key, obj, out = []) {
  if (obj && typeof obj === "object") {
    for (const k of Object.keys(obj)) {
      if (k === key) out.push(obj[k]);
      nestedLookup(key, obj[k], out);
    }
  }
  return out;
}

export function findHiddenData(html) {
  const $ = cheerio.load(html);
  let raw = "";
  $("script").each((_, el) => {
    const t = $(el).html() ?? "";
    if (t.includes("__INITIAL_CONFIG__")) raw = t;
  });
  if (!raw) throw new Error("__INITIAL_CONFIG__ script not found");
  const after = raw.split("=").slice(1).join("=").trim().replace(/;$/, "");
  return JSON.parse(after);
}

export function updateUrlParameter(url, params) {
  const u = new URL(url);
  for (const [k, v] of Object.entries(params)) u.searchParams.set(k, String(v));
  return u.toString();
}

// ---------------- parsers (verbatim from the upstream reference) ----------------

export function parseProduct(data) {
  const product = {
    id: data.id ?? null,
    title: data.productTitle ?? null,
    type: data.productTypeName ?? null,
    typeParent: data.productTypeParentName ?? null,
    ageGroups: data.ageGroups ?? null,
    reviewAverageRating: data.reviewAverageRating ?? null,
    numberOfReviews: data.numberOfReviews ?? null,
    brand: data.brand ?? null,
    description: data.sellingStatement ?? null,
    features: data.features ?? null,
    gender: data.gender ?? null,
    isAvailable: data.isAvailable ?? null,
  };
  const pricesBySku = data.price ? data.price.bySkuId : null;
  const colorsById = data.filters.color.byId;
  product.media = [];
  for (const item of data.mediaExperiences.carouselsByColor) {
    product.media.push({
      colorCode: item.colorCode ?? null,
      colorName: item.colorName ?? null,
      urls: item.orderedShots.map((i) => i.url),
    });
  }
  product.variants = {};
  for (const [sku, skuData] of Object.entries(data.skus.byId)) {
    const parsed = {
      id: skuData.id ?? null,
      sizeId: skuData.sizeId ?? null,
      colorId: skuData.colorId ?? null,
      totalQuantityAvailable: skuData.totalQuantityAvailable ?? null,
    };
    parsed.price = pricesBySku ? pricesBySku[sku]?.regular?.price ?? null : null;
    const color = colorsById[parsed.colorId];
    parsed.color = color
      ? {
          id: color.id ?? null,
          value: color.value ?? null,
          sizes: color.isAvailableWith ?? null,
          mediaIds: color.styleMediaIds ?? null,
          swatch: color.swatchMedia?.desktop ?? null,
        }
      : null;
    product.variants[sku] = parsed;
  }
  return product;
}

// ---------------- scrape functions ----------------

export async function scrapeProducts(urls) {
  const products = [];
  for (const url of urls) {
    try {
      const html = await fetchRenderedHtml(url);
      const data = findHiddenData(html);
      const stylesById = nestedLookup("stylesById", data);
      const product = Object.values(stylesById[0])[0];
      products.push(parseProduct(product));
    } catch (e) {
      console.error(`product ${url} failed:`, e.message);
    }
  }
  return products;
}

export async function scrapeSearch(url, maxPages = 10) {
  const firstHtml = await fetchRenderedHtml(url);
  const data = findHiddenData(firstHtml);
  const firstResults = nestedLookup("productResults", data)[0];
  const products = Object.values(firstResults.productsById);
  const totalPagesAvail = firstResults.query.pageCount;
  const totalPages = maxPages && maxPages < totalPagesAvail ? maxPages : totalPagesAvail;

  for (let page = 2; page <= totalPages; page++) {
    const pageUrl = updateUrlParameter(url, { page });
    try {
      const html = await fetchRenderedHtml(pageUrl);
      const d = findHiddenData(html);
      const r = nestedLookup("productResults", d)[0];
      products.push(...Object.values(r.productsById));
    } catch (e) {
      console.error(`search page ${page} failed:`, e.message);
    }
  }
  return products;
}
