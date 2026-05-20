// Idealista scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// function names and emitted field names match verbatim.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const PROXY_COUNTRY = "ES";
const DEFAULT_SESSION_TTL = 240;
const HOME = "https://www.idealista.com/";

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

// Idealista is fronted by DataDome — cold proxy IPs land on a captcha
// interstitial. Warming up at the homepage (and accepting Spanish locale)
// reliably gets a session cookie before we visit the target.
async function fetchRenderedHtml(url, readySelector, { proxyCountry = PROXY_COUNTRY, retries = 2, warmup = true } = {}) {
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
      await page.setExtraHTTPHeaders({ "accept-language": "es-ES,es;q=0.9,en;q=0.5" });
      if (warmup) {
        try {
          await page.goto(HOME, { waitUntil: "domcontentloaded", timeout: 30000 });
          await new Promise((r) => setTimeout(r, 3000));
        } catch (_) {}
      }
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000, referer: HOME });
      try {
        await page.waitForSelector(readySelector, { timeout: 20000 });
      } catch (_) {
        // non-fatal
      }
      const html = await page.content();
      // Detect a DataDome interstitial — these are tiny (a few hundred bytes)
      // and embed `geo.captcha-delivery.com` or `DataDome Device Check`.
      const isCaptcha =
        html.length < 5000 &&
        /captcha-delivery\.com|DataDome Device Check|geo\.captcha-delivery/i.test(html);
      if (isCaptcha) {
        lastError = new Error("DataDome captcha interstitial");
      } else if (html) {
        return html;
      } else {
        lastError = new Error("empty HTML");
      }
    } catch (e) {
      lastError = e;
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
  }
  throw new Error(`giving up after ${retries + 1} attempts: ${lastError?.message}`);
}

function absoluteUrl(base, rel) {
  try { return new URL(rel, base).toString(); } catch (_) { return rel; }
}

// ---------------- parsers ----------------

export function parseProperty(html, url) {
  const $ = cheerio.load(html);
  const txt = (sel) => $(sel).first().text().trim();

  const priceRaw = txt(".info-data-price span").replace(/,/g, "");
  const price = parseInt(priceRaw, 10) || 0;
  const currency = txt(".info-data-price");

  const descriptionParts = [];
  $("div.comment").find("*").contents().each((_, el) => {
    if (el.type === "text" && el.data) descriptionParts.push(el.data);
  });

  const updatedText = $("p.stats-text").filter((_, el) => $(el).text().includes("updated on")).first().text() || "";
  const updated = updatedText.includes(" on ") ? updatedText.split(" on ").pop() : "";

  const features = {};
  $(".details-property-h2").each((_, el) => {
    const label = $(el).text();
    const items = [];
    $(el).nextAll().first().find("li").each((__, li) => items.push($(li).text().trim()));
    features[label] = items;
  });

  const images = {};
  const plans = [];
  const m = /fullScreenGalleryPics\s*:\s*(\[.+?\]),/s.exec(html);
  if (m) {
    try {
      const normalised = m[1].replace(/(\w+?):([^/])/g, '"$1":$2');
      const arr = JSON.parse(normalised);
      for (const img of arr) {
        const full = absoluteUrl(url, img.imageUrl || "");
        if (img.isPlan) plans.push(full);
        else {
          const tag = img.tag || "";
          (images[tag] = images[tag] || []).push(full);
        }
      }
    } catch (_) {}
  }

  return {
    url,
    title: txt("h1 .main-info__title-main"),
    location: txt(".main-info__title-minor"),
    currency,
    price,
    description: descriptionParts.join("").trim(),
    updated,
    features,
    images,
    plans,
  };
}

export function parseSearch(html, baseUrl) {
  const $ = cheerio.load(html);
  const out = [];
  $("article.item").each((_, el) => {
    const card = $(el);
    const linkRel = card.find(".item-link").attr("href") || "";
    const title = (card.find(".item-link").attr("title") || card.find(".item-link").text() || "").trim();
    const priceText = card.find(".item-price").first().text().trim();
    let price = 0;
    let currency = "";
    const m = /([\d.,]+)\s*([^\d\s]+)/.exec(priceText);
    if (m) {
      price = parseInt(m[1].replace(/[.,]/g, ""), 10) || 0;
      currency = m[2];
    }
    const details = [];
    card.find(".item-detail-char .item-detail").each((__, d) => {
      const t = $(d).text().trim();
      if (t) details.push(t);
    });
    const description = card.find(".item-description").text().trim();
    const tags = [];
    card.find(".item-tags").children().each((__, t) => {
      const v = $(t).text().trim();
      if (v) tags.push(v);
    });
    const listingCompany = card.find(".item-branding .logo-branding").attr("title") || null;
    const lcUrlRel = card.find(".item-branding a").attr("href");
    const picture = card.find(".item-multimedia img").attr("src") || null;
    out.push({
      title,
      link: absoluteUrl(baseUrl, linkRel),
      picture,
      price,
      currency,
      parking_included: /parking/i.test(priceText) || card.find(".item-parking").length > 0,
      details,
      description,
      tags,
      listing_company: listingCompany,
      listing_company_url: lcUrlRel ? absoluteUrl(baseUrl, lcUrlRel) : null,
    });
  });
  return out;
}

export function parseProvince(html, baseUrl) {
  const $ = cheerio.load(html);
  const urls = [];
  $("#location_list li > a").each((_, el) => {
    const href = $(el).attr("href");
    if (href) urls.push(absoluteUrl(baseUrl, href));
  });
  return urls;
}

// ---------------- scrape functions ----------------

export async function scrapeProperties(urls) {
  const out = [];
  for (const u of urls) {
    const html = await fetchRenderedHtml(u, "h1 .main-info__title-main");
    out.push(parseProperty(html, u));
  }
  return out;
}

export async function scrapeSearch(url, maxScrapePages = null) {
  const first = await fetchRenderedHtml(url, "article.item");
  const results = parseSearch(first, url);

  const $ = cheerio.load(first);
  let totalPages = 1;
  $(".pagination li a").each((_, el) => {
    const href = $(el).attr("href") || "";
    const m = /pagina-(\d+)/.exec(href);
    if (m) totalPages = Math.max(totalPages, parseInt(m[1], 10));
  });
  if (maxScrapePages) totalPages = Math.min(totalPages, maxScrapePages);

  for (let page = 2; page <= totalPages; page++) {
    const pageUrl = url.replace(/\/$/, "") + `/pagina-${page}.htm`;
    const html = await fetchRenderedHtml(pageUrl, "article.item");
    results.push(...parseSearch(html, url));
  }
  return results;
}

export async function scrapeProvinces(urls) {
  const out = [];
  for (const u of urls) {
    const html = await fetchRenderedHtml(u, "#location_list");
    out.push(...parseProvince(html, u));
  }
  return out;
}
