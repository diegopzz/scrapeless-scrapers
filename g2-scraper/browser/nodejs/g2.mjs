// G2 scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// the function names and emitted field shapes match verbatim, so downstream code
// can import { Scrapeless } from "@scrapeless-ai/sdk";
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

async function fetchRenderedHtml(url, readySelector, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 1, autoScroll = false } = {}) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const { browserWSEndpoint } = await client().browser.create({ proxyCountry, sessionTTL: DEFAULT_SESSION_TTL });
    let browser;
    try {
      browser = await puppeteer.connect({ browserWSEndpoint });
      const page = await browser.newPage();
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
      if (readySelector) {
        try { await page.waitForSelector(readySelector, { timeout: 15000 }); } catch (_) {}
      }
      if (autoScroll) {
        try {
          await page.evaluate(async () => {
            await new Promise((r) => {
              let y = 0;
              const t = setInterval(() => {
                window.scrollBy(0, 400);
                y += 400;
                if (y >= document.body.scrollHeight) { clearInterval(t); r(); }
              }, 100);
            });
          });
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

// ---------------- parsers ----------------

export function parseSearchPage(html, baseUrl) {
  const $ = cheerio.load(html);
  const totalText = $("div:contains('Products')").next("div").text();
  const tm = totalText.match(/\((\d+)\)/);
  const totalResults = tm ? parseInt(tm[1], 10) : 0;
  const pageSize = 20;
  const totalPages = totalResults ? Math.ceil(totalResults / pageSize) : 0;

  const data = [];
  $("section").each((_, section) => {
    const $s = $(section);
    if (!$s.find("a[href*='/products/']").length) return;
    const name = $s.find("div[class*='elv-text-lg']").first().text();
    if (!name) return;
    const relativeLink = $s.find("div[class*='elv-text-lg']").first().parent("a").attr("href");
    const link = relativeLink ? new URL(relativeLink, baseUrl).toString() : null;
    const image = $s.find("img[alt='Product Avatar Image']").attr("src") ?? null;
    const rawRate = $s.find("label:contains('/5')").first().text();
    const rate = rawRate ? parseFloat(rawRate.split("/")[0]) : null;
    const rawReviews = $s
      .find("a[href*='#reviews'] label")
      .filter((__, l) => !$(l).text().includes("/5"))
      .first()
      .text();
    const reviewsNumber = rawReviews ? parseInt(rawReviews.replace(/[()]/g, ""), 10) : null;
    const descParts = $s
      .find("div:has(> div:contains('Product Description')) p")
      .map((__, p) => $(p).text())
      .get();
    const description = descParts.length ? descParts.join("").trim() : null;
    const categories = $s
      .find("aside div[class*='elv-whitespace-nowrap']")
      .map((__, c) => $(c).text().trim())
      .get();
    data.push({ name: name.trim(), link, image, rate, reviewsNumber, description, categories });
  });

  return { search_data: data, total_pages: totalPages };
}

export function parseReviewPage(html) {
  const $ = cheerio.load(html);
  const totalReviewsText = $("a[href*='/reviews#reviews']:contains('reviews')").first().text();
  let totalPages = 0;
  if (totalReviewsText) {
    const parts = totalReviewsText.trim().split(/\s+/);
    const totalReviews = parseInt(parts[2] ?? "0", 10) || 0;
    totalPages = totalReviews ? Math.ceil(totalReviews / 10) : 0;
  }

  const data = [];
  $("article").each((_, art) => {
    const $r = $(art);
    if (!$r.find("div[itemprop='reviewBody']").length) return;
    const authorName = $r.find("div[itemprop='author'] meta[itemprop='name']").attr("content") ?? null;
    const authorProfile = $r.find("div[class*='avatar']").parent("a").attr("href") ?? null;
    const authorDetails = $r
      .find("div:has(> div[itemprop='author']) div[class*='elv-text-subtle']")
      .map((__, d) => $(d).text())
      .get();
    const authorPosition = authorDetails[0] ?? null;
    const authorCompanySize = authorDetails.find((d) => d.includes("emp.")) ?? null;

    const reviewTags = $r
      .find("div[class*='gap-3'][class*='flex-wrap'] label")
      .map((__, l) => $(l).text().trim())
      .get()
      .filter(Boolean);
    const reviewDate = $r.find("meta[itemprop='datePublished']").attr("content") ?? null;
    const reviewRateRaw = $r.find("span[itemprop='reviewRating'] meta[itemprop='ratingValue']").attr("content");
    const reviewRate = reviewRateRaw ? parseFloat(reviewRateRaw) : null;
    const reviewTitleRaw = $r.find("div[itemprop='name']").text();
    const reviewTitle = reviewTitleRaw ? reviewTitleRaw.replace(/"/g, "").trim() : null;

    const likesParts = $r
      .find("section:has(> div:contains('What do you like best')) p")
      .map((__, p) => $(p).text())
      .get();
    const reviewLikes = likesParts.join("").replace("Review collected by and hosted on G2.com.", "").trim();
    const dislikesParts = $r
      .find("section:has(> div:contains('What do you dislike')) p")
      .map((__, p) => $(p).text())
      .get();
    const reviewDislikes = dislikesParts.join("").replace("Review collected by and hosted on G2.com.", "").trim();

    data.push({
      author: {
        authorName: authorName ? authorName.trim() : null,
        authorProfile,
        authorPosition: authorPosition ? authorPosition.trim() : null,
        authorCompanySize: authorCompanySize ? authorCompanySize.trim() : null,
      },
      review: {
        reviewTags,
        // the upstream reference key sic: reviewData
        reviewData: reviewDate,
        reviewRate,
        reviewTitle,
        reviewLikes,
        reviewDislikes,
      },
    });
  });
  return { total_pages: totalPages, reviews_data: data };
}

export function parseAlternatives(html) {
  const $ = cheerio.load(html);
  const data = [];
  $("div[data-ordered-events-item='products']").each((_, el) => {
    const $a = $(el);
    if ($a.find("span").filter((__, s) => $(s).text() === "Sponsored").length) return;
    const name = $a.find("div[class*='elv-text-lg'][class*='elv-font-bold']").first().text();
    let link = $a.find("a[href*='/products/']").attr("href") ?? null;
    if (link && !link.startsWith("http")) link = `https://www.g2.com${link}`;
    const ranking = $a.find("meta[itemprop='position']").attr("content") ?? null;
    const ratingText = $a.find("label[class*='elv-font-semibold']").first().text();
    const reviewsText = $a.find("label[class*='elv-font-light']").first().text();
    let numberOfReviews = null;
    if (reviewsText) {
      const clean = reviewsText.replace(/[()]/g, "").replace(/,/g, "");
      const n = parseInt(clean, 10);
      if (!Number.isNaN(n)) numberOfReviews = n;
    }
    let rate = null;
    if (ratingText) {
      const f = parseFloat(ratingText.split("/")[0]);
      if (!Number.isNaN(f)) rate = f;
    }
    const description = $a.find("p[class*='elv-text-default']").first().text() || null;
    if (name) {
      data.push({
        name: name.trim(),
        link,
        ranking: ranking ? parseInt(ranking, 10) : null,
        numberOfReviews,
        rate,
        description: description ? description.trim() : null,
      });
    }
  });
  return data;
}

// ---------------- scrape functions ----------------

export async function scrapeSearch(url, maxScrapePages = null) {
  const firstHtml = await fetchRenderedHtml(url, "section a[href*='/products/']");
  const data = parseSearchPage(firstHtml, url);
  const searchData = data.search_data;
  let totalPages = data.total_pages;
  if (maxScrapePages && maxScrapePages < totalPages) totalPages = maxScrapePages;
  for (let page = 2; page <= totalPages; page++) {
    const pageUrl = `${url}&page=${page}`;
    try {
      const html = await fetchRenderedHtml(pageUrl, "section a[href*='/products/']");
      searchData.push(...parseSearchPage(html, pageUrl).search_data);
    } catch (_) {}
  }
  return searchData;
}

export async function scrapeReviews(url, maxReviewPages = null) {
  const firstHtml = await fetchRenderedHtml(url, "section#reviews article", { autoScroll: true });
  const data = parseReviewPage(firstHtml);
  const reviewsData = data.reviews_data;
  let totalPages = data.total_pages;
  if (maxReviewPages && maxReviewPages < totalPages) totalPages = maxReviewPages;
  for (let page = 2; page <= totalPages; page++) {
    const pageUrl = `${url}?page=${page}`;
    try {
      const html = await fetchRenderedHtml(pageUrl, "section#reviews article", { autoScroll: true });
      reviewsData.push(...parseReviewPage(html).reviews_data);
    } catch (_) {}
  }
  return reviewsData;
}

export async function scrapeAlternatives(product, alternatives = "") {
  const url = `https://www.g2.com/products/${product}/competitors/alternatives/${alternatives}`;
  try {
    const html = await fetchRenderedHtml(url, "div[data-ordered-events-item='products']");
    return parseAlternatives(html);
  } catch (_) {
    return [];
  }
}
