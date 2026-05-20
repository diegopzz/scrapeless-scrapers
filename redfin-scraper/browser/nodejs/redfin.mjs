// Redfin scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// function names + emitted field names match verbatim.
//
// Three surfaces:
// - `scrapeSearch(url)`            — JSONP from the stingray `gis` endpoint.
// - `scrapePropertyForSale(urls)`  — DOM-parse the listing page.
// - `scrapePropertyForRent(urls)`  — extract rental UUID from og:image,
//   then call `/stingray/api/v1/rentals/{id}/floorPlans` and return its JSON.

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

async function fetchPage(url, { asText = true, readySelector = null } = {}) {
  const ws = await newBrowser();
  let browser;
  try {
    browser = await puppeteer.connect({ browserWSEndpoint: ws });
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
    if (readySelector) {
      try { await page.waitForSelector(readySelector, { timeout: 15000 }); } catch (_) {}
    }
    if (asText) {
      const body = await page.evaluate(() => document.body && document.body.innerText);
      if (body && body.trim()) return body;
    }
    return await page.content();
  } finally {
    try { await browser?.close(); } catch (_) {}
  }
}

// ---------------- parsers (mirror the upstream reference verbatim) ----------------

export function parseSearchApi(body) {
  return JSON.parse(body.replace("{}&&", "")).payload.homes;
}

export function parsePropertyForSale(html, url) {
  const $ = cheerio.load(html);
  const price = $("div[data-rf-test-id='abp-price'] > div").first().text() || null;
  const estimatedMonthlyPrice = $("span.est-monthly-payment").map((_, el) => $(el).text()).get().join("");
  const address = (
    $("div[class*='street-address']").map((_, el) => $(el).text()).get().join("") +
    " " +
    $("div[class*='cityStateZip']").map((_, el) => $(el).text()).get().join("")
  ).trim();
  const description = $("div#marketing-remarks-scroll p span").first().text() || null;
  const attachments = $("img[class*='widenPhoto']").map((_, el) => $(el).attr("src") ?? "").get();
  const details = $("div .keyDetails-value").map((_, el) => $(el).text()).get();
  const features = {};
  $(".amenity-group ul div.title").each((_, el) => {
    const label = $(el).text();
    const items = $(el).nextAll("li").find("span").map((_, span) => $(span).text().trim()).get();
    features[label] = items;
  });
  return {
    address,
    description,
    price,
    estimatedMonthlyPrice,
    propertyUrl: url,
    attachments,
    details,
    features,
  };
}

export function parsePropertyForRent(html) {
  const $ = cheerio.load(html);
  const data = $("meta[property='og:image']").attr("content");
  if (!data) return null;
  try {
    const rentalId = data.split("rent/")[1].split("/")[0];
    if (rentalId.length !== 36) return null;
    return rentalId;
  } catch (_) {
    return null;
  }
}

// ---------------- scrape functions (mirror the upstream reference verbatim) ----------------

export async function scrapeSearch(url) {
  const body = await fetchPage(url, { asText: true });
  return parseSearchApi(body);
}

export async function scrapePropertyForSale(urls) {
  const out = [];
  for (const url of urls) {
    const html = await fetchPage(url, {
      asText: false,
      readySelector: "div[data-rf-test-id='abp-price'], [class*='street-address']",
    });
    out.push(parsePropertyForSale(html, url));
  }
  return out;
}

export async function scrapePropertyForRent(urls) {
  const apiUrls = [];
  for (const url of urls) {
    const html = await fetchPage(url, {
      asText: false,
      readySelector: "meta[property='og:image']",
    });
    const rentalId = parsePropertyForRent(html);
    if (rentalId) {
      apiUrls.push(`https://www.redfin.com/stingray/api/v1/rentals/${rentalId}/floorPlans`);
    }
  }
  const out = [];
  for (const apiUrl of apiUrls) {
    const body = await fetchPage(apiUrl, { asText: true });
    out.push(JSON.parse(body));
  }
  return out;
}
