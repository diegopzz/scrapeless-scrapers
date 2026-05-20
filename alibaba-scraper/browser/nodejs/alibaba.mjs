// Alibaba scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Under the hood:
// - `client.browser.create()` mints a cloud session on Scrapeless's Scraping Browser,
//   returning a CDP WebSocket endpoint (`browserWSEndpoint`).
// - puppeteer-core connects to that WebSocket, drives the page, returns rendered HTML.
// - cheerio parses the HTML into objects matching DATA_MODEL.md.

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

async function fetchRenderedHtml(url, readySelector, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 1, autoScroll = false } = {}) {
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
      if (autoScroll) {
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
          await new Promise((r) => setTimeout(r, 1500));
        } catch (_) {}
      }
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

// ---------------- helpers ----------------

function text$(node) {
  return (node?.text?.() || "").replace(/\s+/g, " ").trim() || null;
}

function abs(url) {
  if (!url) return null;
  if (url.startsWith("//")) return "https:" + url;
  if (url.startsWith("http")) return url;
  return "https://www.alibaba.com" + (url.startsWith("/") ? url : "/" + url);
}

function uniq(arr) {
  return Array.from(new Set(arr.filter(Boolean)));
}

function idFromUrl(url) {
  if (!url) return "";
  const m = url.match(/product-detail\/[^\/]+_(\d+)\.html/);
  if (m) return m[1];
  const m2 = url.match(/_(\d{8,})\.html/);
  if (m2) return m2[1];
  const m3 = url.match(/\/(\d{8,})\.html/);
  if (m3) return m3[1];
  return "";
}

// ---------------- parsers ----------------

export function parseProduct(html, url) {
  const $ = cheerio.load(html);

  const title =
    text$($("h1").first()) ||
    text$($("[class*='product-title'], [class*='title-content'], [class*='ife-title-display'], [data-test='product-title']").first()) ||
    text$($("h1 span, h1 div").first()) ||
    $("meta[property='og:title']").attr("content") ||
    (($("title").text() || "").split("|")[0] || "").trim() ||
    "";

  // images
  const images = uniq([
    ...$("[class*='detail-gallery'] img, [class*='main-image'] img, [class*='preview-image'] img, [class*='gallery'] img, img[class*='lazyload']")
      .map((_, e) => $(e).attr("src") || $(e).attr("data-src")).get(),
    ...$("meta[property='og:image']").map((_, e) => $(e).attr("content")).get(),
  ]).map((u) => (u && u.startsWith("//") ? "https:" + u : u)).filter(Boolean);

  // price + range
  const priceNodes = $("[class*='price-value'], [class*='price-text'], [class*='product-price'] [class*='price'], [class*='ladderPrice'] [class*='price']")
    .map((_, e) => text$($(e))).get().filter(Boolean);
  const price = priceNodes[0] || null;
  let priceRange = null;
  if (priceNodes.length > 1) priceRange = priceNodes.join(" - ");

  // MOQ
  let moq = null;
  $("[class*='min-order'], [class*='moq'], [class*='ladderMinOrder']").each((_, e) => {
    const t = text$($(e));
    if (!moq && t) moq = t;
  });

  const supplier =
    text$($("a[class*='company-name'], a[class*='supplier-name'], [class*='company-detail-name']").first()) ||
    null;
  const supplierUrl = abs($("a[class*='company-name'], a[class*='supplier-name']").first().attr("href")) || null;
  const supplierYears = text$($("[class*='supplier-years'], [class*='verified-years'], [class*='years-label']").first()) || null;
  const location = text$($("[class*='supplier-location'], [class*='location-info'], [class*='country-name']").first()) || null;
  const rating = text$($("[class*='supplier-rating'], [class*='star-rating'], [class*='reviewer'] [class*='star']").first()) || null;

  const description =
    $("meta[name='description']").attr("content") ||
    $("meta[property='og:description']").attr("content") ||
    null;

  const categories = uniq(
    $("[class*='breadcrumb'] a, [class*='crumb'] a, nav[aria-label*='readcrumb'] a").map((_, e) => text$($(e))).get(),
  );

  return {
    id: String(idFromUrl(url) || ""),
    url,
    title: title || "",
    price,
    priceRange,
    moq,
    images,
    supplier,
    supplierUrl,
    supplierYears,
    location,
    rating,
    description,
    categories,
  };
}

export function parseSearch(html) {
  const $ = cheerio.load(html);
  const out = [];
  const seen = new Set();

  const cardSelectors = [
    "div[class*='organic-list-offer']",
    "div[class*='J-offer-wrapper']",
    "div[class*='fy23-search-card']",
    "div[class*='fy24-search-card']",
    "div[class*='search-card']",
    "div[data-content='product']",
    "div[class*='list-no-v2-outter']",
    "div[data-aplus-auto-clk]",
    "a[class*='card-offer']",
    "a[href*='product-detail']",
  ];

  for (const sel of cardSelectors) {
    $(sel).each((_, el) => {
      const card = $(el);
      const a = card.is("a") ? card : card.find("a[href*='product-detail'], a[href*='/product/'], a[href*='_p']").first();
      let href = a.attr("href") || card.find("a").first().attr("href") || "";
      if (href.startsWith("//")) href = "https:" + href;
      const id = idFromUrl(href);
      if (!id || seen.has(id)) return;
      seen.add(id);

      const title =
        text$(card.find("h2, [class*='title'], [class*='subject'], [class*='product-title']").first()) ||
        text$(a) ||
        "";
      const image =
        card.find("img").first().attr("src") ||
        card.find("img").first().attr("data-src") ||
        null;
      const price = text$(card.find("[class*='price']").first()) || null;
      const moq = text$(card.find("[class*='min-order'], [class*='moq'], [class*='order-num']").first()) || null;
      const supplier = text$(card.find("[class*='supplier'], [class*='company'], [class*='seller-name']").first()) || null;
      const location = text$(card.find("[class*='location'], [class*='country'], [class*='supplier-loc']").first()) || null;

      out.push({
        id,
        title,
        url: href,
        image: image && image.startsWith("//") ? "https:" + image : image,
        price,
        moq,
        supplier,
        location,
      });
    });
  }
  return out;
}

// ---------------- scrape functions ----------------

export async function scrapeProduct(productUrl) {
  const html = await fetchRenderedHtml(productUrl, "h1", { autoScroll: true });
  return parseProduct(html, productUrl);
}

export async function scrapeSearch(query, maxPages = 1) {
  const out = [];
  for (let page = 1; page <= maxPages; page++) {
    // Try the showroom slug first (less aggressive CAPTCHA than /trade/search),
    // then the canonical /trade/search surface.
    const slug = query.trim().toLowerCase().replace(/\s+/g, "-");
    const candidates = [
      `https://www.alibaba.com/showroom/${encodeURIComponent(slug)}.html`,
      `https://www.alibaba.com/trade/search?SearchText=${encodeURIComponent(query)}&page=${page}`,
    ];
    let added = 0;
    for (const url of candidates) {
      try {
        const html = await fetchRenderedHtml(url, "a[href*='product-detail']", { autoScroll: true });
        if (/Captcha Interception/i.test(html)) continue;
        const parsed = parseSearch(html);
        if (parsed.length) {
          out.push(...parsed);
          added = parsed.length;
          break;
        }
      } catch (_) { /* try next */ }
    }
    if (!added) break;
  }
  return out;
}
