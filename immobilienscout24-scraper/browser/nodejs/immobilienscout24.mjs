// Immobilienscout24 scraper using @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Mirrors  —
// function names and emitted field names (including the upstream reference's typos like
// `propertyLlink`, `propertySepcs`, `priceWithoutHeadting`) match verbatim.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const PROXY_COUNTRY = "DE";
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

// ---------------- parsers ----------------

function textOrNull($, sel) {
  const t = $(sel).first().text().trim();
  return t || null;
}

export function parseProperty(html, url) {
  const $ = cheerio.load(html);
  const canonical = $("link[rel='canonical']").attr("href") || url;
  const idMatch = /\/expose\/(\d+)/.exec(canonical);
  const id = idMatch ? idMatch[1] : "";

  const priceText = $("dd.is24qa-kaltmiete, dd[class*='kaltmiete']").first().text().trim();
  const currencyMatch = /([€$£])/.exec(priceText);
  const priceCurrency = currencyMatch ? currencyMatch[1] : null;

  const propertyImages = [];
  $(".sp-slides .sp-slide img").each((_, el) => {
    const src = $(el).attr("data-src");
    if (src) propertyImages.push(src);
  });
  const videoAvailable = $(".sp-slides .sp-video").length > 0;

  const internetText = $("a[class*='mediaavailcheck']").first().text().toLowerCase();
  const additionalSpecs = [];
  $("div[class*='criteriagroup'] dd").each((_, el) => {
    const t = $(el).text().trim();
    if (t) additionalSpecs.push(t);
  });

  return {
    id,
    title: $("h1#expose-title").first().text().trim(),
    description: $("meta[name='description']").attr("content") || null,
    address: textOrNull($, ".address-block > div > span:nth-child(2)"),
    propertyLlink: canonical,
    propertySepcs: {
      floorsNumber: textOrNull($, "dd[class*='etage']"),
      livingSpace: textOrNull($, "dd[class*='wohnflaeche']"),
      livingSpaceUnit: textOrNull($, "dd[class*='wohnflaeche'] span"),
      vacantFrom: textOrNull($, "dd[class*='bezugsfrei']"),
      numberOfRooms: textOrNull($, "dd[class*='zimmer']"),
      "Garage/parking space": textOrNull($, "dd[class*='garage-stellplatz']"),
      additionalSpecs,
      internetAvailable: internetText.includes("verfügbar") || internetText.includes("available"),
    },
    price: {
      priceWithoutHeadting: priceText || null,
      priceperMeter: textOrNull($, "dd[class*='preism2']"),
      additionalCosts: textOrNull($, "dd[class*='nebenkosten']"),
      heatingCosts: textOrNull($, "dd[class*='heizkosten']"),
      totalRent: textOrNull($, "dd[class*='gesamtmiete']"),
      basisRent: textOrNull($, "dd[class*='baseprice']"),
      deposit: textOrNull($, "dd[class*='kaution']"),
      "garage/parkingRent": textOrNull($, "dd[class*='stellplatzmiete']"),
      priceCurrency,
    },
    building: {
      constructionYear: textOrNull($, "dd[class*='baujahr']"),
      energySources: textOrNull($, "dd[class*='energietraeger']"),
      energyCertificate: textOrNull($, "dd[class*='energieausweis']"),
      energyCertificateType: textOrNull($, "dd[class*='energieausweistyp']"),
      energyCertificateDate: textOrNull($, "dd[class*='energieausweis-gueltig']"),
      finalEnergyRrequirement: textOrNull($, "dd[class*='endenergiebedarf']"),
    },
    attachments: {
      propertyImages,
      videoAvailable,
    },
    agencyName: textOrNull($, "span[data-qa='companyName']"),
    agencyAddress: textOrNull($, "div[data-qa='companyAddress']"),
  };
}

function searchPropertyUrls(html) {
  const $ = cheerio.load(html);
  const out = new Set();
  $("a[href*='/expose/']").each((_, el) => {
    let href = $(el).attr("href") || "";
    if (href.startsWith("/")) href = "https://www.immobilienscout24.de" + href;
    href = href.split("#")[0];
    if (href) out.add(href);
  });
  return [...out];
}

// ---------------- scrape functions ----------------

export async function scrapeProperties(urls) {
  const out = [];
  for (const u of urls) {
    const html = await fetchRenderedHtml(u, "h1#expose-title");
    out.push(parseProperty(html, u));
  }
  return out;
}

export async function scrapeSearch(url, scrapeAllPages = false, maxScrapePages = 10) {
  const first = await fetchRenderedHtml(url, "a[href*='/expose/']");
  let propertyUrls = searchPropertyUrls(first);

  const $ = cheerio.load(first);
  let totalPages = 1;
  $("a[href*='pagenumber=']").each((_, el) => {
    const href = $(el).attr("href") || "";
    const m = /pagenumber=(\d+)/.exec(href);
    if (m) totalPages = Math.max(totalPages, parseInt(m[1], 10));
  });
  if (!scrapeAllPages) totalPages = Math.min(totalPages, maxScrapePages);

  for (let page = 2; page <= totalPages; page++) {
    const sep = url.includes("?") ? "&" : "?";
    const pageUrl = `${url}${sep}pagenumber=${page}`;
    const html = await fetchRenderedHtml(pageUrl, "a[href*='/expose/']");
    propertyUrls.push(...searchPropertyUrls(html));
  }
  propertyUrls = [...new Set(propertyUrls)];

  return scrapeProperties(propertyUrls);
}
