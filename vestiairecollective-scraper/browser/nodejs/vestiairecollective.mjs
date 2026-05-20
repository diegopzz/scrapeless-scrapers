// Vestiairecollective scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// the function names and emitted field names match verbatim.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 180;
const SEARCH_API_URL = "https://search.vestiairecollective.com/v1/product/search";

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

// ---------------- helpers ----------------

export function findHiddenData(html) {
  const $ = cheerio.load(html);
  const raw = $("script#__NEXT_DATA__").first().contents().text();
  if (!raw) throw new Error("__NEXT_DATA__ script not found");
  return JSON.parse(raw);
}

export function parseXhrCall(xhrRecords) {
  const searchCall = xhrRecords.find((c) => c.url && c.url.includes("search"));
  if (!searchCall) throw new Error("couldn't find the search xhr call — is the search URL valid?");
  const data = JSON.parse(searchCall.responseBody || "{}");
  return {
    headers: searchCall.requestHeaders || {},
    payload: JSON.parse(searchCall.requestPostData || "{}"),
    total_pages: data?.paginationStats?.totalPages ?? 1,
    data: data?.items ?? [],
  };
}

export function parseSearchApi(body) {
  const data = JSON.parse(body);
  return data?.items ?? [];
}

// ---------------- browser fetch ----------------

async function scrapeFirstSearchPage(url) {
  const { browserWSEndpoint } = await client().browser.create({
    proxyCountry: DEFAULT_PROXY_COUNTRY,
    sessionTTL: DEFAULT_SESSION_TTL,
  });
  const browser = await puppeteer.connect({ browserWSEndpoint });
  const xhr = [];
  try {
    const page = await browser.newPage();
    page.on("response", async (resp) => {
      try {
        if (!resp.url().includes("search")) return;
        if (resp.request().method() !== "POST") return;
        const body = await resp.text();
        xhr.push({
          url: resp.url(),
          requestHeaders: resp.request().headers(),
          requestPostData: resp.request().postData(),
          responseBody: body,
        });
      } catch (_) {}
    });

    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
    try { await page.waitForNetworkIdle({ timeout: 15000 }); } catch (_) {}
    const html = await page.content();
    return { html, xhr };
  } finally {
    try { await browser.close(); } catch (_) {}
  }
}

async function postSearchApi(headers, payload, offset) {
  const { browserWSEndpoint } = await client().browser.create({
    proxyCountry: DEFAULT_PROXY_COUNTRY,
    sessionTTL: DEFAULT_SESSION_TTL,
  });
  const browser = await puppeteer.connect({ browserWSEndpoint });
  try {
    const page = await browser.newPage();
    const nextPayload = JSON.parse(JSON.stringify(payload));
    nextPayload.pagination = nextPayload.pagination || {};
    nextPayload.pagination.offset = offset;

    const result = await page.evaluate(
      async ({ url, headers, body }) => {
        const resp = await fetch(url, {
          method: "POST",
          headers,
          body: JSON.stringify(body),
        });
        return await resp.text();
      },
      { url: SEARCH_API_URL, headers, body: nextPayload }
    );
    return result;
  } finally {
    try { await browser.close(); } catch (_) {}
  }
}

// ---------------- scrape functions ----------------

export async function scrapeProducts(urls) {
  const products = [];
  for (const url of urls) {
    const { browserWSEndpoint } = await client().browser.create({
      proxyCountry: DEFAULT_PROXY_COUNTRY,
      sessionTTL: DEFAULT_SESSION_TTL,
    });
    const browser = await puppeteer.connect({ browserWSEndpoint });
    try {
      const page = await browser.newPage();
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
      try { await page.waitForSelector("script#__NEXT_DATA__", { timeout: 15000 }); } catch (_) {}
      const html = await page.content();
      try {
        const data = findHiddenData(html);
        products.push(data?.props?.pageProps?.product);
      } catch (e) {
        // listing may be expired
      }
    } finally {
      try { await browser.close(); } catch (_) {}
    }
  }
  return products.filter(Boolean);
}

export async function scrapeSearch(url, maxPages = 10) {
  const first = await scrapeFirstSearchPage(url);
  const apiResult = parseXhrCall(first.xhr);
  const headers = apiResult.headers;
  const payload = apiResult.payload;
  const results = [...apiResult.data];
  let totalPages = apiResult.total_pages;
  if (maxPages && maxPages < totalPages) totalPages = maxPages;
  const totalProducts = totalPages * 48;

  for (let offset = 48; offset < totalProducts; offset += 48) {
    try {
      const body = await postSearchApi(headers, payload, offset);
      results.push(...parseSearchApi(body));
    } catch (_) {}
  }
  return results;
}
