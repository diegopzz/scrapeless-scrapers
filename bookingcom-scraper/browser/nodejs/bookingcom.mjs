// Booking.com scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// function names and emitted field names match verbatim.
//
// Booking.com is aggressive about anti-bot — we delegate that to the
// Scrapeless cloud browser session (fresh fingerprint + residential proxy)
// and mirror the upstream reference's structure: location autocomplete, search HTML
// parsing, hotel detail + AvailabilityCalendar GraphQL, review GraphQL.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

// Booking.com aggressively blocks proxies, especially when the proxy region
// doesn't match the search region. Default to GB (matches the en-gb locale we
// pass on the URL); the per-call helpers accept a `proxyCountry` override so
// scrape_search can target e.g. MT/IT/ES/FR depending on the destination.
const DEFAULT_PROXY_COUNTRY = "GB";
const DEFAULT_SESSION_TTL = 300;

const TRANSIENT_NET_ERRORS = [
  "ERR_TUNNEL_CONNECTION_FAILED",
  "ERR_CONNECTION_CLOSED",
  "ERR_CONNECTION_RESET",
  "ERR_CONNECTION_REFUSED",
  "ERR_TIMED_OUT",
  "ERR_NETWORK_CHANGED",
  "ERR_EMPTY_RESPONSE",
  "ERR_PROXY_CONNECTION_FAILED",
  "Navigation timeout",
  "net::",
];

function isTransientError(err) {
  const msg = String(err?.message ?? err ?? "");
  return TRANSIENT_NET_ERRORS.some((s) => msg.includes(s));
}

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}
function client() { return new Scrapeless({ apiKey: requireKey() }); }
async function newSession(proxyCountry = DEFAULT_PROXY_COUNTRY) {
  return client().browser.create({ proxyCountry, sessionTTL: DEFAULT_SESSION_TTL });
}

// Retry helper: open a tab, run `fn(page)`, close. Retries up to `retries`
// times on transient network errors (ERR_TUNNEL_CONNECTION_FAILED etc.) with
// exponential backoff. Each attempt mints a fresh cloud-browser session so
// the proxy IP / fingerprint rotates.
async function withBrowserRetry(fn, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 2, label = "navigation" } = {}) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const { browserWSEndpoint } = await newSession(proxyCountry);
    let browser;
    try {
      browser = await puppeteer.connect({ browserWSEndpoint });
      const page = await browser.newPage();
      return await fn(page, browser);
    } catch (e) {
      lastError = e;
      if (!isTransientError(e) && attempt > 0) throw e;
      if (attempt === retries) break;
      const sleepMs = 5000 * Math.pow(2, attempt);
      await new Promise((r) => setTimeout(r, sleepMs));
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
  }
  throw new Error(`${label}: giving up after ${retries + 1} attempts: ${lastError?.message ?? lastError}`);
}

// ---------------- location suggestions ----------------

export async function searchLocationSuggestions(query, { proxyCountry = DEFAULT_PROXY_COUNTRY } = {}) {
  return withBrowserRetry(async (page) => {
    await page.goto("https://www.booking.com/", { waitUntil: "domcontentloaded", timeout: 45000 });
    const body = JSON.stringify({ query, pageview_id: "", aid: 800210, language: "en-us", size: 5 });
    const text = await page.evaluate(async ({ url, body }) => {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "text/plain;charset=UTF-8" },
        body,
        credentials: "include",
      });
      return await res.text();
    }, { url: "https://accommodations.booking.com/autocomplete.json", body });
    try { return JSON.parse(text); } catch { return { results: [] }; }
  }, { proxyCountry, label: "search_location_suggestions" });
}

// ---------------- search HTML parser ----------------

export function parseSearchHtml(html) {
  const $ = cheerio.load(html);
  const out = [];
  $("div[data-testid='property-card']").each((_, el) => {
    const card = $(el);
    const name = card.find("div[data-testid='title']").first().text().trim();
    const link = card.find("a[data-testid='title-link']").first().attr("href") ?? "";
    const location = card.find("span[data-testid='address']").first().text().trim();
    const distance = card.find("span[data-testid='distance']").first().text().trim();

    const score = card.find("div[data-testid='review-score'] > div").first().text().trim() || null;
    const reviewBlock = card.find("div[data-testid='review-score']").text();
    const reviewCountM = /([\d,]+)\s+reviews?/.exec(reviewBlock);
    const reviewCount = reviewCountM ? parseInt(reviewCountM[1].replace(/,/g, ""), 10) : null;
    const reviewWord = card.find("div[data-testid='review-score'] > div + div > div").first().text().trim() || null;

    const priceText = card.find("span[data-testid='price-and-discounted-price']").first().text().trim();
    const photo = card.find("img[data-testid='image']").first().attr("src") ?? null;

    const stars = card.find("div[data-testid='rating-stars'] svg").length;
    const starRating = stars || null;

    const freeCancellation = card.text().includes("Free cancellation");

    out.push({
      displayName: { text: name },
      basicPropertyData: {
        pageName: link,
        location: { address: location, city: null, countryCode: null },
        reviewScore: {
          score,
          reviewCount,
          totalScoreTextTag: { translation: reviewWord },
        },
        starRating: starRating ? { value: starRating } : null,
        photos: { main: photo ? { highResUrl: { relativeUrl: photo } } : null },
      },
      location: { displayLocation: location, mainDistance: distance || null },
      priceDisplayInfoIrene: {
        displayPrice: priceText ? { amountPerStay: { amount: priceText } } : null,
      },
      policies: { showFreeCancellation: Boolean(freeCancellation) },
    });
  });
  return out;
}

// ---------------- hotel parser ----------------

export function parseHotel(html, url) {
  const $ = cheerio.load(html);
  const features = {};
  $("[data-testid='property-most-popular-facilities-wrapper']").each((_, el) => {
    const header = $(el).find("h3").text().trim();
    const items = [];
    $(el).find("li").each((__, li) => {
      const t = $(li).text().trim();
      if (t) items.push(t);
    });
    if (header && items.length) features[header] = items;
  });
  const latlng = $("div[data-testid='PropertyHeaderAddressDesktop-wrapper']").find("a").attr("data-atlas-latlng");
  let lat = "", lng = "";
  if (latlng) [lat, lng] = latlng.split(",");
  const idMatch = /b_hotel_id:\s*'(.+?)'/.exec(html);
  const description = $("[data-capla-component-boundary='b-property-web-property-page/PropertyDescriptionDesktop']").text().trim();
  const images = [];
  $("#photo_wrapper img").each((_, el) => {
    const src = $(el).attr("src");
    if (src) images.push(src);
  });
  return {
    url,
    id: idMatch ? idMatch[1] : null,
    title: $("h2").first().text() || null,
    description,
    address: $("div[data-testid='PropertyHeaderAddressDesktop-wrapper']").find("button div").first().text() || null,
    images,
    lat,
    lng,
    features,
  };
}

// ---------------- scrape functions ----------------

export async function scrapeSearch(query, checkin = "", checkout = "", numberOfRooms = 1, maxPages = null, { proxyCountry = DEFAULT_PROXY_COUNTRY } = {}) {
  const loc = await searchLocationSuggestions(query, { proxyCountry });
  if (!loc.results?.length) return [];
  const destination = loc.results[0];
  const params = new URLSearchParams({
    ss: destination.value,
    ssne: destination.value,
    ssne_untouched: destination.value,
    checkin,
    checkout,
    no_rooms: String(numberOfRooms),
    dest_id: String(destination.dest_id),
    dest_type: destination.dest_type,
    efdco: "1",
    group_adults: "1",
    group_children: "0",
    lang: "en-gb",
    sb: "1",
    sb_travel_purpose: "leisure",
    src: "index",
    src_elem: "sb",
  });
  const baseUrl = "https://www.booking.com/searchresults.en-gb.html?" + params.toString();
  const pagesToScrape = maxPages ?? 1;
  const out = [];
  for (let i = 0; i < pagesToScrape; i++) {
    const offset = i * 25;
    const url = offset ? `${baseUrl}&offset=${offset}` : baseUrl;
    const cards = await withBrowserRetry(async (page) => {
      // Warm up against the homepage first so booking.com sets its session
      // cookies before we hit the heavily-defended search-results endpoint.
      try {
        await page.goto("https://www.booking.com/", { waitUntil: "domcontentloaded", timeout: 30000 });
        await new Promise((r) => setTimeout(r, 1500));
      } catch (_) {}
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
      try { await page.waitForSelector("div[data-testid='property-card']", { timeout: 30000 }); } catch (_) {}
      const html = await page.content();
      return parseSearchHtml(html);
    }, { proxyCountry, label: `scrape_search page=${i + 1}` });
    out.push(...cards);
    if (!cards.length) break;
  }
  return out;
}

export async function scrapeHotel(url, checkin, priceNDays = 61, { proxyCountry = DEFAULT_PROXY_COUNTRY } = {}) {
  return withBrowserRetry(async (page) => {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
    try { await page.waitForSelector("h2", { timeout: 30000 }); } catch (_) {}
    try {
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      await new Promise((r) => setTimeout(r, 1000));
      await page.evaluate(() => window.scrollTo(0, 0));
    } catch (_) {}
    const html = await page.content();
    const hotel = parseHotel(html, url);

    const country = (/hotelCountry:\s*"(.+?)"/.exec(html) || [])[1];
    const name = (/hotelName:\s*"(.+?)"/.exec(html) || [])[1];
    const csrf = (/b_csrf_token:\s*'(.+?)'/.exec(html) || [])[1];

    let priceDays = [];
    if (country && name && csrf) {
      const gqlBody = {
        operationName: "AvailabilityCalendar",
        variables: {
          input: {
            travelPurpose: 2,
            pagenameDetails: { countryCode: country, pagename: name },
            searchConfig: {
              searchConfigDate: { startDate: checkin, amountOfDays: priceNDays },
              nbAdults: 2,
              nbRooms: 1,
            },
          },
        },
        extensions: {},
        query:
          "query AvailabilityCalendar($input: AvailabilityCalendarQueryInput!) " +
          "{ availabilityCalendar(input: $input) { ... on AvailabilityCalendarQueryResult " +
          "{ hotelId days { available avgPriceFormatted checkin minLengthOfStay __typename } " +
          "__typename } ... on AvailabilityCalendarQueryError { message __typename } __typename } }",
      };
      const text = await page.evaluate(async ({ url, body, csrf, referer }) => {
        const res = await fetch(url, {
          method: "POST",
          headers: {
            "content-type": "application/json",
            "x-booking-csrf-token": csrf,
            referer,
            origin: "https://www.booking.com",
          },
          body: JSON.stringify(body),
          credentials: "include",
        });
        return await res.text();
      }, { url: "https://www.booking.com/dml/graphql?lang=en-gb", body: gqlBody, csrf, referer: url });
      try {
        const data = JSON.parse(text);
        priceDays = data?.data?.availabilityCalendar?.days ?? [];
      } catch (_) {}
    }
    hotel.price = priceDays;
    return hotel;
  }, { proxyCountry, label: "scrape_hotel" });
}

export async function scrapeHotelReviews(url, maxPages = null, { proxyCountry = DEFAULT_PROXY_COUNTRY } = {}) {
  const reviewsPageUrl = `${url}?force_referer=#tab-reviews`;
  return withBrowserRetry(async (page) => {
    const captured = {};
    page.on("response", async (response) => {
      try {
        if (!response.url().includes("/dml/graphql")) return;
        const body = await response.text();
        if (body.includes("reviewCard")) {
          captured.body = body;
          captured.request_body = response.request().postData() ?? "";
        }
      } catch (_) {}
    });
    await page.goto(reviewsPageUrl, { waitUntil: "domcontentloaded", timeout: 60000 });
    try {
      await page.waitForSelector("button[data-testid='fr-read-all-reviews']", { timeout: 15000 });
      await page.click("button[data-testid='fr-read-all-reviews']");
    } catch (_) {
      try { await page.waitForSelector("[data-testid='PropertyReviewsRegionBlock']", { timeout: 15000 }); } catch (_) {}
    }
    const deadline = Date.now() + 20000;
    while (!captured.body && Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 500));
    }
    if (!captured.body) return [];

    const first = JSON.parse(captured.body);
    const initial = first?.data?.reviewListFrontend ?? {};
    const totalReviewCount = parseInt(initial?.reviewsCount ?? 0, 10);
    const out = [];
    out.push(...(initial?.reviewCard ?? []));

    let totalPages = totalReviewCount ? Math.ceil(totalReviewCount / 10) : 1;
    if (maxPages == null || maxPages > totalPages) maxPages = totalPages;

    const html = await page.content();
    const csrf = (/b_csrf_token:\s*'(.+?)'/.exec(html) || [])[1];
    let gqlBody;
    try { gqlBody = JSON.parse(captured.request_body); } catch { gqlBody = null; }

    if (gqlBody && csrf) {
      for (let offset = 10; offset < maxPages * 10; offset += 10) {
        const pageBody = JSON.parse(JSON.stringify(gqlBody));
        try { pageBody.variables.input.skip = offset; } catch { continue; }
        const text = await page.evaluate(async ({ url, body, csrf, referer }) => {
          const res = await fetch(url, {
            method: "POST",
            headers: {
              "content-type": "application/json",
              "x-booking-csrf-token": csrf,
              referer,
              origin: "https://www.booking.com",
            },
            body: JSON.stringify(body),
            credentials: "include",
          });
          return await res.text();
        }, { url: "https://www.booking.com/dml/graphql?lang=en-gb", body: pageBody, csrf, referer: reviewsPageUrl });
        try {
          const data = JSON.parse(text);
          out.push(...(data?.data?.reviewListFrontend?.reviewCard ?? []));
        } catch (_) {}
      }
    }
    return out;
  }, { proxyCountry, label: "scrape_hotel_reviews" });
}
