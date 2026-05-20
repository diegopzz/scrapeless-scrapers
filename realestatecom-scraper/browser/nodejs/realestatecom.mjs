// Realestate.com.au scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "AU";
const DEFAULT_SESSION_TTL = 180;

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function fetchRenderedHtml(url, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 2, warmup = true } = {}) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    if (attempt > 0) await new Promise((r) => setTimeout(r, 6000 * attempt));
    const { browserWSEndpoint } = await client().browser.create({
      proxyCountry,
      sessionTTL: DEFAULT_SESSION_TTL,
    });
    let browser;
    try {
      browser = await puppeteer.connect({ browserWSEndpoint });
      const page = await browser.newPage();
      // Realestate.com.au is fronted by an Akamai Bot Manager interstitial.
      // A homepage warm-up gets the session cookie before navigating to the
      // listing / search page.
      if (warmup) {
        try {
          await page.goto("https://www.realestate.com.au/", { waitUntil: "domcontentloaded", timeout: 30000 });
          await new Promise((r) => setTimeout(r, 4000));
        } catch (_) {}
      }
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
      try {
        await page.waitForFunction(
          "!!document.documentElement.outerHTML.match(/ArgonautExchange/)",
          { timeout: 15000 },
        );
      } catch (_) {}
      const html = await page.content();
      if (html && html.length > 10000) return html;
      lastError = new Error("Akamai interstitial / short HTML");
    } catch (e) {
      lastError = e;
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
  }
  throw new Error(`giving up after ${retries + 1} attempts: ${lastError?.message}`);
}

// ---------------- parsers (verbatim from the upstream reference) ----------------

export function parseHiddenData(html) {
  const $ = cheerio.load(html);
  let script = "";
  $("script").each((_, el) => {
    const t = $(el).html() ?? "";
    if (t.includes("window.ArgonautExchange")) script = t;
  });
  if (!script) throw new Error("ArgonautExchange cache not found");
  const m = script.match(/window\.ArgonautExchange=(\{.+\});/);
  if (!m) throw new Error("ArgonautExchange payload not extracted");
  let data = JSON.parse(m[1]);
  data = JSON.parse(data["resi-property_listing-experience-web"].urqlClientCache);
  data = JSON.parse(Object.values(data)[0].data);
  return data;
}

export function parsePropertyData(data) {
  if (!data) return null;
  const links = data._links ?? {};
  const media = data.media ?? {};
  const lc = data.listingCompany ?? null;
  return {
    id: data.id ?? null,
    propertyType: data.propertyType?.display ?? null,
    description: data.description ?? null,
    propertyLink: links.canonical?.href ?? null,
    address: data.address ?? null,
    propertySizes: data.propertySizes ?? null,
    generalFeatures: data.generalFeatures ?? null,
    propertyFeatures: (data.propertyFeatures ?? []).map((f) => ({
      featureName: f.displayLabel,
      value: f.value,
    })),
    images: (media.images ?? []).map((i) => i.templatedUrl),
    videos: data.videos ?? null,
    floorplans: data.floorplans ?? null,
    listingCompany: lc
      ? {
          name: lc.name ?? null,
          id: lc.id ?? null,
          companyLink: lc._links?.canonical?.href ?? null,
          phoneNumber: lc.businessPhone ?? null,
          address: lc.address?.display?.fullAddress ?? null,
          ratingsReviews: lc.ratingsReviews ?? null,
          description: lc.description ?? null,
        }
      : null,
    listers: data.listers ?? null,
    auction: data.auction ?? null,
  };
}

export function parseSearchData(data) {
  const root = Object.values(data)[0];
  const searchData = root.results.exact.items.map((listing) =>
    parsePropertyData(listing.listing),
  );
  const maxSearchPages = root.results.pagination.maxPageNumberAvailable;
  return { search_data: searchData, max_search_pages: maxSearchPages };
}

// ---------------- scrape functions (mirror the upstream reference's exports) ----------------

export async function scrapeProperties(urls) {
  const properties = [];
  for (const url of urls) {
    try {
      const html = await fetchRenderedHtml(url);
      const data = parseHiddenData(html).details.listing;
      const parsed = parsePropertyData(data);
      if (parsed) properties.push(parsed);
    } catch (e) {
      console.error("An error occurred while scraping property pages:", e.message);
    }
  }
  return properties;
}

export async function scrapeSearch(url, maxScrapePages = null) {
  const firstHtml = await fetchRenderedHtml(url);
  const first = parseHiddenData(firstHtml);
  const parsed = parseSearchData(first);
  const searchData = parsed.search_data;
  const maxSearchPages = parsed.max_search_pages;

  const pages =
    maxScrapePages && maxScrapePages < maxSearchPages ? maxScrapePages : maxSearchPages;

  const base = url.split("/list")[0];
  for (let page = 2; page <= pages; page++) {
    const pageUrl = `${base}/list-${page}`;
    try {
      const html = await fetchRenderedHtml(pageUrl);
      const data = parseHiddenData(html);
      searchData.push(...parseSearchData(data).search_data);
    } catch (e) {
      console.error("An error occurred while scraping search pages:", e.message);
    }
  }
  return searchData;
}
