// Macy's scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Surfaces:
//   - scrapeProduct(urls)                  -> array of Product dicts (PDP fields lifted from JSON-LD)
//   - scrapeSearch(categoryUrl, maxPages)  -> array of SearchResult dicts (PLP tiles)
//
// Macys.com is fronted by Akamai Bot Manager. We warm up each session by hitting the
// homepage first, then navigate to the target with a referer set; we also rotate
// sessions on a 403/Access Denied response.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 240;
const HOME = "https://www.macys.com/";

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function fetchRenderedHtml(url, readySelector, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 3 } = {}) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    if (attempt > 0) {
      // Back off between session attempts to give Akamai's rate-limit some headroom.
      await new Promise((r) => setTimeout(r, 15000));
    }
    const { browserWSEndpoint } = await client().browser.create({
      proxyCountry,
      sessionTTL: DEFAULT_SESSION_TTL,
    });
    let browser;
    try {
      browser = await puppeteer.connect({ browserWSEndpoint });
      const page = await browser.newPage();
      await page.setExtraHTTPHeaders({ "accept-language": "en-US,en;q=0.9" });
      // Warm up the session at the homepage so Akamai issues a session cookie.
      await page.goto(HOME, { waitUntil: "domcontentloaded", timeout: 45000 });
      await new Promise((r) => setTimeout(r, 4000));
      try { await page.evaluate(() => window.scrollBy(0, 600)); } catch (_) {}
      await new Promise((r) => setTimeout(r, 2000));

      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000, referer: HOME });
      if (readySelector) {
        try { await page.waitForSelector(readySelector, { timeout: 20000 }); } catch (_) {}
      }
      // Nuxt SPA: wait an extra beat for client-side JSON-LD to be injected.
      await new Promise((r) => setTimeout(r, 4000));
      const html = await page.content();
      const title = await page.title().catch(() => "");
      const blocked =
        title === "Access Denied" ||
        /\bAccess Denied\b/.test(html) ||
        /sec-if-cpt-container|akamai-logo-msg|"Powered and protected by"/i.test(html);
      if (blocked) {
        lastError = new Error("blocked by Akamai (Access Denied)");
      } else if (html && html.toLowerCase().includes("<html")) {
        return html;
      } else {
        lastError = new Error("empty HTML");
      }
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
      if (Array.isArray(node["@graph"])) { for (const s of node["@graph"]) stack.push(s); }
      else yield node;
    }
  }
}

function typeMatches(node, wanted) {
  const t = node["@type"];
  if (typeof t === "string") return t === wanted;
  if (Array.isArray(t)) return t.includes(wanted);
  return false;
}

function shortAvailability(value) {
  if (typeof value !== "string") return null;
  return value.includes("/") ? value.split("/").pop() : value;
}

function extractProductId(url) {
  if (!url) return "";
  try {
    const u = new URL(url, "https://www.macys.com");
    const id = u.searchParams.get("ID");
    if (id) return id;
  } catch (_) {}
  const m = String(url).match(/[?&]ID=(\d+)/i);
  return m ? m[1] : "";
}

// ---------------- parsers ----------------

export function parseProduct(html, url) {
  const $ = cheerio.load(html);

  let ld = null;
  for (const node of iterJsonldNodes($)) {
    if (typeMatches(node, "Product")) { ld = node; break; }
  }
  if (!ld) {
    // The PDP renders no Product JSON-LD when Akamai serves an interstitial or
    // when the requested ID has been delisted ("Sorry, this page is no longer
    // available."). Fail loudly so callers can rotate / pick a different SKU.
    const bodyText = $("p").first().text().toLowerCase();
    const reason = bodyText.includes("no longer available") ? "product retired"
      : (html.includes("Access Denied") ? "Akamai Access Denied" : "no Product JSON-LD found");
    throw new Error(`macys: ${reason} for ${url}`);
  }

  const offers = ld.offers;
  let offer = {};
  if (Array.isArray(offers) && offers.length) offer = (typeof offers[0] === "object") ? offers[0] : {};
  else if (offers && typeof offers === "object") offer = offers;

  const rating = (ld.aggregateRating && typeof ld.aggregateRating === "object") ? ld.aggregateRating : {};

  let images = [];
  const imgRaw = ld.image;
  if (typeof imgRaw === "string") images = [imgRaw];
  else if (Array.isArray(imgRaw)) images = imgRaw.filter(Boolean).map(String);
  if (!images.length) {
    images = $('meta[property="og:image"]').map((_, el) => $(el).attr("content")).get().filter(Boolean);
  }

  let brand = null;
  if (ld.brand && typeof ld.brand === "object") brand = ld.brand.name ?? null;
  else if (typeof ld.brand === "string") brand = ld.brand;

  const id = ld.productID ? String(ld.productID) : extractProductId(url);

  return {
    id: String(id || ""),
    url,
    name: clean(ld.name) || clean($('h1').first().text()) || clean($('[data-auto="product-name"]').first().text()) || "",
    brand: clean(brand),
    description: clean(ld.description) || clean($('meta[name="description"]').attr("content")),
    price: toNumber(offer.price),
    priceCurrency: offer.priceCurrency ?? null,
    availability: shortAvailability(offer.availability),
    images,
    rating: rating.ratingValue != null ? Number(rating.ratingValue) : null,
    reviewCount: rating.reviewCount != null ? parseInt(rating.reviewCount, 10) : null,
    sku: ld.sku ? String(ld.sku) : null,
  };
}

export function parseSearch(html) {
  const $ = cheerio.load(html);
  const items = [];
  const seen = new Set();

  $('a[href*="ID="]').each((_, el) => {
    const $a = $(el);
    const href = $a.attr("href") || "";
    if (!/\/shop\/product\//i.test(href)) return;
    const abs = href.startsWith("http") ? href : `https://www.macys.com${href}`;
    const id = extractProductId(abs);
    if (!id || seen.has(id)) return;
    seen.add(id);

    const card = $a.closest('[data-testid="product-tile"], [data-auto="product-tile"], .product-thumbnail-container, li, div');
    const ctx = card.length ? card : $a;

    const name = clean(
      ctx.find('[data-auto="product-title"], [data-testid="product-title"], .product-description, h3, h2').first().text() ||
      $a.attr("aria-label") ||
      ctx.find("img").first().attr("alt")
    ) || "";

    const brand = clean(
      ctx.find('[data-auto="product-brand"], [data-testid="product-brand"], .product-brand').first().text()
    );

    const priceText = clean(
      ctx.find('[data-auto="product-price"], [data-testid="product-price"], .price-reg, .pricing').first().text()
    );
    const price = toNumber(priceText);

    const image = ctx.find("img").first().attr("src") || ctx.find("img").first().attr("data-src") || null;

    items.push({
      id: String(id),
      url: abs,
      name,
      brand,
      image: image || null,
      price,
      priceCurrency: priceText && priceText.includes("$") ? "USD" : null,
    });
  });

  return items;
}

// ---------------- scrape functions ----------------

export async function scrapeProduct(urls) {
  const list = Array.isArray(urls) ? urls : [urls];
  const out = [];
  for (const url of list) {
    const html = await fetchRenderedHtml(url, 'script[type="application/ld+json"], h1');
    out.push(parseProduct(html, url));
  }
  return out;
}

export async function scrapeSearch(categoryUrl, maxPages = 1) {
  const out = [];
  for (let page = 1; page <= maxPages; page++) {
    let url = categoryUrl;
    if (page > 1) {
      const u = new URL(categoryUrl);
      u.searchParams.set("Pageindex", String(page));
      url = u.toString();
    }
    const html = await fetchRenderedHtml(url, 'a[href*="ID="]');
    out.push(...parseSearch(html));
  }
  return out;
}
