// Domain.com.au scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
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

async function fetchRenderedHtml(url, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 1 } = {}) {
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
        await page.waitForSelector("script#__NEXT_DATA__", { timeout: 15000 });
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

// ---------------- parsers (verbatim shape from the upstream reference) ----------------

function loadNextData(html) {
  const $ = cheerio.load(html);
  const text = $("script#__NEXT_DATA__").html();
  if (!text) throw new Error("__NEXT_DATA__ script tag not found");
  return JSON.parse(text);
}

export function parseHiddenData(html) {
  return loadNextData(html).props.pageProps.componentProps;
}

export function parseComponentProps(data) {
  if (!data) return null;
  return {
    listingId: data.listingId ?? null,
    listingUrl: data.listingUrl ?? null,
    unitNumber: data.unitNumber ?? null,
    streetNumber: data.streetNumber ?? null,
    street: data.street ?? null,
    suburb: data.suburb ?? null,
    postcode: data.postcode ?? null,
    createdOn: data.createdOn ?? null,
    propertyType: data.propertyType ?? null,
    beds: data.beds ?? null,
    phone: data.phone ?? null,
    agencyName: data.agencyName ?? null,
    propertyDeveloperName: data.propertyDeveloperName ?? null,
    agencyProfileUrl: data.agencyProfileUrl ?? null,
    propertyDeveloperUrl: data.propertyDeveloperUrl ?? null,
    description: data.description ?? null,
    loanfinder: data.loanfinder ?? null,
    schools: data.schoolCatchment?.schools ?? null,
    suburbInsights: data.suburbInsights ?? null,
    gallery: data.gallery ?? null,
    listingSummary: data.listingSummary ?? null,
    agents: data.agents ?? null,
    features: data.features ?? null,
    structuredFeatures: data.structuredFeatures ?? null,
    faqs: data.faqs ?? null,
  };
}

export function parsePageProps(data) {
  if (!data) return null;
  const apollo = data.__APOLLO_STATE__;
  const key = Object.keys(apollo).find((k) => k.startsWith("Property:"));
  const prop = apollo[key];
  const result = {
    propertyId: prop.propertyId ?? null,
    unitNumber: prop.address?.unitNumber ?? null,
    streetNumber: prop.address?.streetNumber ?? null,
    suburb: prop.address?.suburb ?? null,
    postcode: prop.address?.postcode ?? null,
    gallery: [],
  };
  const imageKey = Object.keys(prop).find((k) => k.startsWith("media("));
  if (imageKey) {
    for (const image of prop[imageKey]) result.gallery.push(image.url);
  }
  return result;
}

export function parseRepoertyData(html) {
  const json = loadNextData(html);
  try {
    const data = json.props.pageProps.componentProps;
    return parseComponentProps(data);
  } catch (_) {
    return parsePageProps(json.props.pageProps);
  }
}

export function parseSearchPage(data) {
  if (!data) return null;
  const listings = data.listingsMap;
  const out = [];
  for (const key of Object.keys(listings)) {
    const item = listings[key];
    const parsed = {
      id: item.id ?? null,
      listingType: item.listingType ?? null,
      listingModel: item.listingModel ?? null,
    };
    if (parsed.listingModel && "skeletonImages" in parsed.listingModel) {
      delete parsed.listingModel.skeletonImages;
    }
    out.push(parsed);
  }
  return out;
}

// ---------------- scrape functions ----------------

export async function scrapeProperties(urls) {
  const properties = [];
  for (const url of urls) {
    try {
      const html = await fetchRenderedHtml(url);
      const data = parseRepoertyData(html);
      if (data) {
        data.url = url;
        properties.push(data);
      }
    } catch (e) {
      console.error("An error occurred while scraping property pages:", e.message);
    }
  }
  return properties;
}

export async function scrapeSearch(url, maxScrapePages = null) {
  const firstHtml = await fetchRenderedHtml(url);
  const data = parseHiddenData(firstHtml);
  const searchData = parseSearchPage(data) ?? [];
  const maxSearchPages = data.totalPages;

  const pages =
    maxScrapePages && maxScrapePages < maxSearchPages ? maxScrapePages : maxSearchPages;

  for (let page = 2; page <= pages; page++) {
    const pageUrl = `${url}?page=${page}`;
    try {
      const html = await fetchRenderedHtml(pageUrl);
      const d = parseHiddenData(html);
      searchData.push(...(parseSearchPage(d) ?? []));
    } catch (e) {
      console.error("An error occurred while scraping search pages:", e.message);
    }
  }
  return searchData;
}
