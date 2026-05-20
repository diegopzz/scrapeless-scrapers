// Homegate scraper using @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Mirrors  —
// function names and emitted field names match verbatim.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const PROXY_COUNTRY = "CH";
const DEFAULT_SESSION_TTL = 180;

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function fetchRenderedHtml(url, readySelector, { proxyCountry = PROXY_COUNTRY, retries = 3, warmup = true } = {}) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    if (attempt > 0) await new Promise((r) => setTimeout(r, 8000 * attempt));
    const { browserWSEndpoint } = await client().browser.create({
      proxyCountry,
      sessionTTL: DEFAULT_SESSION_TTL,
    });
    let browser;
    try {
      browser = await puppeteer.connect({ browserWSEndpoint });
      const page = await browser.newPage();
      // Homegate (SIX-fronted) blocks direct deep links from cold sessions.
      // A homepage warm-up gets a session cookie so the listing URL renders.
      if (warmup) {
        try {
          await page.goto("https://www.homegate.ch/", { waitUntil: "domcontentloaded", timeout: 30000 });
          await new Promise((r) => setTimeout(r, 3500));
        } catch (_) {}
      }
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
      try { await page.waitForSelector(readySelector, { timeout: 20000 }); } catch (_) {}
      // Listings are rendered client-side; wait briefly for either the
      // __INITIAL_STATE__ blob (matches all paths) or the per-listing data.
      try {
        await page.waitForFunction(
          () => window.__INITIAL_STATE__ || document.body.innerText.length > 5000,
          { timeout: 15000 },
        );
      } catch (_) {}
      const html = await page.content();
      if (html && html.length > 20000) return html;
      lastError = new Error("interstitial / short HTML");
    } catch (e) {
      lastError = e;
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
  }
  throw new Error(`giving up after ${retries + 1} attempts: ${lastError?.message}`);
}

// ---------------- parsers ----------------

function bracketJson(script, marker) {
  const idx = script.indexOf(marker);
  if (idx === -1) return null;
  const start = script.indexOf("{", idx);
  if (start === -1) return null;
  let depth = 0;
  let end = start;
  for (let i = start; i < script.length; i++) {
    const ch = script[i];
    if (ch === "{") depth++;
    else if (ch === "}") {
      depth--;
      if (depth === 0) { end = i + 1; break; }
    }
  }
  return script.slice(start, end).replace(/undefined/g, "null");
}

export function parsePropertyPage(html) {
  const $ = cheerio.load(html);
  let script = "";
  $("script").each((_, el) => {
    const txt = $(el).html() || "";
    if (txt.includes("window.__PINIA_INITIAL_STATE__")) { script = txt; return false; }
  });
  if (!script) return null;
  const jsonStr = bracketJson(script, "window.__PINIA_INITIAL_STATE__");
  if (!jsonStr) return null;
  try {
    const data = JSON.parse(jsonStr);
    return data?.listing?.listing ?? null;
  } catch (_) { return null; }
}

export function parseNextData(html) {
  const $ = cheerio.load(html);
  let next = "";
  $("script").each((_, el) => {
    const txt = $(el).html() || "";
    if (txt.includes("window.__INITIAL_STATE__")) { next = txt; return false; }
  });
  if (!next) return null;
  try {
    return JSON.parse(next.split("=", 2)[1].trim());
  } catch (_) {
    // fallback to bracket-depth
    const jsonStr = bracketJson(next, "window.__INITIAL_STATE__");
    if (!jsonStr) return null;
    try { return JSON.parse(jsonStr); } catch (_) { return null; }
  }
}

export function parseSearchListings(html) {
  const data = parseNextData(html);
  if (!data) return [];
  return data?.resultList?.search?.fullSearch?.result?.listings ?? [];
}

// ---------------- scrape functions ----------------

export async function scrapeProperties(urls) {
  const out = [];
  for (const u of urls) {
    const html = await fetchRenderedHtml(u, "script");
    const parsed = parsePropertyPage(html);
    out.push(parsed ?? {});
  }
  return out;
}

export async function scrapeSearch(url, scrapeAllPages = false, maxScrapePages = 10) {
  const first = await fetchRenderedHtml(url, "script");
  const results = parseSearchListings(first);

  const data = parseNextData(first) || {};
  let totalPages = 1;
  try {
    totalPages = parseInt(data?.resultList?.search?.fullSearch?.result?.numberOfPages ?? 1, 10) || 1;
  } catch (_) {}
  if (!scrapeAllPages) totalPages = Math.min(totalPages, maxScrapePages);

  for (let page = 2; page <= totalPages; page++) {
    const sep = url.includes("?") ? "&" : "?";
    const pageUrl = `${url}${sep}ep=${page}`;
    const html = await fetchRenderedHtml(pageUrl, "script");
    const items = parseSearchListings(html);
    if (!items.length) break;
    results.push(...items);
  }
  return results;
}
