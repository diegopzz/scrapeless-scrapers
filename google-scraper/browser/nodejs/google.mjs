// Google scraper using @scrapeless-ai/sdk.
//
// Mirrors  —
// function names and emitted field names match verbatim.
//
// Two surfaces:
// - SERP + keyword suggestions: client.deepserp.scrape({ actor: "scraper.google.search", ... }).
// - Google Maps places: client.browser.create(...) + puppeteer-core over CDP.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 180;
const GOOGLE_SERP_ACTOR = "scraper.google.search";

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function deepserpSearch(query, { start = 0, hl = "en", gl = "us" } = {}) {
  const input = { q: query, hl, gl };
  if (start) input.start = start;
  const result = await client().deepserp.scrape({ actor: GOOGLE_SERP_ACTOR, input });
  if (result && typeof result === "object" && result.data && typeof result.data === "object") {
    return result.data;
  }
  return result ?? {};
}

async function fetchRenderedHtml(url, readySelector, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 1 } = {}) {
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
      try {
        await page.waitForSelector(readySelector, { timeout: 15000 });
      } catch (_) {}
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

// ---------------- scrape functions ----------------

export async function scrapeSerp(query, maxPages = 1) {
  const pages = maxPages ?? 1;
  const out = [];
  let position = 0;
  for (let p = 0; p < pages; p++) {
    const data = await deepserpSearch(query, { start: p * 10 });
    for (const item of extractOrganic(data)) {
      position += 1;
      const url = item.url ?? item.link ?? "";
      out.push({
        position,
        title: (item.title ?? "").trim(),
        url,
        origin: item.origin ?? item.source ?? "",
        domain: domainOf(url),
        description: (item.description ?? item.snippet ?? "").trim(),
        date: item.date ?? "",
      });
    }
  }
  return out;
}

export async function scrapeKeywords(query) {
  const data = await deepserpSearch(query);
  return {
    related_search: extractRelated(data),
    people_ask_for: extractPaa(data),
  };
}

export async function scrapeGoogleMapPlaces(urls) {
  const out = [];
  for (const url of urls) {
    const html = await fetchRenderedHtml(url, "h1");
    out.push(parsePlace(html));
  }
  return out;
}

// ---------------- Deep SerpApi shape helpers ----------------

function extractOrganic(data) {
  for (const key of ["organic_results", "organic", "results"]) {
    if (Array.isArray(data?.[key])) return data[key];
  }
  return [];
}

function extractRelated(data) {
  for (const key of ["related_searches", "related_search"]) {
    const items = data?.[key];
    if (!Array.isArray(items)) continue;
    const out = [];
    for (const it of items) {
      if (typeof it === "string") out.push(it.trim());
      else if (it && typeof it === "object") {
        const val = it.query ?? it.name ?? it.text ?? "";
        if (val) out.push(String(val).trim());
      }
    }
    return out.filter(Boolean);
  }
  return [];
}

function extractPaa(data) {
  for (const key of ["related_questions", "people_also_ask", "people_ask_for"]) {
    const items = data?.[key];
    if (!Array.isArray(items)) continue;
    const out = [];
    for (const it of items) {
      if (typeof it === "string") out.push(it.trim());
      else if (it && typeof it === "object") {
        const val = it.question ?? it.title ?? it.query ?? "";
        if (val) out.push(String(val).trim());
      }
    }
    return out.filter(Boolean);
  }
  return [];
}

function domainOf(url) {
  try {
    let host = new URL(url).hostname || "";
    if (host.startsWith("www.")) host = host.slice(4);
    return host;
  } catch {
    return "";
  }
}

// ---------------- Maps place parser ----------------

const STARS_RE = /\d+(?:[,.]\d+)?/g;

function ariaWithLabel($, label) {
  const raw = $(`[aria-label^="${label}"]`).first().attr("aria-label") || "";
  return raw.replace(label, "").trim();
}

function ariaContains($, needle) {
  const found = $(`[aria-label*="${needle}"]`).first().attr("aria-label") || "";
  return found;
}

function starBucket($, bucket) {
  const raw = $(`[aria-label*="${bucket}"]`).first().attr("aria-label") || "";
  const nums = raw.match(STARS_RE);
  return nums ? nums[nums.length - 1] : "";
}

export function parsePlace(html) {
  const $ = cheerio.load(html);
  const starsLabel = ariaContains($, " stars");
  const starsMatch = starsLabel.match(/\d+(?:[,.]\d+)?/);
  return {
    name: $("h1").first().text().trim(),
    category: $("button[jsaction*='category']").first().text().trim(),
    address: ariaWithLabel($, "Address: "),
    website: ariaWithLabel($, "Website: "),
    phone: ariaWithLabel($, "Phone: "),
    review_count: ariaContains($, " reviews"),
    stars: starsMatch ? starsMatch[0] : "",
    "5_stars": starBucket($, "5 stars"),
    "4_stars": starBucket($, "4 stars"),
    "3_stars": starBucket($, "3 stars"),
    "2_stars": starBucket($, "2 stars"),
    "1_stars": starBucket($, "1 stars"),
  };
}
