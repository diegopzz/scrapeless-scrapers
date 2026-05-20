// SeLoger scraper using @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Mirrors  —
// function names and emitted field names match verbatim.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const PROXY_COUNTRY = "FR";
const DEFAULT_SESSION_TTL = 180;

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

function absoluteUrl(base, rel) {
  try { return new URL(rel, base).toString(); } catch (_) { return rel; }
}

// ---------------- parsers ----------------

export function parseSearch(html, baseUrl) {
  const $ = cheerio.load(html);
  const out = [];
  $("div[data-testid='serp-core-classified-card-testid']").each((_, el) => {
    const card = $(el);
    const link = card.find("a[data-testid='card-mfe-covering-link-testid']").attr("href") || "";
    const title = card.find("a[data-testid='card-mfe-covering-link-testid']").attr("title") || "";
    const priceEl = card.find("div[data-testid*='cardmfe-price']").first();
    const price = (priceEl.attr("aria-label") || priceEl.text() || "").trim();
    const pricePerM2El = card.find("div[data-testid*='price-per-m2']").first();
    const pricePerM2 = pricePerM2El.length ? pricePerM2El.text().trim() : null;
    const property_facts = [];
    card.find("div[data-testid*='description']").contents().each((__, n) => {
      if (n.type === "text" && n.data && n.data.trim()) property_facts.push(n.data.trim());
    });
    const address = card.find("div[data-testid*='address']").text().trim();
    const agencyEl = card.find("div[data-testid*='agency']").first();
    const agency = agencyEl.length ? agencyEl.text().trim() : null;
    const images = [];
    card.find("img").each((__, img) => {
      const src = $(img).attr("src");
      if (src) images.push(src);
    });
    out.push({
      title,
      url: absoluteUrl(baseUrl, link),
      images,
      price,
      price_per_m2: pricePerM2,
      property_facts,
      address,
      agency,
    });
  });
  return out;
}

export function parseProperty(html) {
  const $ = cheerio.load(html);
  let payload = {};
  $("body script").each((_, el) => {
    const txt = $(el).html() || "";
    if (!txt.includes("__UFRN_LIFECYCLE_SERVERREQUEST__")) return;
    const m = /JSON\.parse\("(.+)"\)/s.exec(txt);
    if (!m) return;
    try {
      const decoded = JSON.parse(`"${m[1]}"`);
      const data = JSON.parse(decoded);
      const classified = data?.app_cldp?.data?.classified;
      if (classified) {
        payload = { classified };
        return false;
      }
    } catch (_) {}
  });
  return payload;
}

// ---------------- scrape functions ----------------

export async function scrapeSearch(url, maxPages = 10) {
  const first = await fetchRenderedHtml(url, "div[data-testid='serp-core-classified-card-testid']");
  const out = parseSearch(first, url);
  for (let page = 2; page <= maxPages; page++) {
    const sep = url.includes("?") ? "&" : "?";
    const pageUrl = `${url}${sep}page=${page}`;
    const html = await fetchRenderedHtml(pageUrl, "div[data-testid='serp-core-classified-card-testid']");
    const items = parseSearch(html, url);
    if (!items.length) break;
    out.push(...items);
  }
  return out;
}

export async function scrapeProperty(urls) {
  const out = [];
  for (const u of urls) {
    const html = await fetchRenderedHtml(u, "body");
    out.push(parseProperty(html));
  }
  return out;
}
