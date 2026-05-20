// Zara scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Surfaces:
//   - scrapeProduct(urls)         -> array of Product dicts (PDP fields from JSON-LD + DOM)
//   - scrapeSearch(url, maxPages) -> array of SearchResult dicts (PLP cards)
//
// Zara.com is Cloudflare-fronted; Scrapeless's residential fingerprinting handles
// the JS challenge transparently.

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
  if (Array.isArray(offers) && offers.length) return typeof offers[0] === "object" ? offers[0] : {};
  if (offers && typeof offers === "object") {
    if (Array.isArray(offers.offers) && offers.offers.length) return typeof offers.offers[0] === "object" ? offers.offers[0] : {};
    return offers;
  }
  return {};
}

function clean(value) {
  if (value == null) return null;
  const v = String(value).replace(/\s+/g, " ").trim();
  return v || null;
}

const PRODUCT_ID_RE = /-p(\d+)\.html/i;

function extractProductId(url) {
  if (!url) return "";
  const m = url.match(PRODUCT_ID_RE);
  if (m) return m[1];
  try {
    const u = new URL(url);
    return u.pathname.replace(/\/$/, "").split("/").pop().replace(/\.html$/i, "");
  } catch { return ""; }
}

// ---------- parsers ----------

export function parseProduct(html, url) {
  const $ = cheerio.load(html);

  let ld = {};
  for (const node of iterJsonldNodes($)) {
    if (typeMatches(node, "Product")) { ld = node; break; }
  }

  const offer = firstOffer(ld);

  let images = [];
  if (typeof ld.image === "string") images = [ld.image];
  else if (Array.isArray(ld.image)) images = ld.image.filter(Boolean).map(String);
  else images = $('meta[property="og:image"]').map((_, el) => $(el).attr("content")).get().filter(Boolean);

  const name = ld.name
    ? clean(ld.name)
    : clean($('meta[property="og:title"]').attr("content")) || clean($("h1").first().text());

  const description = ld.description
    ? clean(ld.description)
    : clean($('meta[name="description"]').attr("content"));

  const sku = ld.sku || ld.productID || extractProductId(url);

  let brand = "ZARA";
  if (ld.brand) {
    brand = typeof ld.brand === "object" ? (ld.brand.name || "ZARA") : String(ld.brand);
  }

  let rawPrice = offer.price ?? clean($('meta[property="product:price:amount"]').attr("content"));
  let priceValue = null;
  if (rawPrice != null) {
    const n = parseFloat(String(rawPrice).replace(/,/g, ""));
    priceValue = Number.isFinite(n) ? n : null;
  }
  let currency = offer.priceCurrency ?? clean($('meta[property="product:price:currency"]').attr("content"));

  let availability = offer.availability ?? null;
  if (typeof availability === "string" && availability.includes("/")) {
    availability = availability.split("/").pop();
  }

  let color = ld.color ?? null;
  if (!color) {
    color = clean($('[data-qa-qualifier="product-detail-color"]').first().text()
                  || $('p.product-detail-info__color').first().text());
  }

  return {
    id: sku ? String(sku) : "",
    url,
    name: clean(name) || "",
    brand: clean(brand) || "ZARA",
    description,
    price: priceValue,
    priceCurrency: currency,
    availability,
    images,
    color: typeof color === "string" ? clean(color) : null,
    category: ld.category ? clean(ld.category) : null,
  };
}

export function parseSearch(html) {
  const $ = cheerio.load(html);

  // Build a name -> product URL map from DOM anchors, since Zara's ItemList JSON-LD
  // omits per-item URLs.
  const urlByName = new Map();
  $('a[href*="-p0"][href$=".html"], a[href*="-p1"][href$=".html"]').each((_, el) => {
    const $a = $(el);
    const href = $a.attr("href") || "";
    if (!href) return;
    let absolute = "";
    try { absolute = new URL(href, "https://www.zara.com").toString(); } catch { return; }
    const label = clean($a.attr("aria-label")) || clean($a.text());
    if (label && !urlByName.has(label.toUpperCase())) {
      urlByName.set(label.toUpperCase(), absolute);
    }
    // Also index by the image basename (product id appears in image URLs)
    const img = $a.find("img").attr("src") || $a.find("img").attr("data-src");
    if (img) {
      const m = img.match(/\/(\d{8,11})/);
      if (m) {
        const pid8 = m[1].slice(0, 8);
        if (!urlByName.has(`PID:${pid8}`)) urlByName.set(`PID:${pid8}`, absolute);
      }
    }
  });

  const items = [];

  for (const node of iterJsonldNodes($)) {
    if (!typeMatches(node, "ItemList")) continue;
    for (const el of node.itemListElement || []) {
      if (!el || typeof el !== "object") continue;
      const item = (el.item && typeof el.item === "object") ? el.item : el;
      const offer = firstOffer(item);
      const name = clean(item.name) || "";
      // Zara now ships per-item URL inside the offer (`offer.url`); fall back to
      // the legacy `item.url` / `el.url` slots, and finally to a DOM lookup.
      let url = offer?.url || item.url || el.url || "";
      let image = item.image;
      if (Array.isArray(image) && image.length) image = String(image[0]);
      else if (typeof image !== "string") image = null;

      // Look up missing URL via DOM index
      if (!url && name) url = urlByName.get(name.toUpperCase()) || "";
      if (!url && image) {
        const m = image.match(/\/(\d{8,11})/);
        if (m) url = urlByName.get(`PID:${m[1].slice(0, 8)}`) || "";
      }

      const sku = item.sku || item.productID || extractProductId(url);
      let priceValue = null;
      if (offer.price != null) {
        const n = parseFloat(String(offer.price).replace(/,/g, ""));
        priceValue = Number.isFinite(n) ? n : null;
      }
      items.push({
        id: sku ? String(sku) : "",
        url,
        name,
        image,
        price: priceValue,
        priceCurrency: offer.priceCurrency ?? null,
      });
    }
    if (items.length) break;
  }

  if (!items.length) {
    const seen = new Set();
    $('a[href*="-p"][href$=".html"]').each((_, el) => {
      const $a = $(el);
      const href = $a.attr("href") || "";
      let absolute = "";
      try { absolute = new URL(href, "https://www.zara.com").toString(); } catch {}
      const sku = extractProductId(absolute);
      if (!sku || seen.has(sku)) return;
      seen.add(sku);
      const name = clean($a.attr("aria-label") || $a.find("h2,h3,span").first().text());
      const img = $a.find("img").attr("src") || $a.find("img").attr("data-src") || null;
      items.push({
        id: sku,
        url: absolute,
        name: name || "",
        image: img,
        price: null,
        priceCurrency: null,
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
  for (let page = 2; page <= maxPages; page++) {
    const pageUrl = addQuery(url, { page });
    const html = await fetchRenderedHtml(pageUrl, 'script[type="application/ld+json"]');
    out.push(...parseSearch(html).results);
  }
  return out;
}
