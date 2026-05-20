// Zoopla scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// function names + emitted field names match verbatim.
//
// Two surfaces:
// - `scrapeProperties(urls)`                                       — DOM-parse property page.
// - `scrapeSearch(scrapeAllPages, locationSlug, maxScrapePages, queryType)` — DOM-parse cards.
//
// Uses a GB residential proxy (Zoopla is geo-locked + Akamai-protected).

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

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

async function fetchHtml(url, readySelector, { autoScroll = false } = {}) {
  const ws = await newBrowser();
  let browser;
  try {
    browser = await puppeteer.connect({ browserWSEndpoint: ws });
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
    if (readySelector) {
      try { await page.waitForSelector(readySelector, { timeout: 15000 }); } catch (_) {}
    }
    if (autoScroll) {
      try {
        await page.evaluate(async () => {
          const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
          const step = 600;
          for (let y = 0; y < document.body.scrollHeight; y += step) {
            window.scrollTo(0, y);
            await sleep(150);
          }
          window.scrollTo(0, 0);
        });
        await new Promise((r) => setTimeout(r, 1000));
      } catch (_) {}
    }
    return await page.content();
  } finally {
    try { await browser?.close(); } catch (_) {}
  }
}

const intOrNull = (s) => {
  if (!s) return null;
  const n = parseInt(String(s).split(" ")[0].replace(/[£,~]/g, ""), 10);
  return Number.isFinite(n) ? n : null;
};

// ---------------- parsers (mirror the upstream reference verbatim) ----------------

export function parseProperty(html) {
  const $ = cheerio.load(html);
  const url = $('meta[property="og:url"]').attr("content") ?? null;
  const price = $("p").filter((_, el) => /£/.test($(el).text())).first().text() || null;
  const receptions = $("p").filter((_, el) => /reception/.test($(el).text())).first().text() || null;
  const baths = $("p").filter((_, el) => /bath/.test($(el).text())).first().text() || null;
  const beds = $("p").filter((_, el) => /bed/.test($(el).text())).first().text() || null;
  const gmapSrcs = $("section[aria-labelledby='local-area'] picture source")
    .map((_, el) => $(el).attr("srcset"))
    .get();
  const gmapSource = gmapSrcs.length ? gmapSrcs[gmapSrcs.length - 1] : null;
  const coordinates = gmapSource && gmapSource.includes("/static/")
    ? gmapSource.split("/static/")[1].split("/")[0]
    : null;
  const agentPath = $("section[aria-label='Contact agent'] a").first().attr("href") ?? null;

  const info = [];
  $("section[aria-labelledby='key-info'] li").each((_, li) => {
    const $li = $(li);
    const title = $li.find("p").first().text() || null;
    const value = $li.find("div p").first().text() || null;
    if (value !== null && value !== "") info.push({ title, value });
  });

  const nearby = [];
  $("div:has(section[aria-label*='Travel']) section:nth-of-type(3) li div").each((_, div) => {
    const $div = $(div);
    const distance = $div.find("p").eq(1).text() || null;
    nearby.push({
      title: $div.find("p").first().text() || null,
      distance: distance ? parseFloat(distance.split(" ")[0]) : null,
      unit: distance ? distance.split(" ")[1] : null,
    });
  });

  const idFromUrl = url && url.includes("details/")
    ? parseInt(url.split("details/").pop().split("/")[0], 10)
    : null;

  return {
    id: Number.isFinite(idFromUrl) ? idFromUrl : null,
    url,
    title: $("title").first().text() || null,
    address: $("address").first().text() || null,
    price: {
      amount: price ? parseInt(price.replace(/£|,/g, ""), 10) : null,
      currency: "£",
    },
    gallery: $("li[data-key*='gallery'] picture source")
      .last()
      .toArray()
      .map((el) => $(el).attr("srcset"))
      .filter(Boolean),
    epcRating: $("p").filter((_, el) => /EPC/.test($(el).text())).first().text() || null,
    floorArea: $("p").filter((_, el) => /ft/.test($(el).text())).first().text() || null,
    numOfReceptions: intOrNull(receptions),
    numOfBathrooms: intOrNull(baths),
    numOfBedrooms: intOrNull(beds),
    propertyTags: $("section ul").first().find("li p").map((_, el) => $(el).text()).get(),
    propertyInfo: info,
    propertyDescription: $("section[aria-labelledby='about'] ul li p span")
      .map((_, el) => $(el).text())
      .get(),
    coordinates: {
      googleMapeSource: gmapSource,
      latitude: coordinates ? parseFloat(coordinates.split(",")[0]) : null,
      longitude: coordinates ? parseFloat(coordinates.split(",")[1]) : null,
    },
    nearby,
    agent: {
      name: $("section[aria-label='Contact agent'] p").first().text() || null,
      logo: $("section[aria-label='Contact agent'] img").first().attr("src") ?? null,
      url: agentPath ? "https://www.zoopla.co.uk" + agentPath : null,
    },
  };
}

export function parseSearch(html) {
  const $ = cheerio.load(html);
  const data = [];
  const targetingRaw = $("script#__ZAD_TARGETING__").first().text();
  let totalResults = 0;
  try {
    if (targetingRaw) totalResults = parseInt(JSON.parse(targetingRaw).search_results_count, 10) || 0;
  } catch (_) {}
  const boxes = $("div[data-testid='regular-listings'] > div");
  const resultsCount = boxes.length || 1;
  const totalPages = Math.floor(totalResults / resultsCount);

  boxes.each((_, box) => {
    const $box = $(box);
    const url = $box.find("a").first().attr("href");
    if (!url) return;
    const price = $box.find("p[class*='priceText']").first().text() || null;
    const sqFtText = $box.find("span").filter((_, el) => /sq ft/.test($(el).text())).first().text() || null;
    const bathrooms = $box.find("span").filter((_, el) => /bath/.test($(el).text())).first().text() || null;
    const bedrooms = $box.find("span").filter((_, el) => /bed/.test($(el).text())).first().text() || null;
    const livingrooms = $box.find("span").filter((_, el) => /reception/.test($(el).text())).first().text() || null;
    const image = $box.find("picture source").first().attr("srcset") || null;
    const agency = $("img[src*='agent']").first().attr("alt") ?? null;
    data.push({
      price: price ? parseInt(price.split(" ")[0].replace(/£|,/g, ""), 10) : null,
      priceCurrency: "Sterling pound £",
      url: url ? "https://www.zoopla.co.uk" + url.split("?")[0] : null,
      image: image ? image.split(":p")[0] : null,
      address: $box.find("address").first().text() || null,
      squareFt: sqFtText ? parseInt(sqFtText.split(" ")[0].replace(/[~,]/g, ""), 10) : null,
      numBathrooms: bathrooms ? parseInt(bathrooms.split(" ")[0], 10) : null,
      numBedrooms: bedrooms ? parseInt(bedrooms.split(" ")[0], 10) : null,
      numLivingRoom: livingrooms ? parseInt(livingrooms.split(" ")[0], 10) : null,
      description: $box.find("a:has(address) p").first().text() || null,
      justAdded: $box.find("div").filter((_, el) => $(el).text() === "Just added").length > 0,
      agency,
    });
  });
  return { search_data: data, total_pages: totalPages };
}

// ---------------- scrape functions (mirror the upstream reference verbatim) ----------------

export async function scrapeProperties(urls) {
  const out = [];
  for (const url of urls) {
    try {
      const html = await fetchHtml(url, "section[aria-labelledby='local-area']", { autoScroll: true });
      out.push(parseProperty(html));
    } catch (e) {
      console.warn(`error scraping ${url}: ${e.message}`);
    }
  }
  return out;
}

export async function scrapeSearch(scrapeAllPages, locationSlug, maxScrapePages = 10, queryType = "for-sale") {
  const firstUrl = `https://www.zoopla.co.uk/${queryType}/property/${locationSlug}`;
  const firstHtml = await fetchHtml(firstUrl, "p[data-testid='total-results']", { autoScroll: true });
  const first = parseSearch(firstHtml);
  const searchData = [...first.search_data];
  const maxPages = first.total_pages;
  const totalToScrape = scrapeAllPages || maxScrapePages >= maxPages ? maxPages : maxScrapePages;
  for (let p = 2; p <= totalToScrape; p++) {
    try {
      const html = await fetchHtml(`${firstUrl}?pn=${p}`, "div[data-testid='regular-listings']");
      searchData.push(...parseSearch(html).search_data);
    } catch (e) {
      console.warn(`failed page ${p}: ${e.message}`);
    }
  }
  return searchData;
}
