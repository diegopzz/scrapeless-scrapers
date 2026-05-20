// Priceline scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Priceline is a Next.js + Apollo Client app. Both the listing and detail surfaces
// hydrate React via the Apollo SSR Data Transport: a series of inline `<script>`
// tags that call
//   (window[Symbol.for("ApolloSSRDataTransport")] ??= []).push({ rehydrate: { … } })
// Each `rehydrate` payload contains the GraphQL data the server fetched (e.g.
// `standaloneHotelListings.listings[].hotelInfo` for search; `rtlHotelDetails`
// for the PDP). We read those payloads directly from the raw HTML so we don't
// race against the client running its own GraphQL queries after hydration.
//
// Surfaces:
//   - `scrapeSearch(cityId, checkin, checkout)`  → Apollo SSR listings
//   - `scrapeHotel(hotelId, checkin, checkout)`  → detail (Apollo SSR + pcln-graph fallback)
//
// If the Apollo blob is absent we additionally listen for `/pws/v0/pcln-graph`
// XHRs (the rehydration calls the client makes during render) and harvest the
// `rtlHotelDetails` / `standaloneHotelListings` payloads from there.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 300;
const HOMEPAGE_URL = "https://www.priceline.com/";

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function withBrowser(fn, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 1, label = "navigation" } = {}) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const { browserWSEndpoint } = await client().browser.create({
      proxyCountry,
      sessionTTL: DEFAULT_SESSION_TTL,
    });
    let browser;
    try {
      browser = await puppeteer.connect({ browserWSEndpoint });
      return await fn(browser);
    } catch (e) {
      lastError = e;
      if (attempt === retries) break;
      await new Promise((r) => setTimeout(r, 4000 * Math.pow(1.5, attempt)));
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
  }
  throw new Error(`${label}: giving up after ${retries + 1} attempts: ${lastError?.message ?? lastError}`);
}

// ---------------- Apollo SSR transport extraction ----------------

// Walk the HTML and pull every `{ rehydrate: { … } }` payload pushed onto
// the ApolloSSRDataTransport array. Returns the merged `rehydrate` map.
export function extractApolloRehydrate(html) {
  const merged = {};
  let pos = 0;
  while (true) {
    const at = html.indexOf(".push(", pos);
    if (at === -1) break;
    const before = html.slice(Math.max(0, at - 80), at);
    if (!before.includes("ApolloSSRDataTransport")) { pos = at + 6; continue; }
    const start = at + 6;
    // Balanced-brace scan over a JSON object that may contain quoted strings.
    let depth = 0;
    let end = -1;
    let i = start;
    while (i < html.length) {
      const c = html[i];
      if (c === '"') {
        i++;
        while (i < html.length && html[i] !== '"') {
          if (html[i] === "\\") i++;
          i++;
        }
      } else if (c === "{") depth++;
      else if (c === "}") {
        depth--;
        if (depth === 0) { end = i + 1; break; }
      }
      i++;
    }
    if (end < 0) break;
    const objStr = html.slice(start, end).replace(/:\s*undefined\b/g, ": null");
    try {
      const obj = JSON.parse(objStr);
      if (obj && obj.rehydrate) Object.assign(merged, obj.rehydrate);
    } catch (_) {}
    pos = end;
  }
  return merged;
}

function findInTree(node, predicate, out = []) {
  if (!node || typeof node !== "object") return out;
  if (Array.isArray(node)) {
    for (const v of node) findInTree(v, predicate, out);
    return out;
  }
  if (predicate(node)) out.push(node);
  for (const v of Object.values(node)) findInTree(v, predicate, out);
  return out;
}

// ---------------- hotel ----------------

function flattenAmenities(amenityCategories, amenities) {
  const out = [];
  for (const cat of amenityCategories || []) {
    for (const a of cat?.amenities || []) {
      const t = a?.name || a?.label || (typeof a === "string" ? a : null);
      if (t && !out.includes(t)) out.push(t);
    }
  }
  for (const a of amenities || []) {
    const t = a?.name || a?.label || (typeof a === "string" ? a : null);
    if (t && !out.includes(t)) out.push(t);
  }
  return out;
}

function flattenImages(info) {
  const out = [];
  for (const ig of info?.imageGroups || []) {
    for (const img of ig?.images || []) {
      const u = img?.fastlyUrl || img?.url || img?.source;
      if (u && !out.includes(u)) out.push(u);
    }
  }
  for (const img of info?.images || []) {
    const u = img?.fastlyUrl || img?.url || img?.source;
    if (u && !out.includes(u)) out.push(u);
  }
  return out;
}

function hotelDetailUrl(hotelId, checkin = "", checkout = "") {
  const ci = checkin.replace(/-/g, "");
  const co = checkout.replace(/-/g, "");
  const segments = ["https://www.priceline.com/relax/at", hotelId];
  if (ci) segments.push("from", ci);
  if (co) segments.push("to", co);
  segments.push("rooms", "1");
  return segments.join("/");
}

// Lift a hotel object (from search listings) to the SearchResult shape.
function mapListingItem(info) {
  if (!info) return null;
  const id = String(info.id || info.hotelId || "");
  if (!id) return null;
  const name = info.name || info.hotelName || info?.brand?.name || "";
  if (!name) return null;
  const reviewInfo = info.reviewInfo || info.review || {};
  const propertyInfo = info.propertyInfo || {};
  const neighborhood = info?.neighborhood?.name || info?.location?.neighborhoodName || null;
  const starRatingRaw = propertyInfo.starRating || info.starRating || info.starLevelText;
  const starRating = typeof starRatingRaw === "number" ? starRatingRaw
    : typeof starRatingRaw === "string" ? parseFloat(starRatingRaw) || null
    : null;
  const review = typeof reviewInfo.guestRating === "number" ? reviewInfo.guestRating
    : typeof reviewInfo.overallGuestRating === "number" ? reviewInfo.overallGuestRating
    : null;
  const reviewCountRaw = reviewInfo.totalReviewCount ?? reviewInfo.reviewCount;
  const reviewCount = typeof reviewCountRaw === "number" ? reviewCountRaw
    : typeof reviewCountRaw === "string" ? parseInt(reviewCountRaw.replace(/,/g, ""), 10) || null
    : null;
  const firstImage = (info.images || [])[0];
  const image = firstImage?.fastlyUrl || firstImage?.url || firstImage?.source || null;
  return {
    id,
    name,
    url: hotelDetailUrl(id),
    price: null, // listing price lives in a sibling rate/price object, populated separately when present
    starRating,
    review,
    reviewCount,
    image,
    neighborhood,
  };
}

export function parseHotelFromGraphql(graphqlData) {
  const details = graphqlData?.data?.rtlHotelDetails || graphqlData?.rtlHotelDetails || {};
  const info = details.hotelInfo || {};
  const geo = info.geoCoordinate || {};
  const policies = (info.propertyPolicies || []).map((p) => ({
    type: p?.type || null,
    label: p?.label || null,
    description: p?.description?.policyList || [],
  }));
  return {
    name: info.name || "",
    address: info.address || null,
    description: info.description || "",
    amenities: flattenAmenities(info.amenityCategories, info.amenities),
    images: flattenImages(info),
    latitude: typeof geo.latitude === "number" ? geo.latitude : null,
    longitude: typeof geo.longitude === "number" ? geo.longitude : null,
    starRating: info.starRating || info.starLevelText || null,
    policies,
  };
}

export async function scrapeHotel(hotelId, checkin = "", checkout = "", { proxyCountry = DEFAULT_PROXY_COUNTRY } = {}) {
  const url = hotelDetailUrl(hotelId, checkin, checkout);
  return withBrowser(async (browser) => {
    const page = await browser.newPage();
    // Capture pcln-graph rtlHotelDetails responses as a fallback to the SSR blob.
    const detailResponses = [];
    page.on("response", async (resp) => {
      try {
        const u = resp.url();
        if (!u.includes("/pws/v0/pcln-graph")) return;
        if (!/rtlHotelDetails|RtlHotelStandaloneDetails|InventoryQlContent/i.test(u)) return;
        const txt = await resp.text();
        try { detailResponses.push(JSON.parse(txt)); } catch (_) {}
      } catch (_) {}
    });
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
    // Give pcln-graph XHRs a moment to flush and Apollo SSR markers to be present.
    await new Promise((r) => setTimeout(r, 7000));
    const html = await page.content();

    // 1) Apollo SSR transport (preferred — server already populated it).
    const rehydrate = extractApolloRehydrate(html);
    let info = null;
    const candidates = findInTree(rehydrate, (n) => n && typeof n === "object" && n.rtlHotelDetails);
    for (const cand of candidates) {
      const d = cand.rtlHotelDetails;
      if (d && d.hotelInfo && (d.hotelInfo.address || (d.hotelInfo.imageGroups || []).length)) {
        info = d.hotelInfo;
        break;
      }
    }
    // 2) Fall back to captured pcln-graph payloads. Prefer one that has imageGroups/address.
    if (!info) {
      let best = null;
      for (const r of detailResponses) {
        const i = r?.data?.rtlHotelDetails?.hotelInfo;
        if (!i) continue;
        const score = (i.address ? 2 : 0) + ((i.imageGroups || []).length ? 2 : 0) + ((i.amenityCategories || []).length ? 1 : 0);
        if (!best || score > best.score) best = { info: i, score };
      }
      if (best) info = best.info;
    }
    if (!info) {
      throw new Error(`priceline: no hotelInfo for ${hotelId} (Apollo SSR + GraphQL both empty — hotel ID may be invalid or page is anti-bot blocked)`);
    }

    const parsed = parseHotelFromGraphql({ data: { rtlHotelDetails: { hotelInfo: info } } });
    let pageTitle = null;
    try { pageTitle = cheerio.load(html)("title").first().text().trim() || null; } catch (_) {}
    return {
      id: String(hotelId),
      url,
      name: parsed.name,
      address: parsed.address,
      description: parsed.description,
      amenities: parsed.amenities,
      images: parsed.images,
      latitude: parsed.latitude,
      longitude: parsed.longitude,
      starRating: parsed.starRating,
      policies: parsed.policies,
      pageTitle,
    };
  }, { proxyCountry, label: "scrape_hotel" });
}

// ---------------- search ----------------

function listUrl(cityId, checkin = "", checkout = "") {
  const ci = checkin.replace(/-/g, "");
  const co = checkout.replace(/-/g, "");
  const segments = ["https://www.priceline.com/relax/in", cityId];
  if (ci) segments.push("from", ci);
  if (co) segments.push("to", co);
  segments.push("rooms", "1");
  return segments.join("/");
}

export async function scrapeSearch(cityId, checkin = "", checkout = "", { proxyCountry = DEFAULT_PROXY_COUNTRY } = {}) {
  const url = listUrl(cityId, checkin, checkout);
  return withBrowser(async (browser) => {
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
    await new Promise((r) => setTimeout(r, 6000));
    const html = await page.content();
    const rehydrate = extractApolloRehydrate(html);
    const containers = findInTree(rehydrate, (n) => n && typeof n === "object" && Array.isArray(n.listings));
    const listings = [];
    const seen = new Set();
    for (const c of containers) {
      for (const l of c.listings) {
        const info = l?.hotelInfo || l;
        const mapped = mapListingItem(info);
        if (mapped && !seen.has(mapped.id)) {
          // Pull listing-level price from the sibling rate object when present.
          const rate = l?.rateAvailability || l?.rate || null;
          const minRate = l?.minRateSummary || null;
          const priceCandidates = [
            minRate?.formattedAverageNightlyPrice,
            minRate?.averageNightlyPrice && `$${Math.round(minRate.averageNightlyPrice)}`,
            rate?.bestRoomRate?.priceDetails?.displayPrice,
            rate?.bestRoomRate?.priceDetails?.formattedPrice,
          ];
          mapped.price = priceCandidates.find((v) => typeof v === "string" && v) || mapped.price;
          listings.push(mapped);
          seen.add(mapped.id);
        }
      }
    }
    if (!listings.length) {
      throw new Error(`priceline: no listings found in Apollo SSR transport for city ${cityId} (likely anti-bot block or empty city)`);
    }
    return listings;
  }, { proxyCountry, label: "scrape_search" });
}
