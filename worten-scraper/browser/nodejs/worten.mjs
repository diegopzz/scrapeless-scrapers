// Worten scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Worten ships every `/produtos/<slug>-<id>` page with a schema.org Product `ld+json`
// blob plus a BreadcrumbList ld+json. Category landing pages (`/promocoes/...`,
// `/informatica-e-acessorios/...`) are SSR'd shells: product tiles render later via
// Constructor.io + Turnstile, so we capture the breadcrumb / heading / meta only.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "PT";
const DEFAULT_SESSION_TTL = 240;
const ORIGIN = "https://www.worten.pt";

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function fetchRenderedHtml(url, readySelector, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 2, settleMs = 5000 } = {}) {
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
      await page.setExtraHTTPHeaders({ "accept-language": "pt-PT,pt;q=0.9,en;q=0.5" });
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

function findProductLd(blocks) {
  for (const b of blocks) {
    const t = String(b?.["@type"] ?? "").toLowerCase();
    if (t === "product") return b;
  }
  return null;
}

function findBreadcrumbLd(blocks) {
  for (const b of blocks) {
    if (b?.["@type"] === "BreadcrumbList") return b;
  }
  return null;
}

function absUrl(u) {
  if (!u) return null;
  if (u.startsWith("//")) return `https:${u}`;
  if (u.startsWith("/")) return `${ORIGIN}${u}`;
  return u;
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

  const offer = Array.isArray(prod.offers) ? prod.offers[0] : prod.offers;
  const rating = prod.aggregateRating;

  return {
    sku: String(prod.sku ?? ""),
    name: prod.name ?? "",
    brand: prod.brand?.name ?? null,
    description: prod.description ?? null,
    image: absUrl(typeof prod.image === "string" ? prod.image : prod.image?.[0]),
    price: offer?.price != null ? String(offer.price) : null,
    priceCurrency: offer?.priceCurrency ?? null,
    availability: offer?.availability ?? null,
    ratingValue: rating?.ratingValue != null ? Number(rating.ratingValue) : null,
    reviewCount: rating?.reviewCount != null ? Number(rating.reviewCount) : null,
    url: absUrl(prod.url) ?? url,
    breadcrumb,
  };
}

export async function scrapeProduct(productUrl) {
  const url = productUrl.startsWith("http") ? productUrl : `${ORIGIN}${productUrl.startsWith("/") ? "" : "/"}${productUrl}`;
  const html = await fetchRenderedHtml(url, 'script[type="application/ld+json"]');
  return parseProduct(html, url);
}

// ---------------- category ----------------

export function parseCategory(html, url) {
  const $ = cheerio.load(html);
  const blocks = extractLdJsonBlocks(html);
  const breadcrumbLd = findBreadcrumbLd(blocks);
  const breadcrumb = (breadcrumbLd?.itemListElement ?? []).map((b) => ({
    name: b?.name ?? null,
    url: b?.item ?? null,
    position: b?.position ?? null,
  }));
  return {
    name: $("h1").first().text().trim(),
    title: $("title").text().trim() || null,
    description: $("meta[name='description']").attr("content") ?? null,
    url,
    breadcrumb,
  };
}

export async function scrapeCategory(categoryUrl) {
  const url = categoryUrl.startsWith("http") ? categoryUrl : `${ORIGIN}${categoryUrl.startsWith("/") ? "" : "/"}${categoryUrl}`;
  const html = await fetchRenderedHtml(url, "h1");
  return parseCategory(html, url);
}
