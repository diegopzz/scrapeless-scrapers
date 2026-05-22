// MercadoLibre scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Surfaces:
//   - scrapeProduct(url)         -> Product dict (fields lifted from schema.org ld+json)
//   - scrapeSearch(url, maxPages) -> array of SearchResult dicts (PLP cards)
//
// Product pages at articulo.mercadolibre.com.mx/MLM-<id> ship a schema.org Product ld+json
// blob plus a BreadcrumbList ld+json. Search/listing pages at listado.mercadolibre.com.mx/<query>
// render result cards in li[class*="ui-search-layout__item"]; ld+json carries only FAQPage so
// we extract from DOM.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "MX";
const DEFAULT_SESSION_TTL = 300;
const ORIGIN = "https://www.mercadolibre.com.mx";

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function fetchRenderedHtml(url, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 2, settleMs = 6000 } = {}) {
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
      await page.setExtraHTTPHeaders({ "accept-language": "es-MX,es;q=0.9" });
      await page.setViewport({ width: 1280, height: 900 });
      // Use load to handle ML's client-side redirect from micro-landing to product page
      await page.goto(url, { waitUntil: "load", timeout: 90000 });
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
    try { out.push(JSON.parse(txt)); } catch (_) {}
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

  const breadcrumbLd = findByType(blocks, "BreadcrumbList");
  const breadcrumb = (breadcrumbLd?.itemListElement ?? []).map(b => {
    // ML uses item.name + item["@id"] (not top-level name/item)
    const item = (b?.item && typeof b.item === "object") ? b.item : null;
    return {
      name: item?.name ?? b?.name ?? null,
      url: item?.["@id"] ?? (typeof b?.item === "string" ? b.item : null),
      position: b?.position ?? null,
    };
  });

  const offer = Array.isArray(prod.offers) ? prod.offers[0] : (prod.offers ?? {});
  const rating = prod.aggregateRating ?? {};

  let image = prod.image;
  if (Array.isArray(image)) image = image[0] ?? null;

  return {
    id: String(prod.sku ?? ""),
    name: prod.name ?? "",
    brand: prod.brand ? String(prod.brand) : null,
    description: prod.description ?? null,
    image: image ?? null,
    price: offer.price != null ? Number(offer.price) : null,
    priceCurrency: offer.priceCurrency ?? null,
    availability: offer.availability ?? null,
    ratingValue: rating.ratingValue != null ? Number(rating.ratingValue) : null,
    reviewCount: rating.reviewCount != null ? Number(rating.reviewCount) : null,
    url: prod.url ?? url,
    breadcrumb,
  };
}

export async function scrapeProduct(productUrl) {
  const url = productUrl.startsWith("http") ? productUrl : `${ORIGIN}${productUrl.startsWith("/") ? "" : "/"}${productUrl}`;
  const html = await fetchRenderedHtml(url, { settleMs: 6000 });
  return parseProduct(html, url);
}

// ---------- search ----------

const MLM_ID_RE = /\/(MLM[\d]+)/i;

function extractMlmId(url) {
  const m = url.match(MLM_ID_RE);
  return m ? m[1] : "";
}

function parsePrice(text) {
  if (!text) return null;
  // Take only the first numeric value (price fraction may contain "24 meses de $..." suffix)
  const m = text.match(/\$?([\d,.]+)/);
  if (!m) return null;
  const n = parseFloat(m[1].replace(/,/g, ""));
  return Number.isFinite(n) ? n : null;
}

export function parseSearch(html) {
  const $ = cheerio.load(html);
  const items = [];

  $('li[class*="ui-search-layout__item"]').each((_, el) => {
    const $el = $(el);
    // Title
    const name = ($el.find('[class*="poly-component__title"]').first().text() ||
                  $el.find('h2').first().text()).trim();
    // URL from anchor with MLM
    const rawLink = $el.find('a[href*="/MLM-"]').first().attr("href") || "";
    const url = rawLink ? rawLink.split("?")[0] : null;
    const id = url ? extractMlmId(url) : "";
    // Image
    const image = $el.find("img").first().attr("src") ||
                  $el.find("img").first().attr("data-src") || null;
    // Price: fraction text is the whole-number part of the price
    const priceText = $el.find('[class*="price__fraction"]').first().text().trim() ||
                      $el.find('[class*="andes-money-amount__fraction"]').first().text().trim();
    const price = parsePrice(priceText);

    if (name || url) {
      items.push({ id, name, url, image, price, priceCurrency: "MXN" });
    }
  });

  return { results: items };
}

export async function scrapeSearch(searchUrl, maxPages = 1) {
  const firstHtml = await fetchRenderedHtml(searchUrl, { settleMs: 5000 });
  const out = [...parseSearch(firstHtml).results];

  // MercadoLibre pagination: ?from=48 (page 2 = 48, page 3 = 96, …)
  const pageSize = 48;
  for (let page = 2; page <= maxPages; page++) {
    const u = new URL(searchUrl);
    u.searchParams.set("from", String((page - 1) * pageSize));
    const html = await fetchRenderedHtml(u.toString(), { settleMs: 5000 });
    out.push(...parseSearch(html).results);
  }

  return out;
}
