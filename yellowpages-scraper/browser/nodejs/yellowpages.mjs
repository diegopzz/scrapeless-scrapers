// YellowPages scraper using @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// function names and emitted field names match verbatim.

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

function _looksCloudflare(html) {
  if (!html || html.length < 8000) return true;
  if (/Just a moment|cf-browser-verification|cf-challenge/i.test(html.slice(0, 4000))) return true;
  return false;
}

async function fetchRenderedHtml(url, readySelector, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 2, warmup = true } = {}) {
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
      // Warmup: visit yellowpages homepage so Cloudflare cookies attach to
      // the session before the deeper navigation.
      if (warmup) {
        try {
          await page.goto("https://www.yellowpages.com/", { waitUntil: "domcontentloaded", timeout: 30000 });
          await new Promise((r) => setTimeout(r, 2500));
        } catch (_) {}
      }
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
      let html = "";
      for (let i = 0; i < 6; i++) {
        if (readySelector) {
          try { await page.waitForSelector(readySelector, { timeout: 5000 }); break; } catch (_) {}
        }
        await new Promise((r) => setTimeout(r, 2500));
        html = await page.content();
        if (html && !_looksCloudflare(html)) break;
      }
      if (!html) html = await page.content();
      if (html && !_looksCloudflare(html)) return html;
      lastError = new Error(_looksCloudflare(html) ? "cloudflare block" : "empty HTML");
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
  const data = [];
  // YellowPages currently emits the listings as a bare JSON-LD array of
  // LocalBusiness objects (second <script type=application/ld+json> block).
  // Older variants used an ItemList with `itemListElement[].item`; support both.
  $('script[type="application/ld+json"]').each((_, el) => {
    let payload;
    try { payload = JSON.parse($(el).contents().text()); } catch (_) { return; }
    const candidates = Array.isArray(payload) ? payload : [payload];
    for (const node of candidates) {
      if (!node || typeof node !== "object") continue;
      if (node["@type"] === "LocalBusiness") {
        data.push(node);
        continue;
      }
      if (Array.isArray(node.itemListElement)) {
        for (const entry of node.itemListElement) {
          if (entry && typeof entry === "object" && entry.item && typeof entry.item === "object") {
            data.push(entry.item);
          }
        }
      }
    }
  });
  let total_pages = null;
  const pageText = $(".pagination > span").first().text();
  // YellowPages currently prints "Showing X-Y of Z" — Z is the total result count,
  // not the page count. Compute total pages from the page size (30) when needed.
  const m = pageText.match(/of\s+([\d,]+)/);
  if (m) {
    const total = parseInt(m[1].replace(/,/g, ""), 10);
    if (Number.isFinite(total)) {
      total_pages = Math.max(1, Math.ceil(total / 30));
    }
  }
  return { data, total_pages };
}

function _readLocalBusinessLd($) {
  let node = null;
  $('script[type="application/ld+json"]').each((_, el) => {
    let parsed;
    try { parsed = JSON.parse($(el).contents().text()); } catch (_) { return; }
    const candidates = Array.isArray(parsed) ? parsed : [parsed];
    for (const c of candidates) {
      if (!c || typeof c !== "object") continue;
      const t = c["@type"];
      if (typeof t === "string" && /(LocalBusiness|Plumber|Restaurant|Store|Organization|Service)/.test(t)) {
        node = c;
        return false;
      }
    }
  });
  return node;
}

export function parsePage(html) {
  const $ = cheerio.load(html);
  const ratingClass = $(".ratings div").first().attr("class") ?? "";
  let rating = "";
  const rm = ratingClass.match(/result\s+([a-z\s]+?)(?=$|\s\w+$)/);
  if (rm) rating = rm[1].trim();

  const workingHours = {};
  $(".open-details tr").each((_, row) => {
    const day = $(row).find("th").text().trim();
    const hours = $(row).find("time").attr("datetime");
    if (day && hours) workingHours[day] = hours.trim();
  });

  const phoneHref = $(".phone").first().attr("href") ?? "";
  const phone = phoneHref.replace(/^tel:/, "");

  const out = {
    name: $("h1.business-name").first().text().trim(),
    categories: $(".categories > a").map((_, el) => $(el).text().trim()).get().filter(Boolean),
    rating,
    ratingCount: $(".ratings .count").first().text().trim(),
    phone,
    website: $(".website-link").first().attr("href") ?? "",
    address: $(".address").first().text().trim(),
    workingHours,
  };

  // JSON-LD fallback for the (rare) layout variants that drop these selectors.
  const ld = _readLocalBusinessLd($);
  if (ld) {
    if (!out.name && typeof ld.name === "string") out.name = ld.name;
    if (!out.phone && typeof ld.telephone === "string") out.phone = ld.telephone;
    if (!out.address && ld.address && typeof ld.address === "object") {
      const a = ld.address;
      out.address = [a.streetAddress, a.addressLocality, a.addressRegion, a.postalCode]
        .filter((x) => typeof x === "string" && x.trim()).join(", ");
    }
    if (!Object.keys(out.workingHours).length && Array.isArray(ld.openingHours)) {
      for (const spec of ld.openingHours) {
        if (typeof spec !== "string") continue;
        const m = spec.match(/^([A-Za-z-]+)\s+(\d{2}:\d{2}-\d{2}:\d{2})$/);
        if (m) out.workingHours[m[1]] = m[2];
        else out.workingHours[spec] = spec;
      }
    }
  }
  return out;
}

// ---------------- scrape functions ----------------

function urlFor(query, location, page) {
  const loc = location ? encodeURIComponent(location) : "";
  return `https://www.yellowpages.com/search?search_terms=${encodeURIComponent(query)}&geo_location_terms=${loc}&page=${page}`;
}

export async function scrapeSearch(query, location = null, maxPages = null) {
  const firstHtml = await fetchRenderedHtml(urlFor(query, location, 1), ".search-results");
  const first = parseSearch(firstHtml);
  const pages = [first];
  let total = first.total_pages ?? 1;
  if (maxPages !== null && maxPages !== undefined) total = Math.min(total, maxPages);
  for (let p = 2; p <= total; p++) {
    try {
      const html = await fetchRenderedHtml(urlFor(query, location, p), ".search-results");
      pages.push(parseSearch(html));
    } catch (_) { break; }
  }
  return pages;
}

export async function scrapePages(urls) {
  const out = [];
  for (const url of urls) {
    const html = await fetchRenderedHtml(url, "h1.business-name");
    out.push(parsePage(html));
  }
  return out;
}
