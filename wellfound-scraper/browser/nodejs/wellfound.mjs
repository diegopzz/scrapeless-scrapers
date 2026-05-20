// Wellfound (formerly AngelList) scraper using @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// function names and emitted field names match verbatim, including the upstream
// `remtoe` typo on JobData.

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
function client() { return new Scrapeless({ apiKey: requireKey() }); }

async function fetchRenderedHtml(url, readySelector = "script#__NEXT_DATA__", { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 1 } = {}) {
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
      lastError = new Error("empty HTML");
    } catch (e) {
      lastError = e;
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
  }
  throw new Error(`giving up after ${retries + 1} attempts: ${lastError?.message}`);
}

export function extractApolloState(html) {
  const $ = cheerio.load(html);
  const raw = $("script#__NEXT_DATA__").contents().text();
  if (!raw) return {};
  try {
    const data = JSON.parse(raw);
    return data?.props?.pageProps?.apolloState?.data ?? {};
  } catch (_) {
    return {};
  }
}

function isRef(v) {
  return v && typeof v === "object" && !Array.isArray(v)
    && Object.keys(v).length === 1 && "__ref" in v;
}
function resolve(value, graph) {
  if (isRef(value)) return resolve(graph[value.__ref] ?? {}, graph);
  if (Array.isArray(value)) return value.map((v) => resolve(v, graph));
  if (value && typeof value === "object") {
    const out = {};
    for (const [k, v] of Object.entries(value)) out[k] = resolve(v, graph);
    return out;
  }
  return value;
}

export function parseCompany(html) {
  const graph = extractApolloState(html);
  const out = [];
  // Wellfound's Apollo cache uses `Startup:` keys on company pages and
  // `StartupResult:` keys on search-result (role/location) pages.
  for (const [key, node] of Object.entries(graph)) {
    if (typeof node !== "object" || node === null) continue;
    if (!key.startsWith("Startup:") && !key.startsWith("StartupResult:")) continue;
    out.push(resolve(node, graph));
  }
  return out;
}

function searchUrl(role = "", location = "") {
  role = role.trim();
  location = location.trim();
  if (role && location) return `https://wellfound.com/role/l/${role}/${location}`;
  if (role) return `https://wellfound.com/role/${role}`;
  if (location) return `https://wellfound.com/location/${location}`;
  throw new Error("scrapeSearch requires at least role or location");
}

export async function scrapeSearch(role = "", location = "", maxPages = null) {
  const base = searchUrl(role, location);
  const pages = maxPages ?? 1;
  const out = [];
  for (let p = 1; p <= pages; p++) {
    const url = p === 1 ? base : `${base}?page=${p}`;
    try {
      const html = await fetchRenderedHtml(url);
      out.push(...parseCompany(html));
    } catch (_) { break; }
  }
  return out;
}

export async function scrapeCompanies(urls) {
  const out = [];
  for (const url of urls) {
    const html = await fetchRenderedHtml(url);
    out.push(...parseCompany(html));
  }
  return out;
}
