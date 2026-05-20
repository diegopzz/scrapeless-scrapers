// Etsy scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
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

function looksLikeDatadomeBlock(html) {
  if (!html) return true;
  if (html.length < 4000 && html.includes("captcha-delivery")) return true;
  if (html.length < 4000 && html.includes("geo.captcha-delivery")) return true;
  return false;
}

async function fetchRenderedHtml(url, readySelector, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 2, warmup = true } = {}) {
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
      // Etsy is fronted by DataDome and almost always serves a captcha
      // interstitial on cold sessions. Hit the homepage first so the cloud
      // session collects the DataDome cookie before the real navigation.
      if (warmup) {
        try {
          await page.goto("https://www.etsy.com/", { waitUntil: "domcontentloaded", timeout: 30000 });
          await new Promise((r) => setTimeout(r, 2500));
        } catch (_) {}
      }
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
      try {
        await page.waitForSelector(readySelector, { timeout: 15000 });
      } catch (_) {
        // non-fatal
      }
      const html = await page.content();
      if (html && !looksLikeDatadomeBlock(html)) return html;
      lastError = new Error("DataDome interstitial or empty HTML");
    } catch (e) {
      lastError = e;
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
  }
  throw new Error(`giving up after ${retries + 1} attempts: ${lastError?.message}`);
}

// ---------------- helpers ----------------

export function stripText(text) {
  if (text == null) return null;
  return String(text).trim();
}

function toFloat(text) {
  if (!text) return null;
  const m = String(text).replace(/[^0-9.]/g, "");
  if (!m) return null;
  const n = parseFloat(m);
  return Number.isNaN(n) ? null : n;
}

function toInt(text) {
  if (!text) return null;
  const m = String(text).replace(/[^0-9]/g, "");
  if (!m) return null;
  const n = parseInt(m, 10);
  return Number.isNaN(n) ? null : n;
}

// ---------------- parsers ----------------

export function parseSearch(html) {
  const $ = cheerio.load(html);
  const items = [];
  $("div[data-search-results-lg] > ul > li").each((_, li) => {
    const card = $(li);
    if (!card.find("[data-appears-component-name]").length) return;

    const link = card.find("a.v2-listing-card, a[class*='v2-listing-card']").first().attr("href") || "";
    const title = card.find("h3[class*='v2-listing-card__titl']").first().attr("title") || "";
    const image = card.find("img[data-listing-card-listing-image]").first().attr("src") || "";

    let seller = null;
    card.find("span").each((_i, s) => {
      const t = $(s).text();
      if (/^\s*From shop/i.test(t)) {
        seller = t.replace(/^\s*From shop\s*/i, "").trim() || null;
      }
    });

    const isPaid = card.find("span[data-ad-label='Ad by Etsy seller']").length > 0;
    const rating = toFloat(card.find("span.review_stars span, span[class*='review_stars'] span").first().text());
    const reviews = toInt(card.find("div[aria-label*='star rating'] p").first().text());

    let freeShipping = "no";
    card.find("span").each((_i, s) => {
      if (/Free shipping/i.test($(s).text())) freeShipping = "yes";
    });

    const price = toFloat(card.find("span.currency-value").first().text()) ?? 0;
    const currency = (card.find("span.currency-symbol").first().text() || "").trim();

    let originalPrice = "";
    card.find("span").each((_i, s) => {
      const t = $(s).text();
      if (/Original Price/.test(t) && !originalPrice) originalPrice = t.trim();
    });

    let discount = "";
    card.find("span").each((_i, s) => {
      const t = $(s).text();
      if (/off\b/i.test(t) && !discount) discount = t.trim();
    });

    items.push({
      productLink: link,
      productTitle: title,
      productImage: image,
      seller,
      listingType: isPaid ? "paid" : "organic",
      productRate: rating,
      numberOfReviews: reviews,
      freeShipping,
      productPrice: price,
      priceCurrency: currency,
      originalPrice,
      discount,
    });
  });

  const lastPageText = $("nav[aria-label='Pagination'] li").eq(-2).find("a").first().text();
  const totalPages = toInt(lastPageText) ?? 1;
  return { search_data: items, total_pages: totalPages };
}

// Collect every JSON-LD node from a Cheerio document.
//
// Handles three shapes:
//   - bare object: { "@type": "Product", ... }
//   - array of objects: [ { "@type": "Product" }, { "@type": "BreadcrumbList" } ]
//   - graph wrapper: { "@context": "...", "@graph": [ {...}, {...} ] }
function collectJsonLdNodes($) {
  const blocks = $('script[type="application/ld+json"]')
    .toArray()
    .map((el) => $(el).contents().text());
  const nodes = [];
  for (const raw of blocks) {
    if (!raw || !raw.trim()) continue;
    let data;
    try {
      data = JSON.parse(raw);
    } catch (_) {
      continue;
    }
    const items = Array.isArray(data) ? data : [data];
    for (const node of items) {
      if (!node || typeof node !== "object") continue;
      if (Array.isArray(node["@graph"])) {
        for (const sub of node["@graph"]) {
          if (sub && typeof sub === "object") nodes.push(sub);
        }
      } else {
        nodes.push(node);
      }
    }
  }
  return nodes;
}

function typeMatches(node, wanted) {
  const t = node["@type"];
  if (typeof t === "string") return t === wanted;
  if (Array.isArray(t)) return t.includes(wanted);
  return false;
}

export function parseProductPage(html) {
  const $ = cheerio.load(html);
  for (const node of collectJsonLdNodes($)) {
    if (typeMatches(node, "Product")) return node;
  }
  return {};
}

export function parseShopPage(html, url) {
  const $ = cheerio.load(html);
  for (const node of collectJsonLdNodes($)) {
    if (typeMatches(node, "ItemList")) return { ...node, url };
  }
  return { url };
}

// ---------------- scrape functions (mirror the upstream reference) ----------------

export async function scrapeSearch(url, maxPages = null) {
  const html = await fetchRenderedHtml(url, "div[data-search-results-lg]");
  const first = parseSearch(html);
  const items = [...first.search_data];
  let totalPages = first.total_pages;
  if (maxPages && maxPages < totalPages) totalPages = maxPages;
  if (totalPages > 1) {
    for (let page = 2; page <= totalPages; page++) {
      const sep = url.includes("?") ? "&" : "?";
      const pageUrl = `${url}${sep}page=${page}`;
      const pageHtml = await fetchRenderedHtml(pageUrl, "div[data-search-results-lg]");
      items.push(...parseSearch(pageHtml).search_data);
    }
  }
  return items;
}

export async function scrapeProduct(urls) {
  const products = [];
  for (const url of urls) {
    const html = await fetchRenderedHtml(url, "script[type='application/ld+json']");
    products.push(parseProductPage(html));
  }
  return products;
}

export async function scrapeShop(urls) {
  const shops = [];
  for (const url of urls) {
    const html = await fetchRenderedHtml(url, "script[type='application/ld+json']");
    shops.push(parseShopPage(html, url));
  }
  return shops;
}
