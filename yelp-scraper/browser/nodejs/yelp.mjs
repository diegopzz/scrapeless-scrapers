// Yelp scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// the function names and emitted field shapes match verbatim, so downstream
// code can import { Scrapeless } from "@scrapeless-ai/sdk";
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

function looksBlocked(html) {
  if (!html || html.length < 5000) return true;
  if (/captcha-delivery\.com|DataDome CAPTCHA|px-captcha|Pardon Our Interruption/i.test(html)) return true;
  return false;
}

async function fetchRenderedHtml(url, readySelector, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 2, warmup = true } = {}) {
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
      // Warmup: visit yelp.com first so the session picks up DataDome cookies
      // before navigating to the deeper URL — second-hop traffic is far less
      // likely to trip the CAPTCHA interstitial.
      if (warmup) {
        try {
          await page.goto("https://www.yelp.com/", { waitUntil: "domcontentloaded", timeout: 30000 });
          await new Promise((r) => setTimeout(r, 1500));
        } catch (_) {}
      }
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
      if (readySelector) {
        try {
          await page.waitForSelector(readySelector, { timeout: 15000 });
        } catch (_) {
          // non-fatal
        }
      }
      const html = await page.content();
      if (html && !looksBlocked(html)) return html;
      lastError = new Error(looksBlocked(html) ? "anti-bot block" : "empty HTML");
    } catch (e) {
      lastError = e;
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
  }
  throw new Error(`giving up after ${retries + 1} attempts: ${lastError?.message}`);
}

async function postJson(url, payload, headers, { proxyCountry = DEFAULT_PROXY_COUNTRY } = {}) {
  const { browserWSEndpoint } = await client().browser.create({
    proxyCountry,
    sessionTTL: DEFAULT_SESSION_TTL,
  });
  let browser;
  try {
    browser = await puppeteer.connect({ browserWSEndpoint });
    const page = await browser.newPage();
    const referer = headers.referer ?? "https://www.yelp.com/";
    try {
      await page.goto(referer, { waitUntil: "domcontentloaded", timeout: 30000 });
    } catch (_) {}
    const text = await page.evaluate(
      async ([u, body, h]) => {
        const r = await fetch(u, { method: "POST", headers: h, body, credentials: "include" });
        return await r.text();
      },
      [url, payload, headers],
    );
    return text;
  } finally {
    try { await browser?.close(); } catch (_) {}
  }
}

// ---------------- parsers (mirror the upstream reference's function names) ----------------

function _readBusinessJsonLd($) {
  const blocks = [];
  $('script[type="application/ld+json"]').each((_, el) => {
    try {
      const raw = $(el).contents().text();
      if (!raw) return;
      const data = JSON.parse(raw);
      if (Array.isArray(data)) blocks.push(...data);
      else blocks.push(data);
    } catch (_) {}
  });
  const types = new Set([
    "Restaurant", "LocalBusiness", "FoodEstablishment", "Bar",
    "CafeOrCoffeeShop", "Hotel", "Store", "Organization",
  ]);
  const isBusiness = (node) => {
    if (!node || typeof node !== "object") return false;
    const t = node["@type"];
    if (typeof t === "string") return types.has(t);
    if (Array.isArray(t)) return t.some((x) => types.has(x));
    return false;
  };
  return blocks.find(isBusiness) || null;
}

function _addressToString(addr) {
  if (!addr || typeof addr !== "object") return typeof addr === "string" ? addr : "";
  const parts = [addr.streetAddress, addr.addressLocality, addr.addressRegion, addr.postalCode, addr.addressCountry]
    .filter((x) => typeof x === "string" && x.trim());
  return parts.join(", ");
}

function _jsonLdOpenHours(node) {
  // schema.org openingHoursSpecification → { mon: "08:00-17:00", ... }
  const out = {};
  const spec = node?.openingHoursSpecification;
  if (!Array.isArray(spec)) return out;
  for (const entry of spec) {
    const days = Array.isArray(entry?.dayOfWeek) ? entry.dayOfWeek : [entry?.dayOfWeek];
    const opens = entry?.opens ?? "";
    const closes = entry?.closes ?? "";
    const range = opens && closes ? `${opens}-${closes}` : (opens || closes || "");
    for (const day of days) {
      if (typeof day !== "string") continue;
      const key = day.split("/").pop().slice(0, 3).toLowerCase();
      out[key] = range;
    }
  }
  return out;
}

export function parsePage(html) {
  const $ = cheerio.load(html);
  const openHours = {};
  $('th p').each((_, el) => {
    const $p = $(el);
    if (!/day-of-the-week/.test($p.attr("class") || "")) return;
    const name = $p.text().trim();
    const value = $p.parent().parent().find("td p").first().text().trim();
    if (name) openHours[name.toLowerCase()] = value;
  });

  const xText = (sel) => ($(sel).first().text() || "").trim();
  const out = {
    name: xText("h1"),
    website: xText('p:contains("Business website") + p a'),
    phone: xText('p:contains("Phone number") + p'),
    address: (() => {
      const link = $('a:contains("Get Directions")').first();
      return (link.parent().next("p").text() || "").trim();
    })(),
    logo: $('img[class*="businessLogo"]').first().attr("src") || "",
    claim_status: $('span:has(> span[class*="claim"])').first().text().trim().toLowerCase(),
    open_hours: openHours,
  };

  // JSON-LD fallback — the DOM selectors above are fragile across Yelp's
  // A/B layouts. The Restaurant/LocalBusiness JSON-LD block reliably carries
  // name, telephone, address, logo and openingHoursSpecification.
  const business = _readBusinessJsonLd($);
  if (business) {
    if (!out.name) out.name = (business.name ?? "").toString().replace(/&apos;/g, "'");
    if (!out.phone) out.phone = (business.telephone ?? "").toString();
    if (!out.address) out.address = _addressToString(business.address);
    if (!out.website) {
      // Yelp sometimes carries a sameAs[] or url
      const same = business.sameAs;
      if (Array.isArray(same) && same.length) out.website = same[0];
      else if (typeof business.url === "string" && !business.url.includes("yelp.com")) out.website = business.url;
    }
    if (!out.logo) {
      const img = business.image;
      if (typeof img === "string") out.logo = img;
      else if (img && typeof img === "object" && typeof img.url === "string") out.logo = img.url;
    }
    if (!Object.keys(out.open_hours).length) {
      const oh = _jsonLdOpenHours(business);
      if (Object.keys(oh).length) out.open_hours = oh;
    }
  }
  return out;
}

export function parseBusinessId(html) {
  const $ = cheerio.load(html);
  return $('meta[name="yelp-biz-id"]').attr("content") || null;
}

function pluck(node, path) {
  // tiny safe getter, e.g. pluck(node, "feedback.coolCount")
  return path.split(".").reduce((acc, k) => (acc == null ? acc : acc[k]), node);
}

export function parseReviewData(responseText) {
  const data = JSON.parse(responseText);
  const reviews = data[0].data.business.reviews.edges;
  const parsedReviews = reviews.map((edge) => {
    const node = edge.node;
    return {
      encid: node.encid,
      text: { full: pluck(node, "text.full"), language: pluck(node, "text.language") },
      rating: node.rating,
      feedback: {
        coolCount: pluck(node, "feedback.coolCount"),
        funnyCount: pluck(node, "feedback.funnyCount"),
        usefulCount: pluck(node, "feedback.usefulCount"),
      },
      author: {
        encid: pluck(node, "author.encid"),
        displayName: pluck(node, "author.displayName"),
        displayLocation: pluck(node, "author.displayLocation"),
        reviewCount: pluck(node, "author.reviewCount"),
        friendCount: pluck(node, "author.friendCount"),
        businessPhotoCount: pluck(node, "author.businessPhotoCount"),
      },
      business: {
        encid: pluck(node, "business.encid"),
        alias: pluck(node, "business.alias"),
        name: pluck(node, "business.name"),
      },
      createdAt: pluck(node, "createdAt.utcDateTime"),
      businessPhotos: (node.businessPhotos ?? []).map((p) => ({
        encid: p.encid,
        photoUrl: pluck(p, "photoUrl.url"),
        caption: p.caption,
        helpfulCount: p.helpfulCount,
      })),
      businessVideos: node.businessVideos,
      availableReactions: (pluck(node, "availableReactionsContainer.availableReactions") ?? []).map((r) => ({
        displayText: r.displayText,
        reactionType: r.reactionType,
        count: r.count,
      })),
    };
  });
  const totalReviews = data[0].data.business.reviewCount;
  return { reviews: parsedReviews, total_reviews: totalReviews };
}

export function parseSearch(html) {
  const $ = cheerio.load(html);
  const script = $("script[data-id='react-root-props']").first().contents().text();
  const searchData = [];
  let totalResults = 0;
  if (!script) return { search_data: searchData, total_results: totalResults };
  const raw = script.split("react_root_props = ").slice(-1)[0];
  const trimmed = raw.replace(/;\s*$/, "");
  const data = JSON.parse(trimmed);
  const props = data?.legacyProps?.searchAppProps?.searchPageProps ?? {};
  totalResults = props?.paginationInfo?.totalResults ?? 0;
  for (const item of props?.mainContentComponentsListProps ?? []) {
    if (item?.bizId && item?.searchResultBusiness != null) searchData.push(item);
  }
  return { search_data: searchData, total_results: totalResults };
}

// ---------------- scrape functions ----------------

export async function scrapePages(urls) {
  const out = [];
  for (const url of urls) {
    const html = await fetchRenderedHtml(url, "h1");
    out.push(parsePage(html));
  }
  return out;
}

async function requestReviewsApi(url, startIndex, businessId) {
  const paginationData = JSON.stringify({ version: 1, type: "offset", offset: startIndex });
  const after = Buffer.from(paginationData, "utf-8").toString("base64");
  const payload = JSON.stringify([
    {
      operationName: "GetBusinessReviewFeed",
      variables: {
        encBizId: businessId,
        reviewsPerPage: 10,
        selectedReviewEncId: "",
        hasSelectedReview: false,
        sortBy: "DATE_DESC",
        languageCode: "en",
        ratings: [5, 4, 3, 2, 1],
        isSearching: false,
        after,
        isTranslating: false,
        translateLanguageCode: "en",
        reactionsSourceFlow: "businessPageReviewSection",
        minConfidenceLevel: "HIGH_CONFIDENCE",
        highlightType: "",
        highlightIdentifier: "",
        isHighlighting: false,
      },
      extensions: {
        operationType: "query",
        documentId: "ef51f33d1b0eccc958dddbf6cde15739c48b34637a00ebe316441031d4bf7681",
      },
    },
  ]);
  const headers = {
    accept: "*/*",
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "no-cache",
    "content-type": "application/json",
    origin: "https://www.yelp.com",
    referer: url,
    "x-apollo-operation-name": "GetBusinessReviewFeed",
  };
  return await postJson("https://www.yelp.com/gql/batch", payload, headers);
}

export async function scrapeReviews(url, maxReviews = null) {
  const businessHtml = await fetchRenderedHtml(url, 'meta[name="yelp-biz-id"]');
  const businessId = parseBusinessId(businessHtml);
  if (!businessId) return [];

  const first = await requestReviewsApi(url, 1, businessId);
  const firstData = parseReviewData(first);
  const reviews = firstData.reviews;
  let total = firstData.total_reviews;
  if (maxReviews && maxReviews < total) total = maxReviews;

  for (let offset = 11; offset < total; offset += 10) {
    try {
      const resp = await requestReviewsApi(url, offset, businessId);
      reviews.push(...parseReviewData(resp).reviews);
    } catch (e) {
      // continue
    }
  }
  return reviews;
}

function makeSearchUrl(keyword, location, offset) {
  const params = new URLSearchParams({ find_desc: keyword, find_loc: location, start: String(offset) });
  return `https://www.yelp.com/search?${params.toString()}`;
}

export async function scrapeSearch(keyword, location, maxPages = null) {
  const firstHtml = await fetchRenderedHtml(
    makeSearchUrl(keyword, location, 0),
    "script[data-id='react-root-props']",
  );
  const data = parseSearch(firstHtml);
  const searchData = data.search_data;
  const totalResults = data.total_results;
  let totalPages = Math.max(1, Math.ceil(totalResults / 10));
  if (maxPages && maxPages < totalPages) totalPages = maxPages;

  for (let offset = 10; offset < totalPages * 10; offset += 10) {
    try {
      const html = await fetchRenderedHtml(
        makeSearchUrl(keyword, location, offset),
        "script[data-id='react-root-props']",
      );
      searchData.push(...parseSearch(html).search_data);
    } catch (e) {
      // continue
    }
  }
  return searchData;
}
