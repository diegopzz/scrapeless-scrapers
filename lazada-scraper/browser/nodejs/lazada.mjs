// Lazada scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Lazada hydrates PDP fields client-side from an XHR to
//   /h5/mtop.global.detail.web.getdetailinfo/1.0/
// The response wraps a stringified `data.module` JSON that holds `product`,
// `skuInfos[id].price`, `seller`, `review`, `Breadcrumb`, `skuGalleries`.
// We capture that XHR live; the SSR HTML is too sparse to rely on.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "SG";
const DEFAULT_SESSION_TTL = 240;
const DEFAULT_HOST = "https://www.lazada.sg";

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function withBrowser(fn, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 2, label = "navigation" } = {}) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const { browserWSEndpoint } = await client().browser.create({ proxyCountry, sessionTTL: DEFAULT_SESSION_TTL });
    let browser;
    try {
      browser = await puppeteer.connect({ browserWSEndpoint });
      return await fn(browser);
    } catch (e) {
      lastError = e;
      if (attempt === retries) break;
      await new Promise((r) => setTimeout(r, 4000 * Math.pow(1.5, attempt)));
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
  }
  throw new Error(`${label}: giving up after ${retries + 1} attempts: ${lastError?.message ?? lastError}`);
}

// ---------------- helpers ----------------

function abs(url, host = DEFAULT_HOST) {
  if (!url) return null;
  if (url.startsWith("//")) return "https:" + url;
  if (url.startsWith("http")) return url;
  return host + (url.startsWith("/") ? url : "/" + url);
}

function uniq(arr) {
  return Array.from(new Set(arr.filter(Boolean)));
}

function idFromUrl(url) {
  if (!url) return "";
  const m = url.match(/-i(\d+)(?:-s\d+)?\.html/);
  if (m) return m[1];
  const m2 = url.match(/\/(\d{8,})\.html/);
  if (m2) return m2[1];
  return "";
}

function toFloat(text) {
  if (text === null || text === undefined) return null;
  if (typeof text === "number") return Number.isFinite(text) ? text : null;
  const m = String(text).replace(/[^0-9.]/g, "");
  if (!m) return null;
  const n = parseFloat(m);
  return Number.isNaN(n) ? null : n;
}

function toInt(text) {
  if (text === null || text === undefined) return null;
  if (typeof text === "number") return Number.isFinite(text) ? Math.trunc(text) : null;
  const m = String(text).replace(/[^0-9]/g, "");
  if (!m) return null;
  const n = parseInt(m, 10);
  return Number.isNaN(n) ? null : n;
}

// ---------------- parsers ----------------

// Build a `Product` dict from the mtop `module` blob.
export function parseProductFromMtop(mod, url) {
  const product = mod.product || {};
  const skuInfos = mod.skuInfos || {};
  const skuGalleries = mod.skuGalleries || {};
  const seller = mod.seller || {};
  const review = mod.review || {};
  const Breadcrumb = mod.Breadcrumb || mod.breadcrumb || [];
  const globalConfig = mod.globalConfig || {};

  // Find the "default" sku price block — Lazada keys skuInfos by skuId and by "0".
  const ids = Object.keys(skuInfos);
  const preferred = skuInfos[(mod.primaryKey || {}).skuId] || skuInfos[ids[ids.length - 1]] || skuInfos["0"] || {};
  const priceObj = preferred.price || {};
  const sale = priceObj.salePrice || {};
  const orig = priceObj.originalPrice || {};

  // Gather images
  const imgs = [];
  const galleryKey = (mod.primaryKey || {}).skuId || ids[ids.length - 1] || "0";
  for (const g of skuGalleries[galleryKey] || []) {
    const u = g?.src || g?.poster;
    if (u) imgs.push(u.startsWith("//") ? "https:" + u : u);
  }
  for (const u of product.imageUrls || []) imgs.push(u);
  const images = uniq(imgs);

  const categories = (Breadcrumb || []).map((b) => b?.title).filter(Boolean);

  return {
    id: String(idFromUrl(url) || product.itemId || (mod.primaryKey || {}).itemId || ""),
    url,
    title: product.title || "",
    brand: (product.brand && (product.brand.name || product.brand)) || null,
    price: sale.text || (typeof sale.value === "number" ? `${sale.sign || ""}${sale.value}` : null),
    originalPrice: orig.text || (typeof orig.value === "number" ? String(orig.value) : null),
    discount: priceObj.discount || null,
    currency: globalConfig.currencyCode || null,
    rating: toFloat(product.rating?.score ?? review.averageRating),
    reviews: toInt(product.rating?.total ?? review.contentedNum),
    images,
    seller: seller.name || null,
    sellerUrl: abs(seller.url) || null,
    availability: preferred?.operation?.text || null,
    description: product.desc || null,
    categories,
  };
}

export function parseSearch(html) {
  const $ = cheerio.load(html);
  const out = [];
  const seen = new Set();

  const cards = [
    "div[data-qa-locator='product-item']",
    "div[class*='card--']",
    "div[class*='Bm3ON']",
    "div[class*='product-card']",
  ];
  for (const sel of cards) {
    $(sel).each((_, el) => {
      const card = $(el);
      const a = card.find("a[href*='.html']").first();
      let href = a.attr("href") || "";
      if (href.startsWith("//")) href = "https:" + href;
      if (!href) return;
      const id = idFromUrl(href);
      if (!id || seen.has(id)) return;
      seen.add(id);

      const text$ = (n) => (n?.text?.() || "").replace(/\s+/g, " ").trim() || null;
      const title =
        text$(card.find("[class*='RfADt'], [class*='title'], [class*='subject'], [class*='card-text-title']").first()) ||
        a.attr("title") ||
        text$(a) ||
        "";

      const image =
        card.find("img").first().attr("src") ||
        card.find("img").first().attr("data-src") ||
        null;
      const price = text$(card.find("[class*='price'], [class*='ooOxS']").first()) || null;
      const originalPrice = text$(card.find("[class*='WNoq3'], [class*='origPrice']").first()) || null;
      const discount = text$(card.find("[class*='IcOsH'], [class*='discount']").first()) || null;
      let rating = toFloat(
        card.find("[class*='qzqFw'], [class*='rating'], [class*='stars']").first().attr("style") ||
          text$(card.find("[class*='qzqFw'], [class*='rating'], [class*='stars']").first()),
      );
      if (rating !== null && rating > 5) rating = rating / 10;
      if (rating !== null && rating > 5) rating = null;
      const reviews = toInt(text$(card.find("[class*='_6uN7R'], span[class*='review']").first()));
      const location = text$(card.find("[class*='oa6ri'], [class*='location']").first()) || null;

      out.push({
        id,
        title,
        url: href,
        image: image && image.startsWith("//") ? "https:" + image : image,
        price,
        originalPrice,
        discount,
        rating,
        reviews,
        location,
      });
    });
  }
  return out;
}

// ---------------- scrape functions ----------------

export async function scrapeProduct(productUrl) {
  return withBrowser(async (browser) => {
    const page = await browser.newPage();
    const bodies = [];
    page.on("response", async (resp) => {
      try {
        const u = resp.url();
        if (!u.toLowerCase().includes("mtop.global.detail.web.getdetailinfo")) return;
        const txt = await resp.text();
        if (txt) bodies.push(txt);
      } catch (_) {}
    });
    await page.goto(productUrl, { waitUntil: "domcontentloaded", timeout: 60000 });
    // The detail page makes 1–2 mtop calls during boot. Wait for one carrying
    // `product`, with up to 35s budget.
    const deadline = Date.now() + 35000;
    let mod = null;
    while (Date.now() < deadline) {
      for (const body of bodies) {
        try {
          const env = JSON.parse(body);
          const raw = env?.data?.module;
          const m = typeof raw === "string" ? JSON.parse(raw) : (raw || env?.data || null);
          if (m && m.product) { mod = m; break; }
        } catch (_) {}
      }
      if (mod) break;
      await new Promise((r) => setTimeout(r, 500));
    }
    if (!mod) {
      throw new Error(`lazada: detail XHR (mtop.global.detail.web.getDetailInfo) never returned a product block for ${productUrl}`);
    }
    return parseProductFromMtop(mod, productUrl);
  }, { label: "scrape_product" });
}

export async function scrapeSearch(query, maxPages = 1, host = DEFAULT_HOST) {
  return withBrowser(async (browser) => {
    const page = await browser.newPage();
    const out = [];
    for (let p = 1; p <= maxPages; p++) {
      const url = `${host}/catalog/?q=${encodeURIComponent(query)}&page=${p}`;
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
      try { await page.waitForSelector("div[data-qa-locator='product-item'], div[class*='card']", { timeout: 20000 }); } catch (_) {}
      try {
        await page.evaluate(async () => {
          await new Promise((r) => {
            let y = 0;
            const i = setInterval(() => {
              window.scrollBy(0, 600);
              y += 600;
              if (y >= document.body.scrollHeight) { clearInterval(i); r(); }
            }, 120);
          });
        });
      } catch (_) {}
      await new Promise((r) => setTimeout(r, 1500));
      const html = await page.content();
      out.push(...parseSearch(html));
    }
    return out;
  }, { label: "scrape_search" });
}
