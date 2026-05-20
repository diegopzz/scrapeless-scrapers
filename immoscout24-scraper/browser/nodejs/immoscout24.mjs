// Immoscout24 (Swiss) scraper using @scrapeless-ai/sdk + puppeteer-core over CDP.
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
      // ImmoScout24 (SIX-fronted, same anti-bot stack as Homegate) interstitial-
      // gates direct deep links. Warming up at the homepage gets a session
      // cookie so the next navigation returns the real Pinia state.
      if (warmup) {
        try {
          await page.goto("https://www.immoscout24.ch/", { waitUntil: "domcontentloaded", timeout: 30000 });
          await new Promise((r) => setTimeout(r, 3500));
        } catch (_) {}
      }
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
      try { await page.waitForSelector(readySelector, { timeout: 20000 }); } catch (_) {}
      try {
        await page.waitForFunction(
          () => window.__PINIA_INITIAL_STATE__ || document.body.innerText.length > 5000,
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

// Bracket-depth extraction of the Pinia state.
function extractPiniaState(html) {
  const $ = cheerio.load(html);
  let script = "";
  $("script").each((_, el) => {
    const txt = $(el).html() || "";
    if (txt.includes("window.__PINIA_INITIAL_STATE__")) {
      script = txt;
      return false;
    }
  });
  if (!script) return null;
  const idx = script.indexOf("window.__PINIA_INITIAL_STATE__");
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
  const jsonStr = script.slice(start, end).replace(/undefined/g, "null");
  try { return JSON.parse(jsonStr); } catch (_) { return null; }
}

// ---------------- parsers ----------------

export function parsePropertyPage(html) {
  const data = extractPiniaState(html);
  if (!data) return {};
  return data?.listing?.listing ?? {};
}

// Each listing on the modern Immoscout24 SERP carries a schema.org `Product`
// JSON-LD block (name="<address> - CHF <price> - <rooms>", image, offers, url).
// Pinia state isn't exposed on the window anymore.
export function parseSearchPage(html) {
  const $ = cheerio.load(html);
  // First try the legacy Pinia path; if it lands data, prefer it.
  const data = extractPiniaState(html);
  const legacy = data?.resultList?.search?.fullSearch?.result?.listings;
  if (Array.isArray(legacy) && legacy.length) return legacy;
  const out = [];
  $('script[type="application/ld+json"]').each((_, el) => {
    let node;
    try { node = JSON.parse($(el).contents().text()); } catch (_) { return; }
    const nodes = Array.isArray(node) ? node : [node];
    for (const n of nodes) {
      if (!n || typeof n !== "object") continue;
      const t = n["@type"];
      const types = Array.isArray(t) ? t : [t];
      if (!types.includes("Product")) continue;
      const name = (n.name ?? "").toString();
      if (!/CHF/i.test(name)) continue; // skip the search-summary Product node
      const offer = Array.isArray(n.offers) ? n.offers[0] : n.offers;
      const priceText = offer?.price ?? null;
      const url = n.url ?? null;
      // DATA_MODEL.SearchResultEntry requires a `listing` sub-object so the
      // schema lines up with the legacy Pinia payload shape.
      out.push({
        listing: {
          id: url ? url.split("/").pop() : null,
          name,
          url,
          image: n.image ?? null,
          description: n.description ?? null,
          price: priceText ? parseFloat(priceText) : null,
          priceCurrency: offer?.priceCurrency ?? null,
          rawJsonLd: n,
        },
      });
    }
  });
  return out;
}

// ---------------- scrape functions ----------------

const PINIA_READY = "script";

export async function scrapeProperties(urls) {
  const out = [];
  for (const u of urls) {
    try {
      const html = await fetchRenderedHtml(u, PINIA_READY);
      const parsed = parsePropertyPage(html);
      // Skip empty objects (listing 404'd or page didn't render the Pinia state).
      if (parsed && Object.keys(parsed).length > 0) out.push(parsed);
    } catch (_) {
      // network error / interstitial — skip this URL
    }
  }
  return out;
}

export async function scrapeSearch(url, scrapeAllPages = false, maxScrapePages = 10) {
  const first = await fetchRenderedHtml(url, PINIA_READY);
  const results = parseSearchPage(first);
  const state = extractPiniaState(first) || {};
  let totalPages = 1;
  try {
    totalPages = parseInt(state?.resultList?.search?.fullSearch?.result?.numberOfPages ?? 1, 10) || 1;
  } catch (_) {}
  if (!scrapeAllPages) totalPages = Math.min(totalPages, maxScrapePages);

  for (let page = 2; page <= totalPages; page++) {
    const sep = url.includes("?") ? "&" : "?";
    const pageUrl = `${url}${sep}pn=${page}`;
    const html = await fetchRenderedHtml(pageUrl, PINIA_READY);
    const items = parseSearchPage(html);
    if (!items.length) break;
    results.push(...items);
  }
  return results;
}
