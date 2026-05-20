// TripAdvisor scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// the function names and emitted field shapes match verbatim, so downstream code
// can import { Scrapeless } from "@scrapeless-ai/sdk";
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

function _looksBlocked(html) {
  if (!html || html.length < 5000) return true;
  // TripAdvisor's anti-bot shell page lands on a sub-2k page titled "tripadvisor.com".
  if (/Captcha Interception|Pardon Our Interruption/i.test(html)) return true;
  if (/<title>tripadvisor\.com<\/title>/i.test(html) && html.length < 5000) return true;
  return false;
}

async function fetchRenderedHtml(url, readySelector, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 2, warmup = true } = {}) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const { browserWSEndpoint } = await client().browser.create({ proxyCountry, sessionTTL: DEFAULT_SESSION_TTL });
    let browser;
    try {
      browser = await puppeteer.connect({ browserWSEndpoint });
      const page = await browser.newPage();
      // Warm up cookies on tripadvisor.com first — fresh proxies otherwise hit
      // a Captcha Interception shell page on direct hotel/search hits.
      if (warmup) {
        try {
          await page.goto("https://www.tripadvisor.com/", { waitUntil: "domcontentloaded", timeout: 30000 });
          await new Promise((r) => setTimeout(r, 2500));
        } catch (_) {}
      }
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
      if (readySelector) {
        try { await page.waitForSelector(readySelector, { timeout: 15000 }); } catch (_) {}
      }
      await new Promise((r) => setTimeout(r, 2000));
      const html = await page.content();
      if (html && !_looksBlocked(html)) return html;
      lastError = new Error(_looksBlocked(html) ? "captcha block" : "empty HTML");
    } catch (e) {
      lastError = e;
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
  }
  throw new Error(`giving up after ${retries + 1} attempts: ${lastError?.message}`);
}

// ---------------- location autocomplete ----------------

export async function scrapeLocationData(query) {
  const { browserWSEndpoint } = await client().browser.create({
    proxyCountry: DEFAULT_PROXY_COUNTRY,
    sessionTTL: DEFAULT_SESSION_TTL,
  });
  const captured = [];
  let browser;
  try {
    browser = await puppeteer.connect({ browserWSEndpoint });
    const page = await browser.newPage();
    page.on("response", async (resp) => {
      try {
        if (!resp.url().includes("graphql")) return;
        const body = await resp.json();
        for (const entry of Array.isArray(body) ? body : [body]) {
          if (entry?.data?.Typeahead_autocomplete) {
            captured.push(...(entry.data.Typeahead_autocomplete.results ?? []));
          }
        }
      } catch (_) {}
    });
    await page.goto("https://www.tripadvisor.com/", { waitUntil: "domcontentloaded", timeout: 30000 });
    // TripAdvisor's homepage initially renders the search input as visually
    // hidden (a "Where to?" prompt). Clicking the document brings the real
    // <input name="q"> into the focus stack; once focused, the typeahead
    // XHR fires on every keystroke.
    await new Promise((r) => setTimeout(r, 5000));
    try {
      await page.evaluate(() => { document.documentElement.click(); });
    } catch (_) {}
    await new Promise((r) => setTimeout(r, 1500));
    // Explicitly focus the visible search input before typing.
    try {
      await page.evaluate(() => {
        for (const i of document.querySelectorAll('input[name="q"]')) {
          if (i.offsetParent) { i.focus(); return; }
        }
      });
    } catch (_) {}
    await new Promise((r) => setTimeout(r, 500));
    try {
      await page.keyboard.type(query, { delay: 150 });
    } catch (_) {}
    await new Promise((r) => setTimeout(r, 8000));
  } finally {
    try { await browser?.close(); } catch (_) {}
  }
  return captured.map(normalizeLocationItem).filter((x) => x.localizedName && x.url);
}

function normalizeLocationItem(node) {
  const info = node?.contentLocationNode?.detail?.info ?? {};
  const routes = info.linkRoutes ?? [];
  const byKey = (k) => {
    const m = routes.find((r) => (r?.linkType || "").toUpperCase() === k);
    return m?.webLinkUrl ? `https://www.tripadvisor.com${m.webLinkUrl}` : null;
  };
  const primary = info.primaryRoute?.webLinkUrl
    ? `https://www.tripadvisor.com${info.primaryRoute.webLinkUrl}`
    : null;
  return {
    localizedName: info.localizedName ?? null,
    url: primary,
    HOTELS_URL: byKey("HOTELS"),
    ATTRACTIONS_URL: byKey("ATTRACTIONS"),
    RESTAURANTS_URL: byKey("RESTAURANTS"),
  };
}

// ---------------- search ----------------

export function parseSearchPage(html, baseUrl) {
  const $ = cheerio.load(html);
  const parsed = [];
  $("div[data-test-target='hotels-main-list'] ol li").each((_, li) => {
    const titles = $(li).find("div[data-automation=hotel-card-title] a h3").map((__, h) => $(h).text()).get();
    const title = titles.length > 1 ? titles[1] : titles[0] ?? null;
    const href = $(li).find("div[data-automation=hotel-card-title] a").first().attr("href");
    if (!href) return;
    const abs = new URL(href, baseUrl);
    abs.search = "";
    abs.hash = "";
    parsed.push({ url: abs.toString(), name: title });
  });
  if (parsed.length) return parsed;
  $("div.listing_title > a").each((_, a) => {
    const href = $(a).attr("href") ?? "";
    const text = $(a).text() ?? "";
    parsed.push({ url: new URL(href, baseUrl).toString(), name: text.split(". ").slice(-1)[0] });
  });
  return parsed;
}

export async function scrapeSearch(searchUrl, maxPages = null) {
  const firstHtml = await fetchRenderedHtml(searchUrl, "div[data-test-target='hotels-main-list']");
  const results = parseSearchPage(firstHtml, searchUrl);
  if (!results.length) return [];

  const $ = cheerio.load(firstHtml);
  const counterText = $("div[data-test-target='hotels-main-list'] span").text();
  const match = counterText.match(/(\d[\d,]*)/);
  const totalResults = match ? parseInt(match[1].replace(/,/g, ""), 10) : results.length;
  const nextHref = $("a[aria-label='Next page']").attr("href");
  const pageSize = results.length;
  let totalPages = Math.ceil(totalResults / Math.max(pageSize, 1));
  if (maxPages && totalPages > maxPages) totalPages = maxPages;
  if (!nextHref || totalPages <= 1) return results;
  const nextAbs = new URL(nextHref, searchUrl).toString();
  const others = [];
  for (let i = 1; i < totalPages; i++) {
    others.push(nextAbs.replace(`oa${pageSize}`, `oa${pageSize * i}`));
  }
  for (const url of others) {
    try {
      const html = await fetchRenderedHtml(url, "div[data-test-target='hotels-main-list']");
      results.push(...parseSearchPage(html, url));
    } catch (_) {}
  }
  return results;
}

// ---------------- hotel ----------------

export function parseHotelPage(html) {
  const $ = cheerio.load(html);
  let basicData = {};
  // Prefer the explicit JSON-LD LodgingBusiness block. Several `<script>` tags
  // (analytics, tracking) mention "aggregateRating" too, so filter to ld+json.
  $('script[type="application/ld+json"]').each((_, el) => {
    const txt = $(el).contents().text();
    if (!txt) return;
    let parsed;
    try { parsed = JSON.parse(txt); } catch (_) { return; }
    const candidates = Array.isArray(parsed) ? parsed : (parsed["@graph"] ? parsed["@graph"] : [parsed]);
    for (const node of candidates) {
      if (!node || typeof node !== "object") continue;
      const t = node["@type"];
      if (t === "LodgingBusiness" || t === "Hotel" || (Array.isArray(t) && t.some((x) => /Lodging|Hotel/.test(x)))) {
        basicData = node;
        return false;
      }
    }
  });
  if (!Object.keys(basicData).length) {
    const basicScript = $("script:contains('aggregateRating')").first().contents().text();
    if (basicScript) {
      try { basicData = JSON.parse(basicScript); } catch (_) {}
    }
  }
  const description = $("div[data-automation='aboutTabDescription'] div div div").first().text() || null;
  const featues = [];
  $("div[data-test-target*='amenity']").each((_, el) => {
    const t = $(el).text();
    if (t) featues.push(t);
  });

  const reviews = [];
  $("div[data-test-target='HR_CC_CARD']").each((_, el) => {
    const $r = $(el);
    const title = $r.find("div[data-test-target='review-title'] span").first().text() || null;
    const textParts = $r.find("div._c div[class*='fIrGe'] span[class*='JguWG'] span").map((__, s) => $(s).text()).get();
    const text = textParts.join("");
    const rateText = $r.find(":contains('of 5 bubbles')").last().text();
    const rateMatch = rateText.match(/([\d.]+) of 5 bubbles/);
    const rate = rateMatch ? parseFloat(rateMatch[1]) : null;
    const tripDate = $r.find("span:contains('Date of stay:')").parent().next("span").text() || null;
    const tripType = $r.find("span:contains('Trip type:')").parent().next("span").text() || null;
    reviews.push({ title, text, rate, tripDate, tripType });
  });

  // NB: the upstream reference typo "featues" preserved for parity.
  return { basic_data: basicData, description, featues, reviews };
}

export async function scrapeHotel(url, maxReviewPages = null) {
  const firstHtml = await fetchRenderedHtml(url, "div[data-test-target='HR_CC_CARD']");
  const hotelData = parseHotelPage(firstHtml);
  const REVIEW_PAGE_SIZE = 10;
  let totalReviews = 0;
  try {
    totalReviews = parseInt(hotelData.basic_data?.aggregateRating?.reviewCount ?? 0, 10);
  } catch (_) {}
  let totalReviewPages = totalReviews ? Math.ceil(totalReviews / REVIEW_PAGE_SIZE) : 0;
  if (maxReviewPages && maxReviewPages < totalReviewPages) totalReviewPages = maxReviewPages;
  const reviewUrls = [];
  for (let i = 1; i <= totalReviewPages; i++) {
    reviewUrls.push(url.replace("-Reviews-", `-Reviews-or${REVIEW_PAGE_SIZE * i}-`));
  }
  for (const reviewUrl of reviewUrls) {
    try {
      const html = await fetchRenderedHtml(reviewUrl, "div[data-test-target='HR_CC_CARD']");
      hotelData.reviews.push(...parseHotelPage(html).reviews);
    } catch (_) {}
  }
  return hotelData;
}
