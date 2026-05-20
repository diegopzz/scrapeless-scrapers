// Big Lots scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Surfaces:
//   - scrapeProduct(urls)                  -> array of Product dicts (PDP fields lifted from JSON-LD)
//   - scrapeSearch(categoryUrl, maxPages)  -> array of SearchResult dicts (WooCommerce cards)
//
// biglots.com runs WordPress + WooCommerce. JSON-LD Product blocks are emitted on
// every PDP; the category pages render WooCommerce block-template <li class="post-...">
// cards, so DOM scraping is straightforward.

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

async function fetchRenderedHtml(url, readySelector, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 1 } = {}) {
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
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
      if (readySelector) {
        try { await page.waitForSelector(readySelector, { timeout: 15000 }); } catch (_) {}
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

// ---------------- helpers ----------------

function clean(value) {
  if (value == null) return null;
  const v = String(value).replace(/\s+/g, " ").trim();
  return v || null;
}

function toNumber(value) {
  if (value == null) return null;
  const n = parseFloat(String(value).replace(/[^\d.\-]/g, ""));
  return Number.isFinite(n) ? n : null;
}

function* iterJsonldNodes($) {
  const blocks = $('script[type="application/ld+json"]')
    .map((_, el) => $(el).contents().text())
    .get();
  for (const raw of blocks) {
    if (!raw || !raw.trim()) continue;
    let data;
    try { data = JSON.parse(raw); } catch { continue; }
    const stack = Array.isArray(data) ? [...data] : [data];
    while (stack.length) {
      const node = stack.shift();
      if (!node || typeof node !== "object") continue;
      if (Array.isArray(node["@graph"])) {
        for (const sub of node["@graph"]) stack.push(sub);
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

function pickOfferPrice(offer) {
  if (!offer || typeof offer !== "object") return null;
  if (offer.price != null) return toNumber(offer.price);
  const spec = offer.priceSpecification;
  if (Array.isArray(spec) && spec.length) return toNumber(spec[0].price);
  if (spec && typeof spec === "object") return toNumber(spec.price);
  return null;
}

function pickOfferCurrency(offer) {
  if (!offer || typeof offer !== "object") return null;
  if (offer.priceCurrency) return String(offer.priceCurrency);
  const spec = offer.priceSpecification;
  if (Array.isArray(spec) && spec.length) return spec[0].priceCurrency ?? null;
  if (spec && typeof spec === "object") return spec.priceCurrency ?? null;
  return null;
}

function shortAvailability(value) {
  if (typeof value !== "string") return null;
  return value.includes("/") ? value.split("/").pop() : value;
}

// ---------------- parsers ----------------

export function parseProduct(html, url) {
  const $ = cheerio.load(html);

  let ld = {};
  for (const node of iterJsonldNodes($)) {
    if (typeMatches(node, "Product")) { ld = node; break; }
  }

  const offers = ld.offers;
  let offer = {};
  if (Array.isArray(offers) && offers.length) offer = offers[0];
  else if (offers && typeof offers === "object") offer = offers;

  let images = [];
  const imgRaw = ld.image;
  if (typeof imgRaw === "string") images = [imgRaw];
  else if (Array.isArray(imgRaw)) images = imgRaw.filter(Boolean).map(String);
  if (!images.length) {
    images = $('meta[property="og:image"]').map((_, el) => $(el).attr("content")).get().filter(Boolean);
  }

  const categories = [];
  $(".woocommerce-breadcrumb a, .wp-block-woocommerce-breadcrumbs a").each((_, el) => {
    const t = clean($(el).text());
    if (t && !categories.includes(t)) categories.push(t);
  });

  const sellerNode = offer.seller;
  let sellerName = null;
  if (sellerNode && typeof sellerNode === "object") sellerName = sellerNode.name ?? null;
  else if (typeof sellerNode === "string") sellerName = sellerNode;

  const sku = ld.sku != null ? String(ld.sku) : (ld["@id"] || url);

  return {
    id: String(sku),
    url,
    name: clean(ld.name) || clean($("h1").first().text()) || "",
    description: clean(ld.description) || clean($('meta[name="description"]').attr("content")),
    price: pickOfferPrice(offer),
    priceCurrency: pickOfferCurrency(offer),
    availability: shortAvailability(offer.availability),
    images,
    categories,
    sellerName: clean(sellerName),
  };
}

export function parseSearch(html) {
  const $ = cheerio.load(html);
  const items = [];
  const seen = new Set();

  $('li.product, li.wp-block-post.product').each((_, el) => {
    const $card = $(el);
    // post-<id> class identifies the WP post id; fall back to data-id if present
    const classes = ($card.attr("class") || "").split(/\s+/);
    const postClass = classes.find((c) => /^post-\d+$/.test(c));
    const id = postClass ? postClass.replace("post-", "") : ($card.attr("data-id") ?? "");

    const anchor = $card.find('a[href*="/product/"]').first();
    const href = anchor.attr("href") || "";
    if (!href) return;
    const url = href.startsWith("http") ? href : `https://biglots.com${href}`;
    if (seen.has(url)) return;
    seen.add(url);

    const name = clean(
      $card.find('h3 a, h2 a, h3, h2').first().text() ||
      anchor.attr("aria-label") ||
      $card.find("img").first().attr("alt")
    ) || "";

    const priceText = clean(
      $card.find('.wp-block-woocommerce-product-price, .wc-block-components-product-price, .price').first().text()
    );
    const price = toNumber(priceText);

    const image = $card.find('img').first().attr('src') || $card.find('img').first().attr('data-src') || null;

    const category = clean(
      $card.find('.wp-block-post-terms a, .wc-block-grid__product-category').first().text()
    );

    items.push({
      id: String(id || ""),
      url,
      name,
      image: image || null,
      price,
      priceCurrency: priceText && priceText.includes("$") ? "USD" : null,
      category,
    });
  });

  return items;
}

// ---------------- scrape functions ----------------

export async function scrapeProduct(urls) {
  const list = Array.isArray(urls) ? urls : [urls];
  const out = [];
  for (const url of list) {
    const html = await fetchRenderedHtml(url, 'script[type="application/ld+json"]');
    out.push(parseProduct(html, url));
  }
  return out;
}

export async function scrapeSearch(categoryUrl, maxPages = 1) {
  const out = [];
  for (let page = 1; page <= maxPages; page++) {
    let url = categoryUrl;
    if (page > 1) {
      // WP archive pagination: <category>/page/<n>/
      const trimmed = categoryUrl.replace(/\/$/, "");
      url = `${trimmed}/page/${page}/`;
    }
    const html = await fetchRenderedHtml(url, 'li.product, li.wp-block-post.product');
    out.push(...parseSearch(html));
  }
  return out;
}
