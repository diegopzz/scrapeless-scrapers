// Trustpilot scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// the function names and emitted field shapes match verbatim, so downstream code
// can import { Scrapeless } from "@scrapeless-ai/sdk";
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

async function fetchRenderedHtml(url, readySelector = "script#__NEXT_DATA__", { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 1 } = {}) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const { browserWSEndpoint } = await client().browser.create({ proxyCountry, sessionTTL: DEFAULT_SESSION_TTL });
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
      lastError = new Error("empty HTML");
    } catch (e) {
      lastError = e;
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
  }
  throw new Error(`giving up after ${retries + 1} attempts: ${lastError?.message}`);
}

async function fetchJson(url, { proxyCountry = DEFAULT_PROXY_COUNTRY } = {}) {
  const { browserWSEndpoint } = await client().browser.create({ proxyCountry, sessionTTL: DEFAULT_SESSION_TTL });
  let browser;
  try {
    browser = await puppeteer.connect({ browserWSEndpoint });
    const page = await browser.newPage();
    try {
      await page.goto("https://www.trustpilot.com/", { waitUntil: "domcontentloaded", timeout: 30000 });
    } catch (_) {}
    const text = await page.evaluate(
      async (u) => {
        const r = await fetch(u, { credentials: "include" });
        return await r.text();
      },
      url,
    );
    return text;
  } finally {
    try { await browser?.close(); } catch (_) {}
  }
}

// ---------------- parsers ----------------

export function parseHiddenData(html) {
  const $ = cheerio.load(html);
  const script = $("script#__NEXT_DATA__").first().contents().text();
  if (!script) return {};
  return JSON.parse(script);
}

export function parseCompanyData(data) {
  const pp = data?.props?.pageProps ?? {};
  return {
    pageUrl: pp.pageUrl ?? null,
    companyDetails: pp.businessUnit ?? null,
    reviews: pp.reviews ?? [],
  };
}

// ---------------- scrape functions ----------------

export async function scrapeCompany(urls) {
  const out = [];
  for (const url of urls) {
    const html = await fetchRenderedHtml(url);
    const data = parseHiddenData(html);
    out.push(parseCompanyData(data));
  }
  return out;
}

export async function scrapeSearch(url, maxPages = null) {
  const firstHtml = await fetchRenderedHtml(url);
  const businessUnits = parseHiddenData(firstHtml)?.props?.pageProps?.businessUnits ?? {};
  const searchData = [...(businessUnits.businesses ?? [])];
  let totalPages = businessUnits.totalPages ?? 1;
  if (maxPages && maxPages < totalPages) totalPages = maxPages;

  for (let page = 2; page <= totalPages; page++) {
    try {
      const html = await fetchRenderedHtml(`${url}?page=${page}`);
      const businesses = parseHiddenData(html)?.props?.pageProps?.businessUnits?.businesses ?? [];
      searchData.push(...businesses);
    } catch (_) {}
  }
  return searchData;
}

export async function getReviewsApiUrl(url) {
  const html = await fetchRenderedHtml(url);
  const data = parseHiddenData(html);
  const buildId = data.buildId;
  const businessUnit = url.split("review/").slice(-1)[0];
  return `https://www.trustpilot.com/_next/data/${buildId}/review/${businessUnit}.json?sort=recency&businessUnit=${businessUnit}`;
}

export async function scrapeReviews(url, maxPages = null) {
  const apiUrl = await getReviewsApiUrl(url);
  const firstText = await fetchJson(apiUrl);
  const firstData = JSON.parse(firstText).pageProps ?? {};
  const reviewsData = [...(firstData.reviews ?? [])];
  let totalPages = firstData?.filters?.pagination?.totalPages ?? 1;
  if (maxPages && maxPages < totalPages) totalPages = maxPages;

  for (let page = 2; page <= totalPages; page++) {
    try {
      const text = await fetchJson(`${apiUrl}&page=${page}`);
      const pageReviews = JSON.parse(text)?.pageProps?.reviews ?? [];
      reviewsData.push(...pageReviews);
    } catch (_) {}
  }
  return reviewsData;
}
