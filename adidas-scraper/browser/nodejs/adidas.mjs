// Adidas scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Surfaces:
//   - scrapeProduct(urls)        -> array of Product dicts (PDP fields lifted from JSON-LD + DOM)
//   - scrapeSearch(url, maxPages) -> array of SearchResult dicts (PLP cards)
//
// Adidas.com is protected by Akamai; retries + Scrapeless's residential
// fingerprinting matter. We ship retries=2 by default.

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

async function fetchRenderedHtml(url, readySelector, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 2 } = {}) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const session = await client().browser.create({ proxyCountry, sessionTTL: DEFAULT_SESSION_TTL });
    let browser;
    try {
      browser = await puppeteer.connect({ browserWSEndpoint: session.browserWSEndpoint });
      const page = await browser.newPage();
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
      if (readySelector) {
        try { await page.waitForSelector(readySelector, { timeout: 20000 }); } catch (_) {}
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

// ---------- JSON-LD helpers ----------

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
      if (!node || typeof node !== "object") continue;
      if (Array.isArray(node["@graph"])) {
        for (const sub of node["@graph"]) {
          if (sub && typeof sub === "object") yield sub;
        }
      } else {
        yield node;
      }
    }
  }
}

function typeMatches(node, wanted) {
  const t = node["@type"];
  if (typeof t === "string") return t === wanted;
  if (Array.isArray(t)) return t.includes(wanted);
  return false;
}

function firstOffer(node) {
  const offers = node?.offers;
  if (Array.isArray(offers) && offers.length) {
    return typeof offers[0] === "object" ? offers[0] : {};
  }
  if (offers && typeof offers === "object") {
    if (Array.isArray(offers.offers) && offers.offers.length) {
      return typeof offers.offers[0] === "object" ? offers.offers[0] : {};
    }
    return offers;
  }
  return {};
}

function aggregateRating(node) {
  const ar = node?.aggregateRating;
  return (ar && typeof ar === "object") ? ar : {};
}

// ---------- parsers ----------

const PRODUCT_ID_RE = /\/([A-Z]{2}\d{4}|[A-Z]{3}\d{2}|[A-Z]{2}\d{3}[A-Z]?|[A-Z]{1,3}\d{3,4})\.html/i;

function extractProductId(url) {
  if (!url) return "";
  const m = url.match(PRODUCT_ID_RE);
  if (m) return m[1].toUpperCase();
  try {
    const u = new URL(url);
    const last = u.pathname.replace(/\/$/, "").split("/").pop() || "";
    return last.replace(/\.html$/i, "");
  } catch { return ""; }
}

function clean(value) {
  if (value == null) return null;
  const v = String(value).replace(/\s+/g, " ").trim();
  return v || null;
}

export function parseProduct(html, url) {
  const $ = cheerio.load(html);

  let ld = {};
  for (const node of iterJsonldNodes($)) {
    if (typeMatches(node, "Product")) { ld = node; break; }
  }

  const offer = firstOffer(ld);
  const rating = aggregateRating(ld);

  let images = [];
  if (typeof ld.image === "string") images = [ld.image];
  else if (Array.isArray(ld.image)) images = ld.image.filter(Boolean).map(String);
  else {
    images = $('meta[property="og:image"]').map((_, el) => $(el).attr("content")).get().filter(Boolean);
  }

  const name = ld.name ? clean(ld.name) : clean($("h1").first().text());
  const description = ld.description
    ? clean(ld.description)
    : clean($('meta[name="description"]').attr("content"));

  const sku = ld.sku || ld.productID || extractProductId(url);

  let brand = "adidas";
  if (ld.brand) {
    brand = typeof ld.brand === "object" ? (ld.brand.name || "adidas") : String(ld.brand);
  }

  let priceValue = null;
  if (offer.price != null) {
    const n = parseFloat(String(offer.price).replace(/,/g, ""));
    priceValue = Number.isFinite(n) ? n : null;
  }

  let availability = offer.availability ?? null;
  if (typeof availability === "string" && availability.includes("/")) {
    availability = availability.split("/").pop();
  }

  return {
    id: String(sku || ""),
    url,
    name: name || "",
    brand: clean(brand) || "adidas",
    description,
    price: priceValue,
    priceCurrency: offer.priceCurrency ?? null,
    availability,
    images,
    rating: rating.ratingValue != null ? parseFloat(rating.ratingValue) : null,
    reviewCount: rating.reviewCount != null ? parseInt(rating.reviewCount, 10) : null,
    category: ld.category ? clean(ld.category) : null,
    color: ld.color ? clean(ld.color) : null,
  };
}

export function parseSearch(html) {
  const $ = cheerio.load(html);
  const items = [];

  for (const node of iterJsonldNodes($)) {
    if (!typeMatches(node, "ItemList")) continue;
    for (const el of node.itemListElement || []) {
      if (!el || typeof el !== "object") continue;
      const item = (el.item && typeof el.item === "object") ? el.item : el;
      const offer = firstOffer(item);
      const url = item.url || el.url || "";
      const sku = item.sku || item.productID || extractProductId(url);
      let priceValue = null;
      if (offer.price != null) {
        const n = parseFloat(String(offer.price).replace(/,/g, ""));
        priceValue = Number.isFinite(n) ? n : null;
      }
      let img = null;
      if (typeof item.image === "string") img = item.image;
      else if (Array.isArray(item.image) && item.image.length) img = String(item.image[0]);
      items.push({
        id: sku ? String(sku) : "",
        url,
        name: item.name || "",
        image: img,
        price: priceValue,
        priceCurrency: offer.priceCurrency ?? null,
      });
    }
    if (items.length) break;
  }

  if (!items.length) {
    $('[data-testid="plp-product-card"], article[data-testid="product-card"]').each((_, el) => {
      const $card = $(el);
      const link = $card.find("a").first().attr("href") || "";
      let absolute = "";
      try { absolute = link ? new URL(link, "https://www.adidas.com").toString() : ""; } catch {}
      const sku = absolute ? extractProductId(absolute) : ($card.attr("data-grid-id") || "");
      const name = clean(
        $card.find('[data-testid="product-card-title"]').first().text() ||
        $card.find("p").first().text()
      );
      const priceText = clean(
        $card.find('[data-testid="primary-price"]').first().text() ||
        $card.find('div[class*="price"]').first().text()
      );
      let priceValue = null;
      if (priceText) {
        const m = priceText.match(/[\d,.]+/);
        if (m) {
          const n = parseFloat(m[0].replace(/,/g, ""));
          priceValue = Number.isFinite(n) ? n : null;
        }
      }
      const img = $card.find("img").first().attr("src") || $card.find("img").first().attr("data-src") || null;
      items.push({
        id: sku || "",
        url: absolute,
        name: name || "",
        image: img,
        price: priceValue,
        priceCurrency: priceText && priceText.includes("$") ? "USD" : null,
      });
    });
  }

  return { results: items };
}

// ---------- URL helpers ----------

function addQuery(url, params) {
  const u = new URL(url);
  for (const [k, v] of Object.entries(params)) u.searchParams.set(k, String(v));
  return u.toString();
}

// ---------- scrape functions ----------

export async function scrapeProduct(urls) {
  const list = Array.isArray(urls) ? urls : [urls];
  const out = [];
  for (const url of list) {
    const html = await fetchRenderedHtml(url, 'script[type="application/ld+json"]');
    out.push(parseProduct(html, url));
  }
  return out;
}

export async function scrapeSearch(url, maxPages = 1) {
  const firstHtml = await fetchRenderedHtml(url, 'script[type="application/ld+json"]');
  const out = [...parseSearch(firstHtml).results];

  const pageSize = 48;
  for (let page = 2; page <= maxPages; page++) {
    const offset = (page - 1) * pageSize;
    const pageUrl = addQuery(url, { start: offset });
    const html = await fetchRenderedHtml(pageUrl, 'script[type="application/ld+json"]');
    out.push(...parseSearch(html).results);
  }
  return out;
}
