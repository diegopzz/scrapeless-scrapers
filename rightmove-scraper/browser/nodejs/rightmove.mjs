// Rightmove scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// function names + emitted field names match verbatim.
//
// Three surfaces:
// - `scrapeProperties(urls)`                                — window.PAGE_MODEL.propertyData, JMESPath-reduced.
// - `findLocations(query)`                                  — typeahead API → "<type>^<id>" strings.
// - `scrapeSearch(name, id, scrapeAll, maxProperties)`      — /api/property-search/listing/search paginated.
//
// Uses a GB residential proxy (Rightmove is geo-locked).

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";
import jmespath from "jmespath";

const DEFAULT_PROXY_COUNTRY = "GB";
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

async function fetchPage(url, { asText = false, readySelector = null, waitForGlobal = null, evalGlobal = null } = {}) {
  const ws = await newBrowser();
  let browser;
  try {
    browser = await puppeteer.connect({ browserWSEndpoint: ws });
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
    if (readySelector) {
      try { await page.waitForSelector(readySelector, { timeout: 15000 }); } catch (_) {}
    }
    if (waitForGlobal) {
      try {
        await page.waitForFunction(`!!window.${waitForGlobal}`, { timeout: 15000 });
      } catch (_) {}
    }
    if (asText) {
      const body = await page.evaluate(() => document.body && document.body.innerText);
      if (body && body.trim()) return body;
    }
    let evaluated = null;
    if (evalGlobal) {
      try {
        evaluated = await page.evaluate(evalGlobal);
      } catch (_) {}
    }
    const html = await page.content();
    return evalGlobal ? { html, evaluated } : html;
  } finally {
    try { await browser?.close(); } catch (_) {}
  }
}

const PROPERTY_PARSE_MAP = {
  id: "id",
  available: "status.published",
  archived: "status.archived",
  phone: "contactInfo.telephoneNumbers.localNumber",
  bedrooms: "bedrooms",
  bathrooms: "bathrooms",
  type: "transactionType",
  property_type: "propertySubType",
  tags: "tags",
  description: "text.description",
  title: "text.pageTitle",
  subtitle: "text.propertyPhrase",
  price: "prices.primaryPrice",
  price_sqft: "prices.pricePerSqFt",
  address: "address",
  latitude: "location.latitude",
  longitude: "location.longitude",
  features: "keyFeatures",
  history: "listingHistory",
  photos: "images[*].{url: url, caption: caption}",
  floorplans: "floorplans[*].{url: url, caption: caption}",
  agency: `customer.{
    id: branchId,
    branch: branchName,
    company: companyName,
    address: displayAddress,
    commercial: commercial,
    buildToRent: buildToRent,
    isNew: isNewHomeDeveloper
  }`,
  industryAffiliations: "industryAffiliations[*].name",
  nearest_airports: "nearestAirports[*].{name: name, distance: distance}",
  nearest_stations: "nearestStations[*].{name: name, distance: distance}",
  sizings: "sizings[*].{unit: unit, min: minimumSize, max: maximumSize}",
  brochures: "brochures",
};

export function parseProperty(data) {
  const out = {};
  for (const [key, path] of Object.entries(PROPERTY_PARSE_MAP)) {
    out[key] = jmespath.search(data, path);
  }
  return out;
}

// Walk a JS payload yielding parsed JSON objects.
export function* findJsonObjects(text) {
  let pos = 0;
  while (true) {
    const match = text.indexOf("{", pos);
    if (match === -1) break;
    // Try expanding the slice until JSON.parse succeeds at a brace boundary.
    let depth = 0;
    let inString = false;
    let escape = false;
    let end = -1;
    for (let i = match; i < text.length; i++) {
      const c = text[i];
      if (escape) { escape = false; continue; }
      if (c === "\\") { escape = true; continue; }
      if (c === '"') { inString = !inString; continue; }
      if (inString) continue;
      if (c === "{") depth++;
      else if (c === "}") {
        depth--;
        if (depth === 0) { end = i + 1; break; }
      }
    }
    if (end === -1) break;
    try {
      yield JSON.parse(text.slice(match, end));
      pos = end;
    } catch (_) {
      pos = match + 1;
    }
  }
}

// Rightmove now ships PAGE_MODEL as a Devalue-style flat array: each slot is a
// node, and numeric values inside an object/array are slot indices that must be
// resolved against the array. Slot 0 is the root.
function reviveDevalue(arr) {
  const seen = new Map();
  const r = (i) => {
    if (typeof i !== "number") return i;
    if (seen.has(i)) return seen.get(i);
    const v = arr[i];
    if (v === undefined) return undefined;
    if (v === null || typeof v !== "object") {
      seen.set(i, v);
      return v;
    }
    if (Array.isArray(v)) {
      const out = [];
      seen.set(i, out);
      for (const e of v) out.push(typeof e === "number" ? r(e) : e);
      return out;
    }
    const out = {};
    seen.set(i, out);
    for (const [k, val] of Object.entries(v)) {
      out[k] = typeof val === "number" ? r(val) : val;
    }
    return out;
  };
  return r(0);
}

export function extractProperty(html) {
  const $ = cheerio.load(html);
  let script = null;
  $("script").each((_, el) => {
    const txt = $(el).html() ?? "";
    if (txt.includes("PAGE_MODEL = ")) {
      script = txt;
      return false;
    }
  });
  if (!script) throw new Error("PAGE_MODEL script not found");
  for (const obj of findJsonObjects(script)) {
    if (!obj) continue;
    // New Devalue-encoded form: { data: "<stringified array>", encoding: "..." }
    if (typeof obj.data === "string" && Object.prototype.hasOwnProperty.call(obj, "encoding")) {
      try {
        const arr = JSON.parse(obj.data);
        if (Array.isArray(arr) && arr.length > 0) {
          const root = reviveDevalue(arr);
          if (root && root.propertyData) return root.propertyData;
        }
      } catch (_) {}
    }
    // Legacy form: { propertyData: {...} }
    if (obj.propertyData && typeof obj.propertyData === "object") return obj.propertyData;
  }
  throw new Error("propertyData not found in PAGE_MODEL");
}

// ---------------- scrape functions (mirror the upstream reference verbatim) ----------------

export async function scrapeProperties(urls) {
  const out = [];
  for (const url of urls) {
    const html = await fetchPage(url, {
      readySelector: '#propertyHeader, [data-test="property-header"]',
    });
    const propertyData = extractProperty(html);
    if (!propertyData) throw new Error(`propertyData missing for ${url}`);
    out.push(parseProperty(propertyData));
  }
  return out;
}

export async function findLocations(query) {
  const url = `https://los.rightmove.co.uk/typeahead?query=${encodeURIComponent(query)}&limit=10&exclude=STREET`;
  const body = await fetchPage(url, { asText: true });
  const stripped = (body ?? "").trim();
  if (!stripped || !stripped.startsWith("{")) return [];
  let data;
  try { data = JSON.parse(stripped); } catch (_) { return []; }
  return (data.matches ?? []).map((p) => `${p.type}^${p.id}`);
}

export async function scrapeSearch(locationName, locationId, scrapeAllProperties, maxProperties = 1000) {
  const RESULTS_PER_PAGE = 24;
  const MAX_API = 1000;
  const makeUrl = (offset) => {
    const params = new URLSearchParams({
      searchLocation: locationName,
      useLocationIdentifier: "true",
      locationIdentifier: locationId,
      radius: "0.0",
      _includeSSTC: "true",
      index: String(offset),
      sortType: "2",
      channel: "BUY",
      transactionType: "BUY",
    });
    return `https://www.rightmove.co.uk/api/property-search/listing/search?${params.toString()}`;
  };

  const firstBody = await fetchPage(makeUrl(0), { asText: true });
  const firstData = JSON.parse(firstBody);
  const results = [...firstData.properties];
  const totalResults = parseInt(String(firstData.resultCount).replace(/,/g, ""), 10);

  const MAX = !scrapeAllProperties && maxProperties < totalResults ? maxProperties : totalResults;
  const offsets = [];
  for (let offset = RESULTS_PER_PAGE; offset < MAX; offset += RESULTS_PER_PAGE) {
    if (offset >= MAX_API) break;
    offsets.push(offset);
  }
  for (const offset of offsets) {
    try {
      const body = await fetchPage(makeUrl(offset), { asText: true });
      const data = JSON.parse(body);
      results.push(...data.properties);
    } catch (e) {
      console.warn(`failed offset ${offset}: ${e.message}`);
    }
  }
  return results;
}
