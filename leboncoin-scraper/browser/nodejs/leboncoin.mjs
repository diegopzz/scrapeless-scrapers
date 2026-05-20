// Leboncoin scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "FR";
const DEFAULT_SESSION_TTL = 180;

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function fetchRenderedHtml(url, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 2 } = {}) {
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
      try {
        await page.waitForSelector("script#__NEXT_DATA__", { timeout: 20000 });
      } catch (_) {}
      const html = await page.content();
      if (html && html.includes("__NEXT_DATA__")) return html;
      lastError = new Error("blocked / empty NEXT_DATA");
    } catch (e) {
      lastError = e;
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
  }
  throw new Error(`giving up after ${retries + 1} attempts: ${lastError?.message}`);
}

// ---------------- parsers (verbatim from the upstream reference) ----------------

function loadNextData(html) {
  const $ = cheerio.load(html);
  const text = $("script#__NEXT_DATA__").html();
  if (!text) throw new Error("__NEXT_DATA__ not found");
  return JSON.parse(text);
}

export function parseSearch(html) {
  return loadNextData(html).props.pageProps.searchData.ads;
}

export function maxSearchPages(html) {
  return loadNextData(html).props.pageProps.searchData.max_pages;
}

export function parseAd(html) {
  return loadNextData(html).props.pageProps.ad;
}

// ---------------- scrape functions ----------------

export async function scrapeSearch(url, scrapeAllPages, maxPages = 10) {
  const firstHtml = await fetchRenderedHtml(url);
  const searchData = parseSearch(firstHtml);
  const totalSearchPages = maxSearchPages(firstHtml);

  const totalPages =
    scrapeAllPages === false && maxPages < totalSearchPages ? maxPages : totalSearchPages;

  const sep = url.includes("?") ? "&" : "?";
  for (let page = 2; page <= totalPages; page++) {
    const pageUrl = `${url}${sep}page=${page}`;
    try {
      const html = await fetchRenderedHtml(pageUrl);
      searchData.push(...parseSearch(html));
    } catch (e) {
      console.error(`search page ${page} failed:`, e.message);
    }
  }
  return searchData;
}

export async function scrapeAd(url, _retries = 0) {
  try {
    const html = await fetchRenderedHtml(url);
    return parseAd(html);
  } catch (e) {
    if (_retries < 2) return scrapeAd(url, _retries + 1);
    console.error(`ad ${url} failed after retries:`, e.message);
    return null;
  }
}
