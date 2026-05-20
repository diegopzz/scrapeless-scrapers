// Walmart scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// the function names and emitted field names match verbatim. Data is extracted
// from the __NEXT_DATA__ script blob, not from DOM CSS selectors.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 300;

// Transient network failures we treat as retryable. Booking, ChatGPT and
// Walmart all sit behind aggressive CDNs that occasionally tear down the TLS
// tunnel mid-handshake — surfaced by puppeteer-core as one of these strings.
const TRANSIENT_NET_ERRORS = [
  "ERR_TUNNEL_CONNECTION_FAILED",
  "ERR_CONNECTION_CLOSED",
  "ERR_CONNECTION_RESET",
  "ERR_CONNECTION_REFUSED",
  "ERR_TIMED_OUT",
  "ERR_NETWORK_CHANGED",
  "ERR_EMPTY_RESPONSE",
  "ERR_PROXY_CONNECTION_FAILED",
  "Navigation timeout",
  "net::",
];

function isTransientError(err) {
  const msg = String(err?.message ?? err ?? "");
  return TRANSIENT_NET_ERRORS.some((s) => msg.includes(s));
}

function looksLikePerimeterxBlock(html) {
  if (!html) return true;
  // The PerimeterX interstitial body contains "px-captcha" or the
  // "_pxhd"/"px-captcha-wrapper" markers and never embeds __NEXT_DATA__.
  if (!html.includes("__NEXT_DATA__")) return true;
  if (html.includes("px-captcha") || html.includes("Robot or human?")) return true;
  return false;
}

// upstream filter — keep these in sync with the upstream reference's wanted_product_keys
const WANTED_PRODUCT_KEYS = [
  "availabilityStatus",
  "averageRating",
  "brand",
  "id",
  "imageInfo",
  "manufacturerName",
  "name",
  "orderLimit",
  "orderMinLimit",
  "priceInfo",
  "shortDescription",
  "type",
];

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function fetchRenderedHtml(url, readySelector, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 2, warmup = true } = {}) {
  let lastError;
  const totalAttempts = retries + 1;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const session = await client().browser.create({ proxyCountry, sessionTTL: DEFAULT_SESSION_TTL });
    let browser;
    try {
      browser = await puppeteer.connect({ browserWSEndpoint: session.browserWSEndpoint });
      const page = await browser.newPage();
      // Warm-up: hit walmart.com homepage first so the session picks up
      // PerimeterX cookies and a real visit history before navigating to
      // the product / search URL. PX is much less aggressive on second-hop.
      if (warmup) {
        try {
          await page.goto("https://www.walmart.com/", { waitUntil: "domcontentloaded", timeout: 45000 });
          await new Promise((r) => setTimeout(r, 2000));
        } catch (_) {}
      }
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
      // Wait for the React data blob to materialise rather than parsing
      // the raw shell HTML immediately — Walmart's React app injects
      // __NEXT_DATA__ once hydration starts.
      try {
        await page.waitForFunction(
          () => !!document.getElementById("__NEXT_DATA__"),
          { timeout: 25000 },
        );
      } catch (_) {
        if (readySelector) {
          try { await page.waitForSelector(readySelector, { timeout: 5000 }); } catch (_) {}
        }
      }
      const html = await page.content();
      if (!looksLikePerimeterxBlock(html)) return html;
      lastError = new Error("no __NEXT_DATA__ in response (likely PerimeterX interstitial)");
    } catch (e) {
      lastError = e;
      if (!isTransientError(e)) {
        // non-network error, still retry once but log shape
      }
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
    if (attempt < retries) {
      // Sleep 30s between PX retries — PerimeterX rate-limits new browser
      // sessions per /24, so spacing matters more than rotation.
      const sleepMs = 30000 * Math.pow(1.5, attempt);
      await new Promise((r) => setTimeout(r, sleepMs));
    }
  }
  throw new Error(`giving up after ${totalAttempts} attempts: ${lastError?.message}`);
}

function nextData(html) {
  const $ = cheerio.load(html);
  const raw = $("script#__NEXT_DATA__").first().contents().text();
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

// ---------------- product ----------------

export function parseProduct(html) {
  const data = nextData(html);
  if (!data) return null;
  let productRaw, reviewsRaw;
  try {
    productRaw = data.props.pageProps.initialData.data.product;
    reviewsRaw = data.props.pageProps.initialData.data.reviews;
  } catch {
    return null;
  }
  if (!productRaw) return null;
  const product = {};
  for (const k of WANTED_PRODUCT_KEYS) {
    if (k in productRaw) product[k] = productRaw[k];
  }
  return { product, reviews: reviewsRaw };
}

async function scrapeProductWithFallback(url) {
  try {
    const html = await fetchRenderedHtml(url, "script#__NEXT_DATA__");
    const parsed = parseProduct(html);
    if (parsed === null) return { url, error: "failed to parse" };
    return parsed;
  } catch (e) {
    return { url, error: String(e.message ?? e) };
  }
}

export async function scrapeProducts(urls) {
  const results = await Promise.all(urls.map(scrapeProductWithFallback));
  return results;
}

// ---------------- search ----------------

export function parseSearch(html) {
  const data = nextData(html);
  if (!data) return { results: [], total_results: 0 };
  try {
    const stack = data.props.pageProps.initialData.searchResult.itemStacks[0];
    return { results: stack.items ?? [], total_results: stack.count ?? 0 };
  } catch {
    return { results: [], total_results: 0 };
  }
}

function makeSearchUrl(query, page, sort) {
  const u = new URL("https://www.walmart.com/search");
  u.searchParams.set("q", query);
  u.searchParams.set("page", String(page));
  u.searchParams.set(sort, sort);
  u.searchParams.set("affinityOverride", "default");
  return u.toString();
}

export async function scrapeSearch(query = "", sort = "best_match", maxPages = null) {
  let firstHtml;
  try {
    firstHtml = await fetchRenderedHtml(makeSearchUrl(query, 1, sort), "script#__NEXT_DATA__");
  } catch (e) {
    // PerimeterX is more aggressive on /search than on /ip — return what we
    // have rather than propagating the failure.
    console.error(`[walmart] scrapeSearch page=1 blocked: ${e.message ?? e}`);
    return [];
  }
  const first = parseSearch(firstHtml);
  const out = [...first.results];
  const totalResults = first.total_results;
  let totalPages = totalResults ? Math.ceil(totalResults / 40) : 1;
  if (totalPages > 25) totalPages = 25;
  if (maxPages && maxPages < totalPages) totalPages = maxPages;

  for (let page = 2; page <= totalPages; page++) {
    try {
      const html = await fetchRenderedHtml(makeSearchUrl(query, page, sort), "script#__NEXT_DATA__");
      out.push(...parseSearch(html).results);
    } catch (e) {
      console.error(`[walmart] scrapeSearch page=${page} blocked: ${e.message ?? e}`);
      break;
    }
  }
  return out;
}
