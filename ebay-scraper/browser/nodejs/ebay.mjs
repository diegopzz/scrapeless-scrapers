// eBay scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// the function names and emitted field names match verbatim.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 240;
const HOME = "https://www.ebay.com/";

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

// eBay is fronted by Akamai Bot Manager — direct navigation to product/search
// URLs returns an "Access Denied" page. Warming up each session at the homepage
// lets Akamai issue a session cookie before we navigate to the target.
async function fetchRenderedHtml(url, readySelector, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 2 } = {}) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const session = await client().browser.create({ proxyCountry, sessionTTL: DEFAULT_SESSION_TTL });
    let browser;
    try {
      browser = await puppeteer.connect({ browserWSEndpoint: session.browserWSEndpoint });
      const page = await browser.newPage();
      await page.setExtraHTTPHeaders({ "accept-language": "en-US,en;q=0.9" });
      await page.goto(HOME, { waitUntil: "domcontentloaded", timeout: 45000 });
      await new Promise((r) => setTimeout(r, 3500));
      try { await page.evaluate(() => window.scrollBy(0, 600)); } catch (_) {}
      await new Promise((r) => setTimeout(r, 1500));
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000, referer: HOME });
      if (readySelector) {
        try { await page.waitForSelector(readySelector, { timeout: 20000 }); } catch (_) {}
      }
      const html = await page.content();
      const title = await page.title().catch(() => "");
      const blocked =
        title === "Access Denied" ||
        /\bAccess Denied\b/.test(html.slice(0, 2000));
      if (blocked) {
        lastError = new Error("blocked by Akamai (Access Denied)");
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

// ---------------- variants (parse MSKU JS blob) ----------------

function* findJsonObjects(text) {
  let pos = 0;
  while (pos < text.length) {
    const start = text.indexOf("{", pos);
    if (start === -1) return;
    let depth = 0;
    let end = -1;
    let inStr = false;
    let strCh = "";
    let esc = false;
    for (let i = start; i < text.length; i++) {
      const ch = text[i];
      if (inStr) {
        if (esc) { esc = false; continue; }
        if (ch === "\\") { esc = true; continue; }
        if (ch === strCh) { inStr = false; }
        continue;
      }
      if (ch === '"' || ch === "'") { inStr = true; strCh = ch; continue; }
      if (ch === "{") depth++;
      else if (ch === "}") {
        depth--;
        if (depth === 0) { end = i + 1; break; }
      }
    }
    if (end === -1) return;
    try {
      yield JSON.parse(text.slice(start, end));
      pos = end;
    } catch {
      pos = start + 1;
    }
  }
}

function nestedLookup(key, doc) {
  const out = [];
  const walk = (d) => {
    if (d && typeof d === "object") {
      if (Array.isArray(d)) {
        d.forEach(walk);
      } else {
        for (const [k, v] of Object.entries(d)) {
          if (k === key) out.push(v);
          walk(v);
        }
      }
    }
  };
  walk(doc);
  return out;
}

export function parseVariants(html) {
  const $ = cheerio.load(html);
  let script = null;
  $("script").each((_, el) => {
    const t = $(el).html() || "";
    if (t.includes("MSKU") && !script) script = t;
  });
  if (!script) return [];
  const allData = [...findJsonObjects(script)];
  const mskuData = nestedLookup("MSKU", allData);
  if (mskuData.length === 0) return [];
  const data = mskuData[0];

  const selectionNames = {};
  for (const menu of data.selectMenus ?? []) {
    for (const id_ of menu.menuItemValueIds ?? []) {
      selectionNames[id_] = menu.displayLabel;
    }
  }
  const selections = [];
  for (const v of Object.values(data.menuItemMap ?? {})) {
    selections.push({
      name: v.valueName,
      variants: v.matchingVariationIds ?? [],
      label: selectionNames[v.valueId],
    });
  }
  const variantDataLookup = nestedLookup("variationsMap", data);
  if (variantDataLookup.length === 0) return [];
  const variantData = variantDataLookup[0];

  const results = [];
  for (const [id_, variant] of Object.entries(variantData)) {
    const item = { id: id_ };
    for (const sel of selections) {
      if (sel.variants.includes(parseInt(id_, 10))) {
        item[sel.label] = sel.name;
      }
    }
    const priceVal = variant?.binModel?.price?.value ?? {};
    item.price_original = priceVal.convertedFromValue ?? priceVal.value ?? null;
    item.price_original_currency = priceVal.convertedFromCurrency ?? priceVal.currency ?? null;
    item.price_converted = priceVal.value ?? null;
    item.price_converted_currency = priceVal.currency ?? null;
    item.out_of_stock = variant?.quantity?.outOfStock ?? null;
    results.push(item);
  }
  return results;
}

// ---------------- product ----------------

export function parseProduct(html) {
  const $ = cheerio.load(html);
  const item = {};
  item.url = $('link[rel="canonical"]').attr("href") ?? "";
  try { item.id = item.url.split("/itm/")[1].split("?")[0]; }
  catch { item.id = ""; }
  item.price_original = $(".x-price-primary > span").first().text().trim() || null;
  item.price_converted = $(".x-price-approx__price").first().text().trim() || null;
  item.name = $("h1 span").map((_, e) => $(e).text()).get().join("").trim();
  item.seller_name = $("div[class*='info__about-seller'] a span").first().text() || null;
  const sellerHref = $("div[class*='info__about-seller'] a").first().attr("href") || "";
  item.seller_url = sellerHref ? sellerHref.split("?")[0] : null;
  item.photos = $('.ux-image-filmstrip-carousel-item.image img').map((_, e) => $(e).attr("src")).get();
  item.photos.push(...$('.ux-image-carousel-item.image img').map((_, e) => $(e).attr("src")).get());
  item.description_url = $("iframe#desc_ifr").attr("src") || null;

  const features = {};
  $("div.ux-layout-section--features dl.ux-labels-values").each((_, fea) => {
    const label = $(fea).find(".ux-labels-values__labels-content > div > span").map((_, e) => $(e).text()).get().join("").replace(/[:\n ]+$/, "").trim();
    const value = $(fea).find(".ux-labels-values__values-content > div > span").map((_, e) => $(e).text()).get().join("").replace(/[:\n ]+$/, "").trim();
    if (label) features[label] = value;
  });
  item.features = features;
  return item;
}

export async function scrapeProduct(url) {
  const html = await fetchRenderedHtml(url, "h1");
  const product = parseProduct(html);
  product.variants = parseVariants(html);
  return product;
}

// ---------------- search ----------------

function getUrlParam(url, name, def) {
  try { return new URL(url).searchParams.get(name) ?? def; }
  catch { return def; }
}

function updateUrlParam(url, params) {
  const u = new URL(url);
  for (const [k, v] of Object.entries(params)) u.searchParams.set(k, String(v));
  return u.toString();
}

export function parseSearch(html) {
  const $ = cheerio.load(html);
  const previews = [];
  $("ul.srp-results li").each((_, el) => {
    const box = $(el);
    const css = (sel) => box.find(sel).first().text().trim() || null;
    const attr = (sel, a) => box.find(sel).first().attr(a) ?? null;
    const location = box.find("*").filter((__, e) => $(e).text().includes("Located")).first().text() || null;
    const price = css(".s-card__price") || css(".s-item__price");
    const url = attr("a.s-card__link", "href") ?? attr("a.su-link", "href");
    const ratingText = box.find("span").filter((__, e) => $(e).text().includes("positive")).first().text() || "";

    if (!price) return;

    let rating_count = null;
    if (ratingText) {
      const m = ratingText.match(/\(([\d.]+)K?\)/);
      if (m) {
        rating_count = m[0].includes("K)") ? Math.round(parseFloat(m[1]) * 1000) : parseInt(m[1], 10);
      }
    }

    previews.push({
      url: url ? url.split("?")[0] : null,
      title: css(".s-card__title span"),
      price,
      shipping: box.find("*").filter((__, e) => $(e).text().includes("delivery")).first().text() || null,
      location: location ? (location.split("Located in ")[1] ?? null) : null,
      subtitles: css(".s-card__subtitle span"),
      photo: attr("img", "data-src") ?? attr("img", "src"),
      rating: ratingText ? ((ratingText.match(/[\d.]+%/) ?? [null])[0]) : null,
      rating_count,
    });
  });
  return previews;
}

export async function scrapeSearch(url, maxPages = null) {
  const firstHtml = await fetchRenderedHtml(url, "ul.srp-results");
  const results = parseSearch(firstHtml);

  const $ = cheerio.load(firstHtml);
  const totalText = $(".srp-controls__count-heading > span").first().text() || "0";
  const totalResults = parseInt(totalText.replace(/[.,]/g, ""), 10) || 0;
  const itemsPerPage = parseInt(getUrlParam(url, "_ipg", "60"), 10) || 60;
  let totalPages = Math.ceil(totalResults / itemsPerPage) || 1;
  if (maxPages && totalPages > maxPages) totalPages = maxPages;

  for (let i = 2; i <= totalPages; i++) {
    const pageUrl = updateUrlParam(url, { _pgn: i });
    const pageHtml = await fetchRenderedHtml(pageUrl, "ul.srp-results");
    try { results.push(...parseSearch(pageHtml)); } catch (_) {}
  }
  return results;
}
