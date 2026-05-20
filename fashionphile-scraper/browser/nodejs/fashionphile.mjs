// Fashionphile scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
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

async function fetchRendered(url, { readySelector = null, proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 1 } = {}) {
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
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
      if (readySelector) {
        try { await page.waitForSelector(readySelector, { timeout: 15000 }); } catch (_) {}
      }
      const html = await page.content();
      if (html) return html;
      lastError = new Error("empty content");
    } catch (e) {
      lastError = e;
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
  }
  throw new Error(`giving up after ${retries + 1} attempts: ${lastError?.message}`);
}

// ---------------- helpers ----------------

export function convertToJsonUrls(urls) {
  return urls.map((u) => u.replace("/p/", "/products/") + ".json");
}

export function parsePrice(text) {
  if (!text) return 0;
  const digits = String(text).replace(/[$,\s]/g, "");
  const n = parseInt(digits, 10);
  return Number.isNaN(n) ? 0 : n;
}

export function extractProductFromCard($, card) {
  const productId = card.attr("data-product-id") || "";
  const brand_name = (card.find(".fp-card__vendor").first().text() || "").trim();
  const product_name = (card.find(".fp-card__link__product-name").first().text() || "").trim();
  const condition = (card.find(".fp-condition").first().text() || "").trim();

  const regularPriceText = (card.find(".price-item--regular").first().text() || "").trim();
  const salePriceText = (card.find(".price-item--sale.price-item--last").first().text() || "").trim();

  let priceText;
  if (salePriceText) priceText = salePriceText;
  else if (regularPriceText) priceText = regularPriceText;
  else priceText = (card.find(".price-item").first().text() || "$0").trim();

  const price = parsePrice(priceText);
  let discounted_price = 0;
  if (regularPriceText && salePriceText) {
    discounted_price = parsePrice(regularPriceText) - price;
  }

  return {
    brand_name,
    product_name,
    condition,
    discounted_price,
    price,
    id: /^\d+$/.test(productId) ? parseInt(productId, 10) : 0,
  };
}

// ---------------- scrape functions ----------------

export async function scrapeProducts(urls) {
  const jsonUrls = convertToJsonUrls(urls);
  const products = [];
  for (const url of jsonUrls) {
    const content = await fetchRendered(url, { readySelector: null });
    let data;
    try {
      data = JSON.parse(content);
    } catch (_) {
      const $ = cheerio.load(content);
      const body = $("pre").first().text() || $("body").text();
      data = JSON.parse(body);
    }
    if (data && typeof data === "object" && data.product) products.push(data.product);
    else products.push(data);
  }
  return products;
}

export async function scrapeSearch(url, maxPages = 10) {
  const html = await fetchRendered(url, { readySelector: ".fp-algolia-product-card" });
  const $ = cheerio.load(html);
  const results = [];
  $(".fp-algolia-product-card").each((_, el) => {
    try { results.push(extractProductFromCard($, $(el))); } catch (_) {}
  });

  const paginationHref = $(".ais-Pagination-item--lastPage a").first().attr("href") || "";
  let totalPages = 1;
  const m = paginationHref.match(/page=(\d+)/);
  if (m) totalPages = parseInt(m[1], 10);
  if (maxPages && maxPages < totalPages) totalPages = maxPages;

  if (totalPages > 1) {
    const baseUrl = url.split("?")[0];
    for (let page = 2; page <= totalPages; page++) {
      const pageUrl = `${baseUrl}?page=${page}`;
      const pageHtml = await fetchRendered(pageUrl, { readySelector: ".fp-algolia-product-card" });
      const $$ = cheerio.load(pageHtml);
      $$(".fp-algolia-product-card").each((_, el) => {
        try { results.push(extractProductFromCard($$, $$(el))); } catch (_) {}
      });
    }
  }
  return results;
}
