// 1688 scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Under the hood:
// - `client.browser.create()` mints a cloud session on Scrapeless's Scraping Browser,
//   returning a CDP WebSocket endpoint (`browserWSEndpoint`).
// - puppeteer-core connects to that WebSocket, drives the page, returns rendered HTML.
// - cheerio parses the HTML into objects matching DATA_MODEL.md.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "CN";
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
  return "https://www.1688.com" + (url.startsWith("/") ? url : "/" + url);
}

function uniq(arr) {
  return Array.from(new Set(arr.filter(Boolean)));
}

function parseIdFromUrl(url) {
  if (!url) return "";
  const m = url.match(/offer\/(\d+)\.html/);
  if (m) return m[1];
  const m2 = url.match(/(\d{8,})/);
  return m2 ? m2[1] : "";
}

// ---------------- parsers ----------------

// Alibaba serves a "Sorry, we have detected unusual traffic" interstitial when
// the request fails its bot check. We surface that explicitly so the run
// script doesn't emit a hollow stub.
function detectCaptcha(html) {
  const t = (html || "").toLowerCase();
  if (t.includes("unusual traffic") || t.includes("captcha interception") || t.includes("captcha=true")) return true;
  if (t.includes("nocaptcha") && t.includes("punish")) return true;
  return false;
}

export function parseProduct(html, productId, url) {
  if (detectCaptcha(html)) {
    throw new Error(`1688: captcha interstitial served (Alibaba bot wall) — ${url}`);
  }
  const $ = cheerio.load(html);

  // gallery images: any img under the gallery + jsonld + meta.
  const images = uniq([
    ...$("div[class*='detail-gallery'] img, ul[class*='thumbnail'] img, .img-list img, img[class*='gallery']")
      .map((_, e) => $(e).attr("src") || $(e).attr("data-src")).get(),
    ...$("meta[property='og:image']").map((_, e) => $(e).attr("content")).get(),
  ]).map((u) => (u && u.startsWith("//") ? "https:" + u : u)).filter(Boolean);

  // title: prefer h1 / .d-title; fall back to og:title and <title>.
  const title =
    text$($("h1").first()) ||
    text$($("[class*='d-title'], [class*='title-text'], [class*='offer-title']").first()) ||
    $("meta[property='og:title']").attr("content") ||
    (($("title").text() || "").split("-")[0] || "").trim() ||
    "";

  // price + range: 1688 puts prices in spans like `.price`, `.value`, `.mod-detail-price`.
  const priceNodes = $("[class*='price'] [class*='value'], [class*='price-num'], .mod-detail-price .value, .price .value").map((_, e) => text$($(e))).get().filter(Boolean);
  const price = priceNodes[0] || null;
  let priceRange = null;
  if (priceNodes.length > 1) {
    priceRange = priceNodes.join(" - ");
  } else {
    const rangeText = text$($("[class*='price-range'], [class*='priceRange'], .price-range").first());
    if (rangeText) priceRange = rangeText;
  }

  // moq: text near "起订量" / "最小起订"
  let moq = null;
  $("[class*='obj-leading'], [class*='order-tip'], [class*='step-detail'], [class*='min-order'], [class*='moq']").each((_, e) => {
    const t = text$($(e));
    if (!moq && t && (/起订/.test(t) || /MOQ/i.test(t) || /件$/.test(t))) moq = t;
  });
  if (!moq) {
    const bodyText = $("body").text();
    const m = bodyText.match(/起订量[^0-9]{0,4}(\d[\d,]*\s*[件个套盒\w]*)/);
    if (m) moq = m[1].trim();
  }

  // seller + location: usually in side bar
  const seller =
    text$($("a[class*='company-name'], a[class*='supplier-name'], a[class*='shop-name']").first()) ||
    text$($("[class*='company-name'], [class*='supplier']").first()) ||
    null;
  const sellerUrl = abs($("a[class*='company-name'], a[class*='supplier-name'], a[class*='shop-name']").first().attr("href")) || null;
  const location =
    text$($("[class*='location'], [class*='address-info'], [class*='province']").first()) || null;

  // breadcrumb
  const categories = uniq(
    $("[class*='breadcrumb'] a, [class*='crumb'] a, .breadcrumb a").map((_, e) => text$($(e))).get(),
  );

  // description: meta description or og:description
  const description =
    $("meta[name='description']").attr("content") ||
    $("meta[property='og:description']").attr("content") ||
    null;

  return {
    id: String(productId),
    url,
    title: title || "",
    price,
    priceRange,
    moq,
    images,
    seller,
    sellerUrl,
    location,
    description,
    categories,
  };
}

export function parseSearch(html) {
  if (detectCaptcha(html)) {
    throw new Error("1688: captcha interstitial served on search (Alibaba bot wall)");
  }
  const $ = cheerio.load(html);
  const out = [];

  // search results card containers vary. We try several common patterns and dedupe on id.
  const cardSelectors = [
    "div[class*='offer-card']",
    "div[class*='space-offer-card']",
    "li[class*='offer-list']",
    "div[data-aplus-auto-clk]",
    "div[class*='SearchOfferCard']",
    "div.organic-list .organic-item",
    "div.offer",
  ];

  const seen = new Set();
  for (const sel of cardSelectors) {
    $(sel).each((_, el) => {
      const card = $(el);
      const link = card.find("a[href*='offer/'], a[href*='detail.1688.com'], a[href*='.alibaba.com']").first();
      let href = link.attr("href") || card.find("a").first().attr("href") || "";
      if (href && href.startsWith("//")) href = "https:" + href;
      const id = parseIdFromUrl(href);
      if (!id || seen.has(id)) return;
      seen.add(id);

      const title =
        text$(card.find("[class*='title'], [class*='offer-title'], [class*='subject']").first()) ||
        text$(card.find("a").first()) ||
        "";

      const image =
        card.find("img").first().attr("src") ||
        card.find("img").first().attr("data-src") ||
        null;

      const price = text$(card.find("[class*='price'], [class*='Price']").first()) || null;
      const moq = text$(card.find("[class*='moq'], [class*='order-tip'], [class*='step-tip']").first()) || null;
      const seller = text$(card.find("[class*='company'], [class*='supplier']").first()) || null;
      const location = text$(card.find("[class*='location'], [class*='address']").first()) || null;

      out.push({
        id,
        title,
        url: href,
        image: image && image.startsWith("//") ? "https:" + image : image,
        price,
        moq,
        seller,
        location,
      });
    });
  }
  return out;
}

// ---------------- scrape functions ----------------

export async function scrapeProduct(productId) {
  const url = `https://detail.1688.com/offer/${productId}.html`;
  const html = await fetchRenderedHtml(url, "body", { autoScroll: true });
  return parseProduct(html, productId, url);
}

export async function scrapeSearch(query, maxPages = 1) {
  const out = [];
  for (let page = 1; page <= maxPages; page++) {
    const url = `https://s.1688.com/selloffer/offer_search.htm?keywords=${encodeURIComponent(query)}&beginPage=${page}`;
    const html = await fetchRenderedHtml(url, "body", { autoScroll: true });
    out.push(...parseSearch(html));
  }
  return out;
}
