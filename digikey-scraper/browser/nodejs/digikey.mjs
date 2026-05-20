// Digi-Key scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Under the hood:
// - `client.browser.create()` mints a cloud session on Scrapeless's Scraping Browser,
//   returning a CDP WebSocket endpoint (`browserWSEndpoint`).
// - puppeteer-core connects to that WebSocket, drives the page, returns rendered HTML.
// - cheerio parses the embedded `#__NEXT_DATA__` JSON payload that ships with every
//   server-rendered Digi-Key page. Both the detail page (`envelope.type ===
//   "detail-page"`) and the keyword-search page (`envelope.type === "result-page"`)
//   expose their data under `props.pageProps.envelope.data`.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 240;
const PRODUCT_BASE = "https://www.digikey.com/en/products/detail";
const SEARCH_BASE = "https://www.digikey.com/en/products/result";

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function fetchRenderedHtml(url, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 2 } = {}) {
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
      await page.setViewport({ width: 1366, height: 800 });
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 90000 });
      // Cloudflare interstitial: wait for the actual __NEXT_DATA__ payload (Digi-Key ships
      // it server-side on every real page). Up to 120 s; the challenge often clears in 5-20 s.
      try { await page.waitForSelector("script#__NEXT_DATA__", { timeout: 120000 }); } catch (_) {}
      const html = await page.content();
      const title = await page.title();
      if (title.includes("Cloudflare") || title.includes("Attention Required") || title.includes("Just a moment")) {
        lastError = new Error(`blocked by Cloudflare (title=${title})`);
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

function extractNextData(html) {
  const $ = cheerio.load(html);
  const raw = $("#__NEXT_DATA__").html();
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function envelopeData(html) {
  const nd = extractNextData(html);
  return nd?.props?.pageProps?.envelope?.data ?? null;
}

// ---------------- product ----------------

export function parseProduct(html, url) {
  const data = envelopeData(html);
  if (!data) throw new Error("could not parse __NEXT_DATA__ from product page");
  const overview = data.productOverview ?? {};
  const pq = data.priceQuantity ?? {};
  const carousel = data.carouselMedia ?? [];
  const breadcrumb = (data.breadcrumb ?? []).map((b) => ({ label: b.label ?? null, url: b.url ?? null }));

  const attrs = data.productAttributes?.attributes ?? [];
  const attributes = attrs.map((a) => ({
    label: a.label ?? null,
    value: (a.values ?? []).map((v) => v.value).filter(Boolean).join(", ") || null,
  }));

  const pricingTiers = pq.pricing?.[0]?.mergedPricingTiers ?? [];
  const pricing = pricingTiers.map((t) => ({
    breakQuantity: t.brkQty ?? null,
    unitPrice: t.unitPrice ?? null,
    extendedPrice: t.extPrice ?? null,
  }));

  const firstPricing = pq.pricing?.[0] ?? {};
  const stock = {
    quantityAvailable: pq.qtyAvailable ?? null,
    hasLeadTime: Boolean(pq.hasLeadTime),
    leadTime: overview.standardLeadTime ?? null,
    minimumOrderQuantity: firstPricing.minOrderQuantity ?? null,
    packaging: firstPricing.packaging ?? null,
  };

  const partStatusAttr = attrs.find((a) => (a.label ?? "").toLowerCase() === "part status");
  const isActive = (partStatusAttr?.values?.[0]?.value ?? "").toLowerCase() === "active";

  const dkValues = overview.digikeyProductNumbers?.value ?? [];
  const digikeyPartNumber = dkValues[0]?.value ?? overview.rolledUpProductNumber ?? "";

  return {
    digikeyPartNumber,
    manufacturerPartNumber: overview.manufacturerProductNumber ?? overview.title ?? "",
    manufacturer: overview.manufacturer ?? "",
    title: overview.title ?? "",
    description: overview.description ?? null,
    detailedDescription: overview.detailedDescription ?? null,
    datasheetUrl: overview.datasheetUrl ?? null,
    productUrl: url,
    imageUrl: carousel[0]?.displayUrl ? `https:${carousel[0].displayUrl.replace(/^https?:/, "")}` : null,
    media: carousel.map((m) => m.displayUrl).filter(Boolean).map((u) => (u.startsWith("//") ? `https:${u}` : u)),
    breadcrumb,
    attributes,
    pricing,
    stock,
    isActive,
    isUnavailable: Boolean(data.isUnavailable),
  };
}

export async function scrapeProduct(productIdOrUrl) {
  const url = productIdOrUrl.startsWith("http")
    ? productIdOrUrl
    : `https://www.digikey.com/en/products/result?keywords=${encodeURIComponent(productIdOrUrl)}`;
  const html = await fetchRenderedHtml(url);
  return parseProduct(html, url);
}

// ---------------- search ----------------

export function parseSearch(html) {
  const data = envelopeData(html);
  if (!data) return [];
  const top = data.topResults ?? [];
  return top.map((r) => ({
    id: String(r.id ?? ""),
    categoryName: r.categoryName ?? "",
    parentCategory: r.parentCategory ?? null,
    productCount: String(r.productCount ?? ""),
    categoryUrl: r.categoryUrl ?? "",
    imageUrl: r.imageUrl ? (r.imageUrl.startsWith("//") ? `https:${r.imageUrl}` : r.imageUrl) : null,
  }));
}

export async function scrapeSearch(query, maxPages = 1) {
  const out = [];
  for (let page = 1; page <= maxPages; page++) {
    const url = `${SEARCH_BASE}?keywords=${encodeURIComponent(query)}${page > 1 ? `&page=${page}` : ""}`;
    const html = await fetchRenderedHtml(url);
    out.push(...parseSearch(html));
  }
  return out;
}
