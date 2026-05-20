// Similarweb scraper using @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Mirrors  —
// function names and emitted field names match verbatim.
//
// Similarweb is a React SPA. The richest payload lives in `window.__APP_DATA__`
// (a JSON blob embedded in a script tag) — more stable than the rendered DOM.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";
import { gunzipSync } from "node:zlib";

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

async function fetchRenderedHtml(url, readySelector, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 1, waitForGlobal = null, evalGlobal = null } = {}) {
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
      try {
        await page.waitForSelector(readySelector, { timeout: 20000 });
      } catch (_) {}
      if (waitForGlobal) {
        try {
          await page.waitForFunction(`!!window.${waitForGlobal}`, { timeout: 15000 });
        } catch (_) {}
      }
      let evaluated = null;
      if (evalGlobal) {
        try {
          evaluated = await page.evaluate(evalGlobal);
        } catch (_) {}
      }
      const html = await page.content();
      if (html) return evalGlobal ? { html, evaluated } : html;
      lastError = new Error("empty HTML");
    } catch (e) {
      lastError = e;
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
  }
  throw new Error(`giving up after ${retries + 1} attempts: ${lastError?.message}`);
}

async function fetchRawBytes(url, { proxyCountry = DEFAULT_PROXY_COUNTRY } = {}) {
  const { browserWSEndpoint } = await client().browser.create({
    proxyCountry,
    sessionTTL: DEFAULT_SESSION_TTL,
  });
  let browser;
  try {
    browser = await puppeteer.connect({ browserWSEndpoint });
    const page = await browser.newPage();
    const res = await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
    return await res.buffer();
  } finally {
    try { await browser?.close(); } catch (_) {}
  }
}

// ---------------- Embedded-JSON helpers ----------------

const APP_DATA_RE = /window\.__APP_DATA__\s*=\s*(\{.*?\})\s*;\s*window\.__APP_META__/s;

function extractBalancedJson(text, startIdx) {
  // Walk a JSON object from text[startIdx] (which must be '{') honoring
  // string/escape semantics. Returns the slice or null.
  if (text[startIdx] !== "{") return null;
  let depth = 0;
  let inString = false;
  let escape = false;
  for (let i = startIdx; i < text.length; i++) {
    const c = text[i];
    if (escape) { escape = false; continue; }
    if (c === "\\") { escape = true; continue; }
    if (c === '"') { inString = !inString; continue; }
    if (inString) continue;
    if (c === "{") depth++;
    else if (c === "}") {
      depth--;
      if (depth === 0) return text.slice(startIdx, i + 1);
    }
  }
  return null;
}

export function parseHiddenData(html) {
  const m = html.match(APP_DATA_RE);
  if (m) return JSON.parse(m[1]);
  const marker = "window.__APP_DATA__";
  const idx = html.indexOf(marker);
  if (idx === -1) {
    const idxBare = html.indexOf("__APP_DATA__");
    if (idxBare === -1) throw new Error("could not locate window.__APP_DATA__");
    const braceIdx = html.indexOf("{", idxBare);
    if (braceIdx === -1) throw new Error("could not locate window.__APP_DATA__");
    const slice = extractBalancedJson(html, braceIdx);
    if (!slice) throw new Error("could not locate window.__APP_DATA__");
    return JSON.parse(slice);
  }
  const braceIdx = html.indexOf("{", idx);
  if (braceIdx === -1) throw new Error("could not locate window.__APP_DATA__");
  const slice = extractBalancedJson(html, braceIdx);
  if (!slice) throw new Error("could not locate window.__APP_DATA__");
  return JSON.parse(slice);
}

// ---------------- scrape functions ----------------

function pickHiddenData(evaluated, html) {
  // Prefer the live JS global; fall back to the regex-from-HTML path when the
  // global is missing OR shallow (e.g. layout.data not yet populated).
  if (evaluated && evaluated.layout && Object.keys(evaluated.layout.data ?? {}).length > 0) {
    return evaluated;
  }
  return parseHiddenData(html);
}

export async function scrapeWebsite(domains) {
  const out = [];
  for (const domain of domains) {
    const url = `https://www.similarweb.com/website/${domain}/`;
    const { html, evaluated } = await fetchRenderedHtml(url, '[data-test-id="website-name"], h1', {
      waitForGlobal: "__APP_DATA__",
      evalGlobal: "window.__APP_DATA__ || null",
    });
    const data = pickHiddenData(evaluated, html);
    out.push(data?.layout?.data ?? {});
  }
  return out;
}

export async function scrapeWebsiteCompare(firstDomain, secondDomain) {
  const url = `https://www.similarweb.com/website/${firstDomain}/vs/${secondDomain}/`;
  const { html, evaluated } = await fetchRenderedHtml(url, '[data-test-id="website-name"], h1', {
    waitForGlobal: "__APP_DATA__",
    evalGlobal: "window.__APP_DATA__ || null",
  });
  const data = pickHiddenData(evaluated, html);
  const layout = data?.layout?.data ?? {};
  const compare = layout?.compareCompetitor ?? layout;
  function subset(obj) {
    if (!obj) return {};
    return {
      overview: obj.overview,
      traffic: obj.traffic,
      trafficSources: obj.trafficSources,
      ranking: obj.ranking,
      demographics: obj.demographics,
      geography: obj.geography,
    };
  }
  return {
    [firstDomain]: subset(compare[firstDomain] ?? compare),
    [secondDomain]: subset(compare[secondDomain] ?? {}),
  };
}

export async function scrapeSitemaps(url) {
  const body = await fetchRawBytes(url);
  let decompressed;
  try {
    decompressed = gunzipSync(body);
  } catch (_) {
    decompressed = gunzipSync(Buffer.from(body.toString("utf-8"), "base64"));
  }
  const xml = decompressed.toString("utf-8");
  const $ = cheerio.load(xml, { xmlMode: true });
  const out = [];
  $("url > loc").each((_, el) => out.push($(el).text()));
  return out;
}

export async function scrapeTrendings(urls) {
  const out = [];
  for (const url of urls) {
    const html = await fetchRenderedHtml(url, "script#dataset-json-ld");
    const $ = cheerio.load(html);
    const raw = $("script#dataset-json-ld").first().text() || "{}";
    let doc = {};
    try { doc = JSON.parse(raw); } catch (_) {}
    const main = doc.mainEntity ?? {};
    out.push({
      name: main.name ?? "",
      url,
      list: main.itemListElement ?? [],
    });
  }
  return out;
}
