// GooglePlay scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Target surface: `https://play.google.com/store/apps/details?id=<package>`.
// The page embeds a `SoftwareApplication` JSON-LD blob with the cleanest
// representation of name/rating/description/icon. Install band, latest
// update, screenshots and categories come from the rendered DOM.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 180;
const READY_SELECTOR = "script[type='application/ld+json']";

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function fetchRenderedHtml(url, readySelector, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 1 } = {}) {
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
      await page.setViewport({ width: 1366, height: 900 });
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
      try { await page.waitForSelector(readySelector, { timeout: 15000 }); } catch (_) {}
      await new Promise((r) => setTimeout(r, 1500));
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

// ---------------- scrape functions ----------------

export async function scrapeApp(packageId) {
  const url = `https://play.google.com/store/apps/details?id=${encodeURIComponent(packageId)}&hl=en_US&gl=US`;
  const html = await fetchRenderedHtml(url, READY_SELECTOR);
  return parseApp(html, packageId, url);
}

export async function scrapeApps(packageIds) {
  const out = [];
  for (const id of packageIds) out.push(await scrapeApp(id));
  return out;
}

// ---------------- parser ----------------

export function parseApp(html, packageId, url) {
  const $ = cheerio.load(html);

  // Pick out the SoftwareApplication blob from one of the JSON-LD scripts.
  const ld = findSoftwareApplicationLd($);

  // Install band: rendered next to "Downloads"; look for an element whose
  // following sibling text is "Downloads", or fall back to a span containing
  // a `+` count.
  const installs = readInstallBand($);
  const latestUpdate = readLatestUpdate($);
  const categories = readCategories($, ld);
  const screenshots = readScreenshots($);

  return {
    id: packageId,
    name: (ld?.name ?? readMetaTitle($) ?? "").trim(),
    developer: (ld?.author?.name ?? ld?.author ?? readDeveloper($) ?? "").toString().trim(),
    rating: parseFloatOrNull(ld?.aggregateRating?.ratingValue),
    rating_count: parseIntOrNull(ld?.aggregateRating?.ratingCount ?? ld?.aggregateRating?.reviewCount),
    price: readPrice($, ld),
    installs,
    description: (ld?.description ?? readMetaDescription($) ?? "").trim(),
    categories,
    latest_update: latestUpdate,
    screenshots,
    icon: (ld?.image ?? ld?.logo ?? readIcon($) ?? "").toString().trim(),
    url,
  };
}

function findSoftwareApplicationLd($) {
  let found = null;
  $("script[type='application/ld+json']").each((_, el) => {
    if (found) return;
    const raw = $(el).contents().text().trim();
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw);
      const arr = Array.isArray(parsed) ? parsed : [parsed];
      for (const obj of arr) {
        const t = obj?.["@type"];
        if (typeof t === "string" && t.toLowerCase().includes("application")) { found = obj; return; }
        if (Array.isArray(t) && t.some((s) => String(s).toLowerCase().includes("application"))) { found = obj; return; }
      }
    } catch (_) {}
  });
  return found;
}

function readInstallBand($) {
  // Look for "Downloads" anywhere in the metric strip; the count is the
  // adjacent element. Modern layout: a wrapper div with two children where
  // the bottom one is "Downloads".
  let band = "";
  $("div, span").each((_, el) => {
    const txt = $(el).text().trim();
    if (txt === "Downloads") {
      const parent = $(el).parent();
      const sib = parent.children().first();
      const v = sib.text().trim();
      if (v && /[\d+]/.test(v)) { band = `${v} Downloads`; return false; }
    }
    return undefined;
  });
  if (band) return band;
  // Older "+" install band markup.
  const m = $("body").text().match(/(\d[\d,]*\+)\s+(downloads|installs)/i);
  return m ? `${m[1]} ${m[2]}` : "";
}

function readLatestUpdate($) {
  // "Updated on" or "Updated" label, value follows.
  let value = "";
  $("div, span").each((_, el) => {
    const txt = $(el).text().trim();
    if (/^Updated(?: on)?$/i.test(txt)) {
      const sib = $(el).next();
      const v = sib.text().trim();
      if (v) { value = v; return false; }
    }
    return undefined;
  });
  if (value) return value;
  // Try meta itemprop="datePublished".
  return $("[itemprop='datePublished']").attr("content") || "";
}

function readCategories($, ld) {
  const cats = new Set();
  const cat = ld?.applicationCategory;
  if (typeof cat === "string") cats.add(cat.trim());
  if (Array.isArray(cat)) for (const c of cat) cats.add(String(c).trim());
  // DOM fallback: category chips render as `<a>` whose href hits `/category/`.
  $("a[href*='/store/apps/category/']").each((_, el) => {
    const t = $(el).text().trim();
    if (t && !/^view all|see more/i.test(t)) cats.add(t);
  });
  return [...cats].filter(Boolean);
}

function readScreenshots($) {
  const seen = new Set();
  const out = [];
  $("img[src*='play-lh.googleusercontent.com']").each((_, el) => {
    const src = ($(el).attr("src") || "").split("=")[0];
    if (!src || seen.has(src)) return;
    seen.add(src);
    out.push(src);
  });
  // Drop the first (icon) and over-large hero asset duplicates; keep up to 20.
  return out.slice(1, 21);
}

function readPrice($, ld) {
  const offers = ld?.offers;
  const offerList = Array.isArray(offers) ? offers : (offers ? [offers] : []);
  for (const o of offerList) {
    if (!o) continue;
    if (o.price === "0" || o.price === 0 || o.price === "0.00") return "Free";
    if (o.price && o.priceCurrency) return `${o.priceCurrency} ${o.price}`;
    if (o.price) return String(o.price);
  }
  // DOM fallback: install button text.
  const btn = $("button[aria-label^='Install']").text().trim();
  return btn || "";
}

function readMetaTitle($) {
  return $("meta[property='og:title']").attr("content")
    || $("meta[name='twitter:title']").attr("content")
    || $("title").first().text().trim();
}

function readMetaDescription($) {
  return $("meta[name='description']").attr("content")
    || $("meta[property='og:description']").attr("content")
    || "";
}

function readIcon($) {
  return $("meta[property='og:image']").attr("content")
    || $("img[alt='Icon image']").attr("src")
    || "";
}

function readDeveloper($) {
  // Developer link sits under the app title with `/store/apps/dev?id=` or `/store/apps/developer?id=`.
  return $("a[href*='/store/apps/dev'], a[href*='/store/apps/developer']").first().text().trim() || "";
}

function parseFloatOrNull(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function parseIntOrNull(v) {
  const n = parseInt(String(v), 10);
  return Number.isFinite(n) ? n : null;
}
