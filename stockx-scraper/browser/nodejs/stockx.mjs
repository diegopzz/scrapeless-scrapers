// StockX scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
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

async function fetchWithXhrs(url, { readySelector = null, proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 1 } = {}) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const { browserWSEndpoint } = await client().browser.create({
      proxyCountry,
      sessionTTL: DEFAULT_SESSION_TTL,
    });
    let browser;
    const xhr = [];
    try {
      browser = await puppeteer.connect({ browserWSEndpoint });
      const page = await browser.newPage();
      page.on("response", async (resp) => {
        try {
          const rt = resp.request().resourceType();
          if (rt !== "xhr" && rt !== "fetch") return;
          const ct = resp.headers()["content-type"] || "";
          if (!/json/i.test(ct)) return;
          const body = await resp.text();
          xhr.push({ url: resp.url(), body });
        } catch (_) {}
      });

      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
      if (readySelector) {
        try { await page.waitForSelector(readySelector, { timeout: 20000 }); } catch (_) {}
      }
      try { await page.waitForNetworkIdle({ timeout: 10000 }); } catch (_) {}
      const html = await page.content();
      if (html) return { html, xhr, finalUrl: page.url() };
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

function nestedLookup(key, obj, results = []) {
  if (obj && typeof obj === "object") {
    if (Array.isArray(obj)) {
      for (const v of obj) nestedLookup(key, v, results);
    } else {
      for (const [k, v] of Object.entries(obj)) {
        if (k === key) results.push(v);
        nestedLookup(key, v, results);
      }
    }
  }
  return results;
}

export function parseNextjs(html) {
  const $ = cheerio.load(html);
  let raw = $("script#__NEXT_DATA__").first().contents().text();
  if (!raw) {
    raw = $("script[data-name=query]").first().contents().text();
    if (raw) {
      const idx = raw.indexOf("=");
      raw = raw.slice(idx + 1).trim().replace(/;$/, "");
    }
  }
  if (!raw) throw new Error("__NEXT_DATA__ not found");
  return JSON.parse(raw);
}

export function parsePricing(xhrs, sku = null) {
  const parsed = [];
  for (const x of xhrs) {
    try { parsed.push(JSON.parse(x.body)); } catch (_) {}
  }
  for (const x of parsed) {
    if (!x || typeof x !== "object") continue;
    const product = x?.data?.product;
    if (!product || !product.uuid) continue;
    if (sku == null || sku === product.uuid) {
      return {
        minimumBid: product.minimumBid,
        market: product.market,
        variants: product.variants,
      };
    }
  }
  return null;
}

// ---------------- scrape functions ----------------

export async function scrapeProduct(url) {
  const fetched = await fetchWithXhrs(url, { readySelector: "h2[data-testid='trade-box-buy-amount']" });
  const data = parseNextjs(fetched.html);
  const products = nestedLookup("product", data);
  const product = products.find(
    (p) => p && typeof p === "object" && p.urlKey && fetched.finalUrl.includes(p.urlKey)
  );
  if (!product) throw new Error(`could not find product dataset in page cache for ${url}`);
  product.pricing = parsePricing(fetched.xhr, product.id);
  return product;
}

export async function scrapeSearch(url, maxPages = 25) {
  const first = await fetchWithXhrs(url, { readySelector: null });
  const data = parseNextjs(first.html);
  const firstResults = nestedLookup("results", data)[0];
  const paging = firstResults?.pageInfo ?? {};
  let totalPages = paging.pageCount ?? Math.ceil((paging.total ?? 0) / Math.max(paging.limit ?? 1, 1));
  if (maxPages < totalPages) totalPages = maxPages;

  const previews = (firstResults?.edges ?? []).map((e) => e.node);

  if (totalPages > 1) {
    for (let page = 2; page <= totalPages; page++) {
      const sep = url.includes("?") ? "&" : "?";
      const pageUrl = `${url}${sep}page=${page}`;
      const fetched = await fetchWithXhrs(pageUrl, { readySelector: null });
      const pageData = parseNextjs(fetched.html);
      const pageResults = nestedLookup("results", pageData)[0];
      previews.push(...(pageResults?.edges ?? []).map((e) => e.node));
    }
  }
  return previews;
}
