// AliExpress scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// the function names and emitted field names match verbatim.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 180;

// Localization cookie. cookie`.
const LOCALE_COOKIE = "aep_usuc_f=site=glo&province=&city=&c_tp=USD&region=US&b_locale=en_US&ae_u_p_s=2";

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

function parseLocaleCookie() {
  const out = [];
  for (const pair of LOCALE_COOKIE.split(";")) {
    const i = pair.indexOf("=");
    if (i === -1) continue;
    out.push({
      name: pair.slice(0, i).trim(),
      value: pair.slice(i + 1).trim(),
      domain: ".aliexpress.com",
      path: "/",
    });
  }
  return out;
}

async function fetchRenderedHtml(url, readySelector, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 1, autoScroll = false } = {}) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const session = await client().browser.create({ proxyCountry, sessionTTL: DEFAULT_SESSION_TTL });
    let browser;
    try {
      browser = await puppeteer.connect({ browserWSEndpoint: session.browserWSEndpoint });
      try { await browser.setCookie(...parseLocaleCookie()); } catch (_) {}
      const page = await browser.newPage();
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
      if (readySelector) {
        try { await page.waitForSelector(readySelector, { timeout: 20000 }); } catch (_) {}
      }
      if (autoScroll) {
        try {
          await page.evaluate(async () => {
            await new Promise((r) => {
              let y = 0;
              const i = setInterval(() => {
                window.scrollBy(0, 400);
                y += 400;
                if (y >= document.body.scrollHeight) { clearInterval(i); r(); }
              }, 100);
            });
          });
          await new Promise((r) => setTimeout(r, 1500));
        } catch (_) {}
      }
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

async function fetchJson(url) {
  const html = await fetchRenderedHtml(url, "pre");
  const $ = cheerio.load(html);
  const raw = $("pre").first().text() || html;
  return JSON.parse(raw);
}

// ---------------- search ----------------

export function addOrReplaceUrlParameters(url, params) {
  const u = new URL(url);
  for (const [k, v] of Object.entries(params)) u.searchParams.set(k, String(v));
  return u.toString();
}

export function extractSearch(html) {
  const $ = cheerio.load(html);
  let script = null;
  $("script").each((_, el) => {
    const t = $(el).html() || "";
    if (t.includes("_init_data_=") && !script) script = t;
  });
  if (!script) return {};
  const match = script.match(/_init_data_\s*=\s*\{\s*data:\s*(\{.+\}) \}/s);
  if (!match) return {};
  try {
    const data = JSON.parse(match[1]);
    return data?.data?.root?.fields ?? {};
  } catch {
    return {};
  }
}

export function parseSearch(html) {
  const data = extractSearch(html);
  return data?.mods?.itemList?.content ?? [];
}

export async function scrapeSearch(url, maxPages = 60) {
  const firstHtml = await fetchRenderedHtml(url, "div[class*='card--gallery']");
  const firstData = extractSearch(firstHtml);
  const pageSize = firstData?.pageInfo?.pageSize ?? 60;
  const totalResults = firstData?.pageInfo?.totalResults ?? 0;
  let totalPages = pageSize ? Math.ceil(totalResults / pageSize) : 1;
  if (totalPages > maxPages) totalPages = maxPages;

  const out = parseSearch(firstHtml);
  for (let page = 2; page <= totalPages; page++) {
    const pageUrl = addOrReplaceUrlParameters(url, { page });
    const pageHtml = await fetchRenderedHtml(pageUrl, "div[class*='card--gallery']");
    out.push(...parseSearch(pageHtml));
  }
  return out;
}

// ---------------- product ----------------

function parseCount(text) {
  if (!text) return 0;
  let t = text.replace(" sold", "").replace(" available", "").replace(/,/g, "").replace(/\+/g, "").trim();
  t = t ? t.split(/\s+/)[0] : "";
  if (!t) return 0;
  const n = parseFloat(t);
  return Number.isFinite(n) ? Math.round(n) : 0;
}

export function parseProduct(html, url) {
  const $ = cheerio.load(html);
  const reviewsText = $("a[class*='reviewer--reviews']").first().text() || null;
  const rateNodes = $("div[class*='rating--wrap'] > div").length;
  const soldText = $("a[class*='reviewer--sliderItem']")
    .find("span")
    .filter((_, e) => $(e).text().includes("sold"))
    .first()
    .text() || null;
  const availableText = $("div[class*='quantity--info'] div span").first().text() || null;

  const productIdStr = url.includes("item/") ? url.split("item/").pop().split(".")[0] : "";
  const productIdInt = parseInt(productIdStr, 10);
  const productId = Number.isFinite(productIdInt) ? productIdInt : productIdStr;

  const info = {
    name: $("h1[data-pl]").first().text() || null,
    productId,
    link: url,
    media: $("div[class*='slider--img'] img").map((_, e) => $(e).attr("src")).get().filter(Boolean),
    rate: rateNodes || null,
    reviews: reviewsText ? parseInt(reviewsText.replace(" Reviews", ""), 10) : null,
    soldCount: parseCount(soldText),
    availableCount: parseCount(availableText),
  };

  const price = $("span[class*='price-default--current']").first().text() || null;
  const originalPrice = $("span[class*='price-default--original']").first().text() || null;
  const discount = $("span[class*='price--discount']").first().text() || null;
  const pricing = {
    priceCurrency: "USD $",
    price: price ? parseFloat(price.split("$").pop()) : null,
    originalPrice: originalPrice ? parseFloat(originalPrice.split("$").pop()) : "No discount",
    discount: discount ?? "No discount",
  };
  const delivery = $(".dynamic-shipping strong").eq(1).text() || null;

  const specifications = $("div[class*='specification--prop']").map((_, el) => {
    const $el = $(el);
    return {
      name: $el.find("div[class*='specification--title'] span").first().text() || null,
      value: $el.find("div[class*='specification--desc'] span").first().text() || null,
    };
  }).get();

  const faqs = $("div.ask-list ul li").map((_, el) => {
    const $el = $(el);
    return {
      question: $el.find("p.ask-content span").first().text() || null,
      answer: $el.find("ul.answer-box li p").first().text() || null,
    };
  }).get();

  return { info, pricing, specifications, delivery, faqs };
}

export async function scrapeProduct(url) {
  const html = await fetchRenderedHtml(url, "h1[data-pl]", { autoScroll: true });
  return parseProduct(html, url);
}

// ---------------- product reviews (JSON API) ----------------

export function parseReviewPage(payload) {
  const data = payload?.data ?? {};
  return {
    max_pages: data.totalPage ?? 1,
    reviews: data.evaViewList ?? [],
    evaluation_stats: data.productEvaluationStatistic ?? {},
  };
}

export async function scrapeProductReviews(productId, maxScrapePages = null) {
  const urlForPage = (page) =>
    `https://feedback.aliexpress.com/pc/searchEvaluation.do?productId=${productId}&lang=en_US&country=US&page=${page}&pageSize=10&filter=all&sort=complex_default`;

  const firstPayload = await fetchJson(urlForPage(1));
  const data = parseReviewPage(firstPayload);
  let maxPages = data.max_pages;
  if (maxScrapePages && maxScrapePages < maxPages) maxPages = maxScrapePages;

  for (let page = 2; page <= maxPages; page++) {
    const p = await fetchJson(urlForPage(page));
    data.reviews.push(...parseReviewPage(p).reviews);
  }
  delete data.max_pages;
  return data;
}

// ---------------- category ----------------

export function parseCategoryPage(html) {
  const $ = cheerio.load(html);
  let script = null;
  $("script").each((_, el) => {
    const t = $(el).html() || "";
    if (t.includes("_init_data_=") && !script) script = t;
  });
  if (!script) return { product_data: [], total_pages: 1 };
  const match = script.match(/_init_data_\s*=\s*\{\s*data:\s*(\{.+\}) \}/s);
  if (!match) return { product_data: [], total_pages: 1 };
  try {
    const jsonData = JSON.parse(match[1]).data.root.fields;
    const productData = jsonData?.mods?.itemList?.content ?? [];
    const totalResults = jsonData?.pageInfo?.totalResults ?? 0;
    const pageSize = jsonData?.pageInfo?.pageSize ?? 60;
    const totalPages = pageSize ? Math.ceil(totalResults / pageSize) : 1;
    return { product_data: productData, total_pages: totalPages };
  } catch {
    return { product_data: [], total_pages: 1 };
  }
}

export async function findAliexpressProducts(url, maxPages = null) {
  const firstHtml = await fetchRenderedHtml(url, "body");
  const first = parseCategoryPage(firstHtml);
  const out = [...first.product_data];
  let pages = Math.max(1, first.total_pages - 1);
  if (maxPages !== null) pages = maxPages;
  for (let page = 2; page <= pages; page++) {
    const pageHtml = await fetchRenderedHtml(`${url}?page=${page}`, "body");
    out.push(...parseCategoryPage(pageHtml).product_data);
  }
  return out;
}
