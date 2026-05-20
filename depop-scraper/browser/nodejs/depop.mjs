// Depop scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 180;
const HOST = "https://www.depop.com";

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
    const session = await client().browser.create({ proxyCountry, sessionTTL: DEFAULT_SESSION_TTL });
    let browser;
    try {
      browser = await puppeteer.connect({ browserWSEndpoint: session.browserWSEndpoint });
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
                window.scrollBy(0, 600);
                y += 600;
                if (y >= document.body.scrollHeight) { clearInterval(i); r(); }
              }, 120);
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

// ---------------- helpers ----------------

function text$(node) {
  return (node?.text?.() || "").replace(/\s+/g, " ").trim() || null;
}

function abs(url) {
  if (!url) return null;
  if (url.startsWith("//")) return "https:" + url;
  if (url.startsWith("http")) return url;
  return HOST + (url.startsWith("/") ? url : "/" + url);
}

function uniq(arr) {
  return Array.from(new Set(arr.filter(Boolean)));
}

function toFloat(text) {
  if (!text) return null;
  const m = String(text).replace(/[^0-9.]/g, "");
  if (!m) return null;
  const n = parseFloat(m);
  return Number.isNaN(n) ? null : n;
}

function toInt(text) {
  if (!text) return null;
  // Support K / M suffixes (e.g. "12.3K followers").
  const s = String(text).replace(/[,\s]/g, "");
  let m = s.match(/(-?\d+(?:\.\d+)?)\s*([kKmM])\b/);
  if (m) {
    const n = parseFloat(m[1]);
    const mult = m[2].toLowerCase() === "k" ? 1000 : 1_000_000;
    return Number.isFinite(n) ? Math.round(n * mult) : null;
  }
  const digits = s.replace(/[^0-9-]/g, "");
  if (!digits) return null;
  const n = parseInt(digits, 10);
  return Number.isNaN(n) ? null : n;
}

function productSlugFromUrl(url) {
  if (!url) return "";
  const m = url.match(/\/products\/([^/?#]+)/);
  return m ? m[1] : "";
}

function sellerFromUrl(url) {
  if (!url) return null;
  const m = url.match(/\/products\/([^-]+)-/);
  return m ? m[1] : null;
}

// Extract Next.js page data from `<script id="__NEXT_DATA__">`.
function extractNextData($) {
  const raw = $("script#__NEXT_DATA__").text();
  if (!raw) return null;
  try { return JSON.parse(raw); } catch (_) { return null; }
}

// Depop's shop page is rendered through Next.js streaming (RSC), where the
// seller payload ships inside a doubly-encoded JSON chunk. Raw character form:
//   ...\"seller\":{\"username\":\"…\",\"verified\":false,…}...
// (i.e. each JSON quote is preceded by a literal backslash). We can't trivially
// brace-balance because the inner braces share the same string state with the
// outer JSON; instead we scan a generous window and read scalars per key.
// Regex source matching a literal `\"` (backslash + double-quote) in the HTML.
// Inside a JS string literal, `\\\\` is the 2-char escape for `\\`, and `\\"`
// is the 2-char escape for `\"` — together they form the 4-char regex source
// `\\\"`, which matches the 2 input characters `\"`.
const RSC_BS_Q = "\\\\\"";
function extractRscField(haystack, key) {
  const k = key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const prefix = `${RSC_BS_Q}${k}${RSC_BS_Q}:`;
  // Number / boolean / null
  let m = haystack.match(new RegExp(`${prefix}(true|false|null|-?\\d+(?:\\.\\d+)?)`));
  if (m) {
    const v = m[1];
    if (v === "true") return true;
    if (v === "false") return false;
    if (v === "null") return null;
    return v.includes(".") ? parseFloat(v) : parseInt(v, 10);
  }
  // String value: `\"…\"` where the inner chars never include `\"`.
  m = haystack.match(new RegExp(`${prefix}${RSC_BS_Q}((?:(?!${RSC_BS_Q}).)*)${RSC_BS_Q}`));
  if (m) return m[1];
  // Empty object literal
  if (new RegExp(`${prefix}\\{\\}`).test(haystack)) return {};
  return null;
}

function extractRscSeller(html) {
  // Find the rich seller object (carries `reviews_total`, `items_sold`, …).
  // The slimmer envelope (`{sellerId, followers, following, username}`) ships
  // first; we anchor on the trailing `items_sold` sentinel so we never confuse
  // the two — and we use a lazy `.{200,2000}?` because `picture:{}` puts an
  // early `}` inside the seller block, breaking any `[^}]` window.
  const re = new RegExp(
    `${RSC_BS_Q}seller${RSC_BS_Q}:\\{.{200,2000}?${RSC_BS_Q}items_sold${RSC_BS_Q}:[0-9]+`,
    "s"
  );
  const m = re.exec(html);
  return m ? m[0] : null;
}

// JSON-LD nodes (flat + @graph)
function jsonLdNodes($) {
  const out = [];
  $("script[type='application/ld+json']").each((_, el) => {
    const t = $(el).text();
    if (!t) return;
    try {
      const v = JSON.parse(t);
      const arr = Array.isArray(v) ? v : [v];
      for (const n of arr) {
        if (!n || typeof n !== "object") continue;
        if (Array.isArray(n["@graph"])) {
          for (const s of n["@graph"]) if (s && typeof s === "object") out.push(s);
        } else {
          out.push(n);
        }
      }
    } catch (_) {}
  });
  return out;
}

function typeMatches(node, wanted) {
  const t = node["@type"];
  if (typeof t === "string") return t === wanted;
  if (Array.isArray(t)) return t.includes(wanted);
  return false;
}

// ---------------- parsers ----------------

export function parseProduct(html, url) {
  const $ = cheerio.load(html);
  const nodes = jsonLdNodes($);
  const product = nodes.find((n) => typeMatches(n, "Product")) || {};

  const slug = productSlugFromUrl(url);

  const title =
    product.name ||
    text$($("h1").first()) ||
    $("meta[property='og:title']").attr("content") ||
    "";

  const offers = Array.isArray(product.offers) ? product.offers[0] : product.offers || {};
  const price = offers?.price != null ? String(offers.price) : null;
  const currency = offers?.priceCurrency || $("meta[itemprop='priceCurrency']").attr("content") || null;
  const availability =
    typeof offers?.availability === "string" ? offers.availability : null;
  const sold = !!availability && /OutOfStock|SoldOut/i.test(availability);

  const brand =
    (typeof product.brand === "object" ? product.brand?.name : product.brand) || null;
  const condition = product.itemCondition || null;
  const color = product.color || null;
  const size = product.size || null;
  const description =
    product.description ||
    $("meta[property='og:description']").attr("content") ||
    null;

  const seller =
    sellerFromUrl(url) ||
    text$($("a[href^='/'][class*='username'], [data-testid*='username']").first()) ||
    null;
  const sellerUrl = seller ? `${HOST}/${seller}/` : null;

  const ldImages = Array.isArray(product.image) ? product.image : product.image ? [product.image] : [];
  const images = uniq([
    ...ldImages,
    ...$("img[alt][src*='depop'], picture img, [class*='gallery'] img").map((_, e) => $(e).attr("src") || $(e).attr("data-src")).get(),
    ...$("meta[property='og:image']").map((_, e) => $(e).attr("content")).get(),
  ]).map((u) => (u && u.startsWith("//") ? "https:" + u : u)).filter(Boolean);

  const hashtags = uniq(
    $("a[href*='/search/?q=%23'], a[href*='/search/?q=#']").map((_, e) => text$($(e))).get(),
  );

  return {
    id: slug || "",
    url,
    title: title || "",
    price,
    currency,
    brand,
    condition,
    size,
    color,
    description,
    images,
    seller,
    sellerUrl,
    hashtags,
    sold,
  };
}

export function parseSearch(html) {
  const $ = cheerio.load(html);
  const out = [];
  const seen = new Set();

  $("a[href^='/products/']").each((_, el) => {
    const a = $(el);
    const href = a.attr("href") || "";
    const slug = productSlugFromUrl(href);
    if (!slug || seen.has(slug)) return;
    seen.add(slug);
    const img = a.find("img").first();
    // Cards: <li><a><img></a><p>price</p><p aria-label='Size'>S</p></li>.
    // We look both inside the <a> and at the closest list-item ancestor for sibling metadata.
    const card = a.closest("li, article, div[class*='styles__']");

    const title =
      img.attr("alt") ||
      text$(a.find("p[class*='styles__StyledProductCardTitle']").first()) ||
      text$(a) ||
      "";
    const image = img.attr("src") || img.attr("data-src") || null;

    const priceNode = card.find("p[aria-label='Price'], p[data-testid='product__priceAmount'], p[class*='Price']").first();
    const origNode = card.find("p[aria-label='Discounted price'], p[aria-label='original price'], s, del").first();
    const sizeNode = card.find("p[aria-label='Size'], [data-testid*='size']").first();

    const price = text$(priceNode) || null;
    const originalPrice = text$(origNode) || null;
    const seller = sellerFromUrl(href);
    const size = text$(sizeNode) || null;

    out.push({
      id: slug,
      title,
      url: abs(href),
      image,
      price,
      originalPrice,
      seller,
      size,
    });
  });
  return out;
}

export function parseShop(html, username) {
  const $ = cheerio.load(html);
  const next = extractNextData($);
  const page = next?.props?.pageProps || {};
  const profile = page?.user || page?.shop || {};

  // Pull the streaming RSC seller chunk as a secondary source — depop has
  // moved most data out of `__NEXT_DATA__` and into per-component RSC payloads.
  const rsc = extractRscSeller(html) || "";

  const rscFirstName = extractRscField(rsc, "first_name");
  const rscLastName = extractRscField(rsc, "last_name");
  const composed = [rscFirstName, rscLastName].filter((p) => p).join(" ").trim() || null;

  // Depop's shop name lives in `<p class="… styles_sellerName__…">`.
  const sellerNameDom = text$(
    $("p[class*='styles_sellerName']").first()
  );

  const displayName =
    profile?.displayName ||
    composed ||
    sellerNameDom ||
    text$($("h1").first()) ||
    username;

  const bio =
    profile?.bio ||
    extractRscField(rsc, "bio") ||
    text$($("p[data-testid='shop__bio'], div[class*='styles_shopBio'] p").first()) ||
    null;

  const avatar =
    profile?.profileImage ||
    profile?.avatar ||
    $("meta[property='og:image']").attr("content") ||
    null;

  const location =
    profile?.location ||
    extractRscField(rsc, "location") ||
    text$($("[data-testid*='location']").first()) ||
    null;

  let followers = toInt(profile?.followers);
  if (followers == null) followers = toInt(text$($("a[href*='/followers/'] span, a[href*='/followers/']").first()));
  if (followers == null) followers = extractRscField(rsc, "followers");

  let following = toInt(profile?.following);
  if (following == null) following = toInt(text$($("a[href*='/following/'] span, a[href*='/following/']").first()));
  if (following == null) following = extractRscField(rsc, "following");

  let rating = toFloat(profile?.rating);
  if (rating == null) rating = toFloat(text$($("[data-testid*='rating']").first()));
  if (rating == null) rating = extractRscField(rsc, "reviews_rating");

  let reviews = toInt(profile?.reviewsCount);
  if (reviews == null) reviews = toInt(text$($("a[href*='/reviews']").first()));
  if (reviews == null) reviews = extractRscField(rsc, "reviews_total");

  const listings = parseSearch(html);

  return {
    username,
    url: `${HOST}/${username}/`,
    displayName,
    bio,
    avatar,
    location,
    followers,
    following,
    reviews,
    rating,
    listings,
  };
}

// ---------------- scrape functions ----------------

export async function scrapeProduct(productUrl) {
  const html = await fetchRenderedHtml(productUrl, "h1, script#__NEXT_DATA__", { autoScroll: true });
  return parseProduct(html, productUrl);
}

export async function scrapeSearch(query, maxPages = 1) {
  const out = [];
  for (let page = 1; page <= maxPages; page++) {
    const url = `${HOST}/search/?q=${encodeURIComponent(query)}${page > 1 ? `&page=${page}` : ""}`;
    const html = await fetchRenderedHtml(url, "a[href^='/products/']", { autoScroll: true });
    out.push(...parseSearch(html));
  }
  return out;
}

export async function scrapeShop(username) {
  const url = `${HOST}/${username}/`;
  const html = await fetchRenderedHtml(url, "h1, script#__NEXT_DATA__", { autoScroll: true });
  return parseShop(html, username);
}
