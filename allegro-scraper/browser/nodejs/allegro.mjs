// Allegro (allegro.pl) scraper using @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// function names and emitted field names match verbatim. Polish characters in
// titles, seller names, etc. are preserved verbatim.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "PL";
const DEFAULT_SESSION_TTL = 240;
const HOME = "https://allegro.pl/";

// Extract a balanced JSON object starting at index `start` (must point at '{').
function readJsonObject(text, start) {
  let depth = 0;
  let inStr = false;
  let esc = false;
  for (let i = start; i < text.length; i++) {
    const ch = text[i];
    if (inStr) {
      if (esc) { esc = false; continue; }
      if (ch === "\\") { esc = true; continue; }
      if (ch === '"') { inStr = false; }
      continue;
    }
    if (ch === '"') { inStr = true; continue; }
    if (ch === "{") depth++;
    else if (ch === "}") {
      depth--;
      if (depth === 0) return text.slice(start, i + 1);
    }
  }
  return null;
}

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}
function client() { return new Scrapeless({ apiKey: requireKey() }); }

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
      await page.setExtraHTTPHeaders({ "accept-language": "pl-PL,pl;q=0.9,en;q=0.5" });
      if (warmup) {
        try {
          await page.goto(HOME, { waitUntil: "domcontentloaded", timeout: 30000 });
          await new Promise((r) => setTimeout(r, 2500));
        } catch (_) {}
      }
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000, referer: HOME });
      if (readySelector) {
        try { await page.waitForSelector(readySelector, { timeout: 20000 }); } catch (_) {}
      }
      // Give Allegro's React tree a moment to mount listing/product state.
      await new Promise((r) => setTimeout(r, 1500));
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

function boxPayload($, needle) {
  let found = null;
  $('script[data-serialize-box-id]').each((_, el) => {
    const text = $(el).contents().text();
    if (!text.includes(needle)) return;
    try {
      const parsed = JSON.parse(text);
      found = parsed;
      return false;
    } catch (_) {}
  });
  return found;
}

function listingState($) {
  // Allegro's listing state is embedded as part of a larger inline JSON object
  // in a `<script>` tag, keyed `"__listing_StoreState":{...}`. The legacy
  // assignment form (`__listing_StoreState = {...};`) no longer ships, so we
  // locate the key and balance braces ourselves.
  let found = null;
  $("script").each((_, el) => {
    const text = $(el).contents().text();
    const idx = text.indexOf('"__listing_StoreState"');
    if (idx === -1) return;
    let cursor = text.indexOf(":", idx) + 1;
    while (cursor < text.length && /\s/.test(text[cursor])) cursor++;
    if (text[cursor] !== "{") return;
    const obj = readJsonObject(text, cursor);
    if (!obj) return;
    try { found = JSON.parse(obj); return false; } catch (_) {}
  });
  return found;
}

function searchMeta($) {
  // searchMeta can appear either inside a data-serialize-box-id payload or
  // inline within the same script that holds __listing_StoreState (newer flow).
  let found = null;
  $('script[data-serialize-box-id]').each((_, el) => {
    const text = $(el).contents().text();
    if (!text.includes("searchMeta")) return;
    try {
      const data = JSON.parse(text);
      const meta = data?.props?.searchMeta ?? data?.searchMeta;
      if (meta && typeof meta === "object") { found = meta; return false; }
    } catch (_) {}
  });
  if (found) return found;
  // Fallback: scan all inline <script> blocks for the embedded `"searchMeta":{...}`.
  $("script").each((_, el) => {
    const text = $(el).contents().text();
    const idx = text.indexOf('"searchMeta"');
    if (idx === -1) return;
    let cursor = text.indexOf(":", idx) + 1;
    while (cursor < text.length && /\s/.test(text[cursor])) cursor++;
    if (text[cursor] !== "{") return;
    const obj = readJsonObject(text, cursor);
    if (!obj) return;
    try { found = JSON.parse(obj); return false; } catch (_) {}
  });
  return found;
}

// ---------------- parsers ----------------

function normaliseTitle(title) {
  if (typeof title === "string") return title;
  if (title && typeof title === "object") return title.text ?? "";
  return "";
}

function normalisePrice(price) {
  // Allegro's listing element ships price as `{mainPrice: {amount, currency}}`.
  if (!price || typeof price !== "object") return null;
  const main = price.mainPrice ?? price;
  if (!main || typeof main !== "object") return null;
  const amount = main.amount ?? null;
  const currency = main.currency ?? null;
  if (amount == null && currency == null) return null;
  return { amount, currency };
}

function firstPhoto(photos) {
  if (!Array.isArray(photos) || !photos.length) return null;
  const p = photos[0];
  if (!p) return null;
  if (typeof p === "string") return p;
  return p.url ?? p.medium ?? p.original ?? p.small ?? null;
}

function decanonicaliseOfferUrl(url) {
  // Sponsored items wrap the real URL in an /events/clicks?redirect=... shim.
  if (typeof url !== "string" || !url) return url ?? "";
  try {
    const u = new URL(url);
    if (u.pathname.startsWith("/events/clicks")) {
      const redirect = u.searchParams.get("redirect");
      if (redirect) return decodeURIComponent(redirect);
    }
  } catch (_) {}
  return url;
}

export function parseSearch(html) {
  const $ = cheerio.load(html);
  const state = listingState($) ?? {};
  const elements = Array.isArray(state?.items?.elements) ? state.items.elements : [];
  const products = [];
  for (const el of elements) {
    if (!el || typeof el !== "object") continue;
    const price = normalisePrice(el.price);
    products.push({
      // `el.id` is the canonical product UUID; `el.offerId` is the per-listing numeric id.
      product_id: el.productId ?? el.product_id ?? el.id ?? "",
      offer_id: el.offerId ?? el.offer_id ?? "",
      title: normaliseTitle(el.title),
      price,
      currency: price?.currency ?? null,
      url: decanonicaliseOfferUrl(el.url ?? ""),
      image: firstPhoto(el.photos),
      seller: el.seller ?? null,
      delivery_info: el.deliveryInfo ?? el.delivery ?? null,
    });
  }
  const meta = searchMeta($) ?? state?.searchMeta ?? {};
  return {
    products,
    products_count: products.length,
    total_pages: meta.lastAvailablePage ?? null,
    total_count: meta.totalCount ?? null,
  };
}

export function parseProduct(html) {
  const $ = cheerio.load(html);
  const priceBox = boxPayload($, "formattedPrice") ?? {};
  // The price box wraps the actual price subtree under `.price`; emit just that.
  const price = (priceBox && typeof priceBox === "object" && priceBox.price && typeof priceBox.price === "object")
    ? priceBox.price
    : priceBox;
  const galleryBox = boxPayload($, "galleryItems") ?? boxPayload($, "gallery") ?? {};
  const seller = boxPayload($, "sellerName") ?? {};

  // Gallery payload now ships items under `galleryItems` (was `images`).
  const galleryItems = Array.isArray(galleryBox.galleryItems)
    ? galleryBox.galleryItems
    : (Array.isArray(galleryBox.images) ? galleryBox.images : []);
  const images = [];
  for (const img of galleryItems) {
    if (!img) continue;
    if (typeof img === "string") { images.push(img); continue; }
    const url = img.original ?? img.embeded ?? img.url ?? img.thumbnail ?? null;
    if (url) images.push(url);
  }

  // Rating lives in the aggregateRating box (`{value, label, count}`), and in a
  // JSON-LD `aggregateRating.ratingValue` block for older flows.
  let rating = null;
  const ratingBox = boxPayload($, "aggregateRating");
  if (ratingBox && ratingBox.aggregateRating && ratingBox.aggregateRating.value != null) {
    rating = String(ratingBox.aggregateRating.value);
  }
  if (!rating) {
    $("script").each((_, el) => {
      const text = $(el).contents().text();
      if (!text.includes("aggregateRating")) return;
      try {
        const data = JSON.parse(text);
        const agg = data?.aggregateRating;
        if (agg && agg.ratingValue !== undefined && agg.ratingValue !== null) {
          rating = String(agg.ratingValue);
          return false;
        }
      } catch (_) {}
    });
  }

  const title = $("h1").first().text().trim();
  const specifications = [];
  $('[data-role="product-parameters"] li, .product-parameters li').each((_, row) => {
    const name = $(row).find("span").eq(0).text().trim();
    const value = $(row).find("span").eq(1).text().trim();
    if (name) specifications.push({ name, value });
  });
  // Newer listings expose specs as table rows under "Najważniejsze informacje" /
  // "Parametry produktu". Mine them out of `productParameters` boxes too.
  if (!specifications.length) {
    const paramsBox = boxPayload($, "productParameters") ?? boxPayload($, "parameters");
    const groups = paramsBox?.groups ?? paramsBox?.parameters ?? [];
    if (Array.isArray(groups)) {
      for (const group of groups) {
        const items = Array.isArray(group?.parameters) ? group.parameters : (Array.isArray(group?.items) ? group.items : []);
        for (const it of items) {
          const name = it?.name ?? it?.label ?? null;
          const value = it?.value ?? (Array.isArray(it?.values) ? it.values.join(", ") : null);
          if (name) specifications.push({ name: String(name), value: value == null ? "" : String(value) });
        }
      }
    }
  }

  const shipping_info = boxPayload($, "deliveryOptions") ?? boxPayload($, "shipping") ?? null;
  const allegro_smart_badge =
    $('[data-role="smart-badge"], [aria-label*="Smart"]').length > 0 ||
    /allegro smart!/i.test(html);

  return {
    title,
    price,
    images,
    shipping_info,
    rating,
    specifications,
    seller,
    reviews: [],
    allegro_smart_badge,
  };
}

// ---------------- scrape functions ----------------

function searchUrl(query, page) {
  return `https://allegro.pl/listing?string=${encodeURIComponent(query)}&p=${page}`;
}

export async function scrapeSearch(query, maxPages = 3, scrapeAllPages = false) {
  const firstHtml = await fetchRenderedHtml(searchUrl(query, 1), "article");
  const first = parseSearch(firstHtml);
  const products = [...(first.products ?? [])];
  const totalPages = first.total_pages ?? 1;
  const limit = scrapeAllPages ? totalPages : Math.min(maxPages, totalPages);
  let pagesScraped = 1;
  for (let p = 2; p <= limit; p++) {
    try {
      const html = await fetchRenderedHtml(searchUrl(query, p), "article");
      const data = parseSearch(html);
      products.push(...(data.products ?? []));
      pagesScraped += 1;
    } catch (_) { break; }
  }
  return {
    products,
    scraped_pages: pagesScraped,
    products_count: products.length,
    total_pages: first.total_pages,
    total_count: first.total_count,
  };
}

export async function scrapeProduct(urls) {
  const out = [];
  for (const url of urls) {
    const html = await fetchRenderedHtml(url, "h1");
    out.push(parseProduct(html));
  }
  return out;
}
