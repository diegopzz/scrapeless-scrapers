// Zillow scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// function names and emitted field names match verbatim.
//
// Discovery: Zillow's property page embeds `__NEXT_DATA__` (modern) or
// `hdpApolloPreloadedData` (legacy) script tags containing the full property JSON.
// We render the page through a Scrapeless Scraping Browser session (residential
// proxy + DataDome mitigation), then parse the embedded JSON.
//
// For search, we bootstrap the queryState from the first page's `__NEXT_DATA__`
// then call `async-create-search-page-state` with PUT from inside the page so
// TLS + cookie fingerprint stay sticky.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 180;
const BACKEND_SEARCH_URL = "https://www.zillow.com/async-create-search-page-state";

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function newBrowser(proxyCountry = DEFAULT_PROXY_COUNTRY) {
  const { browserWSEndpoint } = await client().browser.create({
    proxyCountry,
    sessionTTL: DEFAULT_SESSION_TTL,
  });
  return browserWSEndpoint;
}

async function fetchRenderedHtml(url, readySelector, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 1 } = {}) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const ws = await newBrowser(proxyCountry);
    let browser;
    try {
      browser = await puppeteer.connect({ browserWSEndpoint: ws });
      const page = await browser.newPage();
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
      if (readySelector) {
        try { await page.waitForSelector(readySelector, { timeout: 15000 }); } catch (_) {}
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

function createSearchPayload(queryData, pageNumber) {
  const payload = {
    searchQueryState: queryData,
    wants: { cat1: ["listResults", "mapResults"], cat2: ["total"] },
    requestId: Math.floor(Math.random() * 9) + 2,
  };
  if (pageNumber) payload.searchQueryState.pagination = { currentPage: pageNumber };
  return JSON.stringify(payload);
}

// ---------------- scrape functions (mirror the upstream reference's exports) ----------------

export async function scrapeSearch(url, maxScrapePages = null) {
  const searchData = [];
  const ws = await newBrowser();
  let browser;
  try {
    browser = await puppeteer.connect({ browserWSEndpoint: ws });
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
    try { await page.waitForSelector("script#__NEXT_DATA__", { timeout: 15000 }); } catch (_) {}
    const html = await page.content();
    const $ = cheerio.load(html);
    const nextDataText = $("script#__NEXT_DATA__").first().text();
    if (!nextDataText) throw new Error("missing __NEXT_DATA__ on search page");
    const scriptData = JSON.parse(nextDataText);
    const queryData = scriptData.props.pageProps.searchPageState.queryState;

    const callBackend = async (body) => {
      const text = await page.evaluate(async ({ url, body }) => {
        const res = await fetch(url, {
          method: "PUT",
          headers: { "content-type": "application/json" },
          body,
        });
        return await res.text();
      }, { url: BACKEND_SEARCH_URL, body });
      return JSON.parse(text);
    };

    const first = await callBackend(createSearchPayload(queryData));
    searchData.push(...first.cat1.searchResults.listResults);
    let totalPages = first.cat1.searchList.totalPages;
    if (totalPages > 1) {
      if (maxScrapePages && maxScrapePages < totalPages) totalPages = maxScrapePages;
      for (let p = 2; p <= totalPages; p++) {
        const pageData = await callBackend(createSearchPayload(queryData, p));
        searchData.push(...pageData.cat1.searchResults.listResults);
      }
    }
  } finally {
    try { await browser?.close(); } catch (_) {}
  }
  return searchData;
}

export async function scrapeProperties(urls) {
  const out = [];
  for (const url of urls) {
    const html = await fetchRenderedHtml(url, "script#__NEXT_DATA__");
    out.push(parseProperty(html));
  }
  return out;
}

// ---------------- parsers ----------------

export function parseProperty(html) {
  const $ = cheerio.load(html);
  const nextText = $("script#__NEXT_DATA__").first().text();
  if (nextText) {
    const data = JSON.parse(nextText);
    const cache = JSON.parse(data.props.pageProps.componentProps.gdpClientCache);
    const firstKey = Object.keys(cache)[0];
    return cache[firstKey].property;
  }
  const apolloText = $("script#hdpApolloPreloadedData").first().text();
  if (!apolloText) throw new Error("no property JSON found on page");
  const apollo = JSON.parse(JSON.parse(apolloText).apiCache);
  for (const [k, v] of Object.entries(apollo)) {
    if (k.includes("ForSale")) return v.property;
  }
  throw new Error("no ForSale entry in hdpApolloPreloadedData");
}
