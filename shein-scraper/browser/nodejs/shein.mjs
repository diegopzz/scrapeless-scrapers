// SHEIN scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 180;
const DEFAULT_HOST = "https://us.shein.com";

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

function uniq(arr) {
  return Array.from(new Set(arr.filter(Boolean)));
}

function abs(url, host = DEFAULT_HOST) {
  if (!url) return null;
  if (url.startsWith("//")) return "https:" + url;
  if (url.startsWith("http")) return url;
  return host + (url.startsWith("/") ? url : "/" + url);
}

function idFromUrl(url) {
  if (!url) return "";
  const m = url.match(/-p-(\d+)\.html/);
  if (m) return m[1];
  const m2 = url.match(/\/(\d{8,})\.html/);
  if (m2) return m2[1];
  return "";
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

export function parseProduct(html, url) {
  const $ = cheerio.load(html);

  const title =
    text$($("h1").first()) ||
    text$($("[class*='product-intro__head-name'], [class*='product-name'], [data-name='product-title']").first()) ||
    $("meta[property='og:title']").attr("content") ||
    "";

  // Shein bounces dead PDPs (and most bot-flagged sessions) back to the homepage
  // or serves an interstitial — both produce zero usable PDP fields. Fail loudly
  // so the run script doesn't emit a hollow stub.
  if (!title) {
    const pageTitle = ($("title").first().text() || "").trim();
    const hint = /Women.s.{0,3}Men.s Clothing,?\s*Shop Online Fashion/i.test(pageTitle)
      ? "bounced to homepage" : "missing product fields";
    throw new Error(`shein: ${hint} (anti-bot block or retired SKU) — ${url}`);
  }

  const price =
    text$($("[class*='product-intro__head-mainprice'], [class*='from-skc'] [class*='price'], [class*='price-content'] .from").first()) ||
    text$($("[class*='product-price'], [class*='sale-price']").first()) ||
    null;
  const originalPrice =
    text$($("[class*='product-intro__head-original-price'], [class*='product-intro__head-discount'] del, del[class*='retail']").first()) ||
    null;
  const discount =
    text$($("[class*='product-intro__head-discount'], [class*='discount-badge']").first()) ||
    null;
  const currency =
    $("meta[itemprop='priceCurrency']").attr("content") ||
    $("meta[property='og:price:currency']").attr("content") ||
    null;

  const rating = toFloat(text$($("[class*='ProductReviews_score'], [class*='rating-star'] [class*='value'], .score-num").first()));
  const reviews = toInt(text$($("[class*='ProductReviews_count'], [class*='review-count'], .review-num").first()));

  const images = uniq([
    ...$("[class*='product-intro__main-img-pic'] img, [class*='product-intro__thumbs'] img, [class*='gallery'] img, [class*='product-image'] img")
      .map((_, e) => $(e).attr("src") || $(e).attr("data-src") || $(e).attr("data-srcset")).get(),
    ...$("meta[property='og:image']").map((_, e) => $(e).attr("content")).get(),
  ]).map((u) => (u && u.startsWith("//") ? "https:" + u : u)).filter(Boolean);

  const color = text$($("[class*='product-intro__color-block'][class*='active'] + [class*='color-name'], [class*='current-color-name']").first()) || null;
  const sizes = uniq(
    $("[class*='product-intro__sizes-radio'] [class*='size-list__item'], [class*='product-intro__size-radio'] [class*='size'], [class*='size-radio'] [class*='item']")
      .map((_, e) => text$($(e))).get(),
  );

  const brand =
    text$($("[class*='product-intro__head-brand'], a[class*='brand-link']").first()) ||
    $("meta[property='og:brand']").attr("content") ||
    null;
  const availability =
    $("meta[itemprop='availability']").attr("content") ||
    text$($("[class*='out-of-stock'], [class*='sold-out']").first()) ||
    null;
  const description =
    $("meta[name='description']").attr("content") ||
    $("meta[property='og:description']").attr("content") ||
    null;
  const categories = uniq(
    $("[class*='breadcrumb'] a, [class*='crumb'] a, [class*='c-breadcrumb'] a").map((_, e) => text$($(e))).get(),
  );

  return {
    id: String(idFromUrl(url) || ""),
    url,
    title: title || "",
    brand,
    price,
    originalPrice,
    discount,
    currency,
    rating,
    reviews,
    images,
    color,
    sizes,
    availability,
    description,
    categories,
  };
}

export function parseSearch(html) {
  const $ = cheerio.load(html);
  const out = [];
  const seen = new Set();
  const cards = [
    "section[class*='product-card']",
    "section[data-locate-key]",
    "div[class*='product-list-item']",
    "div[class*='S-product-card']",
    "div[class*='product-card']",
    "li[class*='product-card']",
    "a[href*='-p-'][href$='.html']",
  ];
  for (const sel of cards) {
    $(sel).each((_, el) => {
      const card = $(el);
      const a = card.is("a") ? card : card.find("a[href*='-p-'], a[href*='.html']").first();
      let href = a.attr("href") || "";
      if (href.startsWith("//")) href = "https:" + href;
      if (!href) return;
      if (href.startsWith("/")) href = DEFAULT_HOST + href;
      const id = idFromUrl(href);
      if (!id || seen.has(id)) return;
      seen.add(id);
      const title =
        text$(card.find("[class*='goods-title-link'], [class*='product-card__goods-name'], [class*='card-name'], a[title]").first()) ||
        a.attr("title") ||
        text$(a) ||
        "";
      const image =
        card.find("img").first().attr("src") ||
        card.find("img").first().attr("data-src") ||
        null;
      const price = text$(card.find("[class*='product-card__price-sale'], [class*='product-card-sale-price'], [class*='from-skc']").first()) || text$(card.find("[class*='price']").first()) || null;
      const originalPrice = text$(card.find("[class*='product-card__price-original'], del, [class*='retail']").first()) || null;
      const discount = text$(card.find("[class*='product-card__discount'], [class*='discount-badge']").first()) || null;
      const rating = toFloat(text$(card.find("[class*='product-card__rate'], [class*='rating']").first()));
      out.push({
        id,
        title,
        url: href,
        image: image && image.startsWith("//") ? "https:" + image : image,
        price,
        originalPrice,
        discount,
        rating,
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

export async function scrapeSearch(query, maxPages = 1, host = DEFAULT_HOST) {
  const out = [];
  for (let page = 1; page <= maxPages; page++) {
    const slug = encodeURIComponent(String(query).trim().toLowerCase().replace(/\s+/g, "-"));
    const url = `${host}/pdsearch/${slug}/?page=${page}`;
    const html = await fetchRenderedHtml(url, "section[class*='product-card'], div[class*='product-card']", { autoScroll: true });
    out.push(...parseSearch(html));
  }
  return out;
}
