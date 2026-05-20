// Amazon scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
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

function addOrReplaceUrlParameters(url, params) {
  const u = new URL(url);
  for (const [k, v] of Object.entries(params)) u.searchParams.set(k, String(v));
  return u.toString();
}

async function fetchRenderedHtml(url, readySelector, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 1 } = {}) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const session = await client().browser.create({
      proxyCountry,
      sessionTTL: DEFAULT_SESSION_TTL,
    });
    let browser;
    try {
      browser = await puppeteer.connect({ browserWSEndpoint: session.browserWSEndpoint });
      const page = await browser.newPage();
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
      // Handle "Continue shopping" interstitial
      try {
        const handle = await page.$x("//button[contains(., 'Continue shopping')]");
        if (handle?.[0]) {
          await handle[0].click();
          await page.waitForNavigation({ waitUntil: "domcontentloaded", timeout: 15000 }).catch(() => {});
        }
      } catch (_) {}
      if (readySelector) {
        try {
          await page.waitForSelector(readySelector, { timeout: 15000 });
        } catch (_) {}
      }
      const html = await page.content();
      if (html && !html.slice(0, 5000).includes("Continue shopping")) return html;
      lastError = new Error("interstitial / empty HTML");
    } catch (e) {
      lastError = e;
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
  }
  throw new Error(`giving up after ${retries + 1} attempts: ${lastError?.message}`);
}

// ---------------- search ----------------

export function parseSearch(html, baseUrl) {
  const $ = cheerio.load(html);
  const previews = [];
  $("div.s-result-item[data-component-type=s-search-result]").each((_, el) => {
    const box = $(el);
    const href = box.find("div > a").first().attr("href");
    if (!href) return;
    let url;
    try { url = new URL(href, baseUrl).toString().split("?")[0]; }
    catch { return; }
    if (url.includes("/slredirect/")) return;

    const ratingAria = box.find("div[data-cy='reviews-block'] a[aria-label*='out of']").attr("aria-label") || "";
    const ratingMatch = ratingAria.match(/(\d+\.?\d*) out/);
    const ratingCountAria = box.find("div[data-cy='reviews-block'] a[aria-label*='ratings']").attr("aria-label");

    previews.push({
      url,
      title: box.find("div > a > h2").attr("aria-label") ?? null,
      price: box.find(".a-price[data-a-size=xl] .a-offscreen").first().text() || null,
      real_price: box.find("div[data-cy='secondary-offer-recipe'] span.a-color-base").filter((__, e) => $(e).text().includes("$")).first().text() || null,
      rating: ratingMatch ? parseFloat(ratingMatch[1]) : null,
      rating_count: ratingCountAria ? parseInt(ratingCountAria.replace(/,/g, "").replace(" ratings", ""), 10) : null,
    });
  });
  return previews;
}

export async function scrapeSearch(url, maxPages = null) {
  const firstHtml = await fetchRenderedHtml(url, "div.s-result-item[data-component-type=s-search-result]");
  const results = parseSearch(firstHtml, url);

  const $ = cheerio.load(firstHtml);
  const pagingMeta = $("[cel_widget_id='UPPER-RESULT_INFO_BAR-0'] span").text() || "";
  let totalPages = 1;
  const totalMatch = pagingMeta.match(/(?:over\s+)?([\d,]+)\s+results/);
  const perMatch = pagingMeta.match(/\d+-(\d+)/);
  if (totalMatch && perMatch) {
    const totalResults = parseInt(totalMatch[1].replace(/,/g, ""), 10);
    const perPage = parseInt(perMatch[1], 10);
    totalPages = Math.ceil(totalResults / perPage);
  }
  if (maxPages && totalPages > maxPages) totalPages = maxPages;

  for (let page = 2; page <= totalPages; page++) {
    const pageUrl = addOrReplaceUrlParameters(url, { page });
    const pageHtml = await fetchRenderedHtml(pageUrl, "div.s-result-item[data-component-type=s-search-result]");
    results.push(...parseSearch(pageHtml, pageUrl));
  }
  return results;
}

// ---------------- reviews ----------------

export function parseReviews(html) {
  const $ = cheerio.load(html);
  const out = [];
  $("#cm-cr-dp-review-list li.review").each((_, el) => {
    const box = $(el);
    const ratingText = box.find("[data-hook=review-star-rating]").text();
    const ratingMatch = ratingText.match(/(\d+\.?\d*) out/);
    out.push({
      text: box.find("[data-hook=review-collapsed]").text().trim(),
      title: box.find("[data-hook=review-title] > span").first().text() || null,
      location_and_date: box.find("span[data-hook=review-date]").first().text() || null,
      verified: !!box.find("span[data-hook=avp-badge]").text(),
      rating: ratingMatch ? parseFloat(ratingMatch[1]) : null,
    });
  });
  return out;
}

export async function scrapeReviews(url) {
  const html = await fetchRenderedHtml(url, "#cm-cr-dp-review-list");
  return parseReviews(html);
}

// ---------------- product ----------------

export function parseProduct(html) {
  let images = [];
  const colorMatch = html.match(/colorImages':.*'initial':\s*(\[.+?\])\},\n/);
  if (colorMatch) {
    try { images = JSON.parse(colorMatch[1]).map((img) => img.large); } catch (_) {}
  }
  const galleryMatch = html.match(/imageGalleryData'\s*:\s*(\[.+\]),\n/);
  if (galleryMatch) {
    try { images = JSON.parse(galleryMatch[1]).map((img) => img.mainUrl); } catch (_) {}
  }

  const $ = cheerio.load(html);
  const parsed = {
    name: ($("#productTitle").text() || "").trim(),
    asin: ($("input[name=ASIN]").attr("value") || "").trim(),
    style: $("[id^=inline-twister-expanded-dimension-text]").text().trim(),
    description: $("#productDescription p span").map((_, el) => $(el).text()).get().join("\n").trim(),
    stars: $("i[data-hook=average-star-rating]").text().trim(),
    rating_count: $("span[data-hook=total-review-count]").text().trim(),
    features: $("#feature-bullets li").map((_, el) => $(el).text().trim()).get().filter(Boolean),
    images,
    info_table: {},
  };

  const infoTable = {};
  $("#productDetails_detailBullets_sections1 tr").each((_, row) => {
    const label = $(row).find("th").first().text().trim();
    let value = $(row).find("td").first().text().trim();
    if (!value) value = $(row).find("td span").first().text().trim();
    if (label) infoTable[label] = value;
  });
  infoTable["Customer Reviews"] = $("td:has(#averageCustomerReviews) span.a-icon-alt").first().text() || null;
  const rank = $("tr:has(th:contains('Best Sellers Rank')) td").text().trim().replace(/\s+/g, " ");
  infoTable["Best Sellers Rank"] = rank;
  parsed.info_table = infoTable;
  return parsed;
}

export async function scrapeProduct(url) {
  url = url.split("/ref=")[0];
  const asin = url.split("/dp/")[1]?.replace(/\/$/, "") ?? "";
  const html = await fetchRenderedHtml(url, "#productDetails_detailBullets_sections1 tr");
  const variants = [parseProduct(html)];

  const variationMatch = html.match(/dimensionValuesDisplayData"\s*:\s*(\{.+?\}),\n/);
  if (variationMatch) {
    try {
      const variantAsins = Object.keys(JSON.parse(variationMatch[1])).filter((a) => a !== asin);
      for (const va of variantAsins) {
        const variantUrl = `https://www.amazon.com/dp/${va}`;
        const vHtml = await fetchRenderedHtml(variantUrl, "#productDetails_detailBullets_sections1 tr");
        variants.push(parseProduct(vHtml));
      }
    } catch (_) {}
  }
  return variants;
}
