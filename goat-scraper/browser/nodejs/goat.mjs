// Goat scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// the function names and emitted field names match verbatim.

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

export function findHiddenData(html) {
  const $ = cheerio.load(html);
  const raw = $("script#__NEXT_DATA__").first().contents().text();
  if (!raw) throw new Error("__NEXT_DATA__ script not found");
  return JSON.parse(raw);
}

function extractJsonPayload(html) {
  try {
    return JSON.parse(html);
  } catch (_) {
    const $ = cheerio.load(html);
    const body = $("pre").first().text() || $("body").text();
    return JSON.parse(body);
  }
}

// ---------------- scrape functions ----------------

export async function scrapeProducts(urls) {
  const products = [];
  for (const url of urls) {
    const html = await fetchRendered(url, { readySelector: "script#__NEXT_DATA__" });
    const data = findHiddenData(html);
    const pageProps = data?.props?.pageProps ?? {};
    const product = pageProps.productTemplate ?? {};
    product.offers = pageProps.offers ? pageProps.offers.offerData : null;
    products.push(product);
  }
  return products;
}

export async function scrapeSearch(query, maxPages = 10) {
  const makePageUrl = (page = 1) => {
    const params = new URLSearchParams({
      queryString: query,
      pageLimit: "12",
      pageNumber: String(page),
      sortType: "1",
    });
    return `https://www.goat.com/web-api/consumer-search/get-product-search-results?${params.toString()}`;
  };

  const firstHtml = await fetchRendered(makePageUrl(1));
  const firstData = (extractJsonPayload(firstHtml).data) ?? {};
  const results = [...(firstData.productsList ?? [])];
  const totalResults = firstData.totalResults ?? 0;
  const perPage = 12;
  let totalPages = totalResults ? Math.ceil(totalResults / perPage) : 1;
  if (maxPages && maxPages < totalPages) totalPages = maxPages;

  if (totalPages > 1) {
    for (let page = 2; page <= totalPages; page++) {
      const html = await fetchRendered(makePageUrl(page));
      const data = (extractJsonPayload(html).data) ?? {};
      results.push(...(data.productsList ?? []));
    }
  }
  return results;
}
