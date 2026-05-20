// Realtor.com scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// function names + emitted field names match verbatim.
//
// Three surfaces:
// - `scrapeProperty(url)`                     — `__NEXT_DATA__` JSON, JMESPath-reduced.
// - `scrapeSearch(state, city, maxPages)`     — `__NEXT_DATA__` array of property cards.
// - `scrapeFeed(url)`                         — XML sitemap with `<loc>` + `<lastmod>` pairs.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";
import jmespath from "jmespath";

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

async function newBrowser(proxyCountry = DEFAULT_PROXY_COUNTRY) {
  const { browserWSEndpoint } = await client().browser.create({
    proxyCountry,
    sessionTTL: DEFAULT_SESSION_TTL,
  });
  return browserWSEndpoint;
}

async function fetchHtml(url, readySelector = null, { retries = 2, warmup = true } = {}) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    if (attempt > 0) await new Promise((r) => setTimeout(r, 6000 * attempt));
    const ws = await newBrowser();
    let browser;
    try {
      browser = await puppeteer.connect({ browserWSEndpoint: ws });
      const page = await browser.newPage();
      // Realtor.com is fronted by PerimeterX. A homepage warm-up lets the
      // session pick up the `_px*` cookies before navigating to the search
      // / property page, which avoids the static "Press & Hold" interstitial.
      if (warmup && !url.endsWith(".xml")) {
        try {
          await page.goto("https://www.realtor.com/", { waitUntil: "domcontentloaded", timeout: 30000 });
          await new Promise((r) => setTimeout(r, 3000));
        } catch (_) {}
      }
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
      if (readySelector) {
        try { await page.waitForSelector(readySelector, { timeout: 15000 }); } catch (_) {}
      }
      const html = await page.content();
      // PerimeterX interstitials are ~2KB; real pages are far larger.
      if (html && (url.endsWith(".xml") || html.length > 10000)) return html;
      lastError = new Error("PerimeterX interstitial / short HTML");
    } catch (e) {
      lastError = e;
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
  }
  throw new Error(`giving up after ${retries + 1} attempts: ${lastError?.message}`);
}

const PROPERTY_JMESPATH = `{
    id: propertyDetails.listing_id,
    slug: slug,
    url: propertyDetails.href,
    status: propertyDetails.status,
    tags: propertyDetails.tags,
    sold_date: propertyDetails.last_sold_date,
    sold_price: propertyDetails.last_sold_price,
    list_date: propertyDetails.list_date,
    list_price: propertyDetails.list_price,
    list_price_last_change: propertyDetails.last_price_change_amount,
    details: propertyDetails.description,
    flags: propertyDetails.flags,
    local: propertyDetails.local,
    location: propertyDetails.location,
    agent: propertyDetails.source.agents,
    advertisers: propertyDetails.advertisers,
    tax_history: propertyDetails.tax_history,
    history: propertyDetails.property_history[].{
        date: date,
        event: event_name,
        price: price,
        price_sqft: price_sqft
    },
    photos: propertyDetails.photos[].{
        url: href,
        tags: tags[].label
    },
    phones: propertyDetails.lead_attributes.opcity_lead_attributes.phones[].{
        type: category,
        number: number
    },
    features: propertyDetails.details[].{
        name: category,
        values: text
    }
}`;

// ---------------- parsers (mirror the upstream reference verbatim) ----------------

export function parseProperty(html, url) {
  const $ = cheerio.load(html);
  const data = $("script#__NEXT_DATA__").first().text();
  if (!data) {
    console.warn(`page ${url} is not a property listing page`);
    return null;
  }
  const parsed = JSON.parse(data);
  const raw = parsed.props.pageProps.initialReduxState;
  const reduced = jmespath.search(raw, PROPERTY_JMESPATH);
  if (reduced && Array.isArray(reduced.features)) {
    const flat = {};
    for (const f of reduced.features) {
      if (f && f.name) flat[f.name] = f.values;
    }
    reduced.features = flat;
  }
  return reduced;
}

export function parseSearch(html, url) {
  const $ = cheerio.load(html);
  const data = $("script#__NEXT_DATA__").first().text();
  if (!data) {
    console.warn(`page ${url} is not a property listing page`);
    return null;
  }
  const parsed = JSON.parse(data).props.pageProps;
  if (!parsed.properties) {
    parsed.properties = parsed.searchResults.home_search.results;
  }
  if (!parsed.totalProperties) {
    parsed.totalProperties = parsed.searchResults.home_search.total;
  }
  return parsed;
}

// ---------------- scrape functions (mirror the upstream reference verbatim) ----------------

export async function scrapeProperty(url) {
  const html = await fetchHtml(url, "script#__NEXT_DATA__");
  return parseProperty(html, url);
}

export async function scrapeSearch(state, city, maxPages = null) {
  const firstUrl = `https://www.realtor.com/realestateandhomes-search/${city}_${state}/pg-1`;
  const firstHtml = await fetchHtml(firstUrl, "script#__NEXT_DATA__");
  const first = parseSearch(firstHtml, firstUrl);
  if (!first) return [];
  const results = [...first.properties];
  let totalPages = results.length > 0 ? Math.ceil(first.totalProperties / results.length) : 1;
  if (maxPages && totalPages > maxPages) totalPages = maxPages;
  for (let p = 2; p <= totalPages; p++) {
    const pageUrl = firstUrl.replace("pg-1", `pg-${p}`);
    try {
      const html = await fetchHtml(pageUrl, "script#__NEXT_DATA__");
      const parsed = parseSearch(html, pageUrl);
      if (parsed) results.push(...parsed.properties);
    } catch (e) {
      console.warn(`failed page ${p}: ${e.message}`);
    }
  }
  return results;
}

export async function scrapeFeed(url) {
  const body = await fetchHtml(url);
  const $ = cheerio.load(body, { xmlMode: true });
  const out = {};
  $("sitemap").each((_, el) => {
    const loc = $(el).find("loc").text();
    const pub = $(el).find("lastmod").text();
    if (loc && pub) {
      const d = new Date(pub);
      if (!isNaN(d.getTime())) out[loc] = d.toISOString();
    }
  });
  return out;
}
