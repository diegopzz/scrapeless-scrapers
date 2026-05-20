// Immowelt scraper using @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Mirrors  —
// function names and emitted field names match verbatim.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";
import LZString from "lz-string";

const PROXY_COUNTRY = "DE";
const DEFAULT_SESSION_TTL = 180;

const SEARCH_KEYS = ["sections", "id", "brand", "tags", "contactSections"];

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function fetchRenderedHtml(url, readySelector, { proxyCountry = PROXY_COUNTRY, retries = 1 } = {}) {
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
      try { await page.waitForSelector(readySelector, { timeout: 20000 }); } catch (_) {}
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

// ---------------- parsers ----------------

export function parseSearch(html) {
  const $ = cheerio.load(html);
  let out = [];
  $("script").each((_, el) => {
    const txt = $(el).html() || "";
    if (!txt.includes("classified-serp-init-data")) return;
    const m = /JSON\.parse\("(.+?)"\)/s.exec(txt);
    if (!m) return;
    try {
      const inner = JSON.parse(`"${m[1]}"`);
      let data = JSON.parse(inner);
      // Modern Immowelt embeds a GraphQL response shape; the actual init payload
      // is an LZ-string base64-encoded string at `data.data["classified-serp-init-data"]`.
      // Older builds used a `compressed` key at the root.
      let payloadStr = null;
      if (data?.data && typeof data.data["classified-serp-init-data"] === "string") {
        payloadStr = data.data["classified-serp-init-data"];
      } else if (data?.compressed && typeof data.compressed === "string") {
        payloadStr = data.compressed;
      }
      if (payloadStr) {
        const dec = LZString.decompressFromBase64(payloadStr);
        if (dec) data = JSON.parse(dec);
      }
      const classifieds = data?.pageProps?.classifiedsData ?? data?.classifiedsData;
      if (classifieds) {
        out = Array.isArray(classifieds) ? classifieds : Object.values(classifieds);
        return false;
      }
    } catch (_) {}
  });
  return out;
}

function findListing(node) {
  if (node && typeof node === "object" && !Array.isArray(node)) {
    if ("sections" in node && "id" in node) return node;
    for (const v of Object.values(node)) {
      const found = findListing(v);
      if (found) return found;
    }
  } else if (Array.isArray(node)) {
    for (const v of node) {
      const found = findListing(v);
      if (found) return found;
    }
  }
  return null;
}

export function parseProperty(html) {
  const $ = cheerio.load(html);
  let result = {};
  $("script").each((_, el) => {
    const txt = $(el).html() || "";
    if (!txt.includes("UFRN_LIFECYCLE_SERVERREQUEST")) return;
    const m = /JSON\.parse\("(.+?)"\)/s.exec(txt);
    if (!m) return;
    try {
      const inner = JSON.parse(`"${m[1]}"`);
      const data = JSON.parse(inner);
      const listing = findListing(data);
      if (listing) {
        result = Object.fromEntries(SEARCH_KEYS.map((k) => [k, listing[k]]));
        return false;
      }
    } catch (_) {}
  });
  return result;
}

// ---------------- scrape functions ----------------

export async function scrapeSearch(url, maxScrapePages = null) {
  const first = await fetchRenderedHtml(url, "body");
  const out = parseSearch(first);

  const $ = cheerio.load(first);
  let totalPages = 1;
  $("a[href*='page=']").each((_, el) => {
    const href = $(el).attr("href") || "";
    const m = /[?&]page=(\d+)/.exec(href);
    if (m) totalPages = Math.max(totalPages, parseInt(m[1], 10));
  });
  if (maxScrapePages) totalPages = Math.min(totalPages, maxScrapePages);

  for (let page = 2; page <= totalPages; page++) {
    const sep = url.includes("?") ? "&" : "?";
    const pageUrl = `${url}${sep}page=${page}`;
    const html = await fetchRenderedHtml(pageUrl, "body");
    const items = parseSearch(html);
    if (!items.length) break;
    out.push(...items);
  }
  return out;
}

export async function scrapeProperties(urls) {
  const out = [];
  for (const u of urls) {
    const html = await fetchRenderedHtml(u, "body");
    out.push(parseProperty(html));
  }
  return out;
}
