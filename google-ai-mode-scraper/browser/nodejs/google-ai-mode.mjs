// GoogleAiMode scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Google's AI Mode is the streaming AI overlay reachable at
// `https://www.google.com/search?q=<query>&udm=50`. The scraper drives the
// SERP, waits for the AI panel to stream in, and extracts the answer text
// plus cited links.
//
// Flow:
// - `client.browser.create()` mints a cloud session (CDP WebSocket).
// - puppeteer-core connects, navigates to the SERP with `udm=50`.
// - Wait for the AI panel container, then settle for streamed content.
// - cheerio parses the rendered HTML into a single `AiResponse` object.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 240;
const AI_READY_SELECTOR = "div[data-subtree='aimc'], div[jsname][data-md], div[role='region']";

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function warmupGoogle(page) {
  // Land on the bare homepage so Google's NID/consent cookies are minted on
  // a less-defended endpoint before the AI Mode SERP. The first hop often
  // lands on /sorry/ without this.
  try {
    await page.goto("https://www.google.com/", { waitUntil: "domcontentloaded", timeout: 30000 });
    try { await page.click("button[aria-label*='Accept']", { timeout: 1500 }); } catch (_) {}
    try { await page.click("#L2AGLb", { timeout: 1500 }); } catch (_) {}
    await new Promise((r) => setTimeout(r, 1500));
  } catch (_) {}
}

function isCaptchaPage(page) {
  const url = page.url() || "";
  return url.includes("/sorry/") || url.includes("captcha");
}

async function fetchAiModeHtml(query, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 3 } = {}) {
  const url = `https://www.google.com/search?q=${encodeURIComponent(query)}&udm=50&hl=en`;
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
      await warmupGoogle(page);
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
      if (isCaptchaPage(page)) {
        lastError = new Error("captcha interstitial");
      } else {
        try { await page.waitForSelector(AI_READY_SELECTOR, { timeout: 20000 }); } catch (_) {}
        // Let the streamed AI answer settle. Google paints the AI panel
        // incrementally; bail once the DOM stops changing for 3 seconds or
        // after a hard ceiling.
        await settleForStreamedContent(page, { idleMs: 3000, ceilingMs: 30000 });
        if (isCaptchaPage(page)) {
          lastError = new Error("captcha interstitial");
        } else {
          const html = await page.content();
          if (html) return { html, finalUrl: page.url() };
          lastError = new Error("empty HTML");
        }
      }
    } catch (e) {
      lastError = e;
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
    if (attempt < retries) await new Promise((r) => setTimeout(r, 4000 + attempt * 3000));
  }
  throw new Error(`giving up after ${retries + 1} attempts: ${lastError?.message}`);
}

async function settleForStreamedContent(page, { idleMs, ceilingMs }) {
  const start = Date.now();
  let lastLen = 0;
  let lastChange = Date.now();
  while (Date.now() - start < ceilingMs) {
    await new Promise((r) => setTimeout(r, 500));
    let len = 0;
    try { len = await page.evaluate(() => document.body?.innerText?.length ?? 0); } catch (_) {}
    if (len !== lastLen) {
      lastLen = len;
      lastChange = Date.now();
    } else if (Date.now() - lastChange >= idleMs) {
      return;
    }
  }
}

// ---------------- scrape functions ----------------

export async function scrapeAiResponse(query) {
  const { html, finalUrl } = await fetchAiModeHtml(query);
  return parseAiResponse(html, query, finalUrl);
}

// ---------------- parser ----------------

export function parseAiResponse(html, query, finalUrl) {
  const $ = cheerio.load(html);

  // The AI panel renders inside one of a handful of containers. Try the
  // most specific selectors first, then fall back to the main content
  // column. We deliberately keep this defensive — Google rerolls AI Mode
  // markup frequently.
  const candidates = [
    "div[data-subtree='aimc']",
    "div[jsname][data-md]",
    "div[role='region'][aria-label]",
    "#main",
  ];
  let $panel = null;
  for (const sel of candidates) {
    const node = $(sel).filter((_, el) => $(el).text().trim().length > 80).first();
    if (node.length) { $panel = node; break; }
  }
  if (!$panel || !$panel.length) $panel = $("body");

  const responseText = normaliseText($panel.text());

  // Citations: chips/cards rendered with an outbound link + visible label.
  // Google decorates them with `aria-label` containing the source domain.
  const citations = [];
  const seenCite = new Set();
  $panel.find("a[href^='http']").each((_, a) => {
    const $a = $(a);
    const href = $a.attr("href") || "";
    if (!href || href.includes("google.com/search") || href.includes("/url?")) return;
    const aria = $a.attr("aria-label") || "";
    const text = normaliseText($a.text());
    // Citations show a domain badge — most have an `<img>` favicon descendant.
    const hasFavicon = $a.find("img").length > 0;
    if (!hasFavicon && !aria) return;
    const source = domainOf(href);
    const key = `${href}|${text}`;
    if (seenCite.has(key)) return;
    seenCite.add(key);
    citations.push({
      title: text || aria || source,
      url: href,
      source,
    });
  });

  // Generic outbound links (super-set of citations, deduped on href alone).
  const links = [];
  const seenLink = new Set();
  $panel.find("a[href^='http']").each((_, a) => {
    const $a = $(a);
    const href = $a.attr("href") || "";
    if (!href || href.includes("google.com/search") || href.includes("/url?")) return;
    if (seenLink.has(href)) return;
    seenLink.add(href);
    links.push({
      url: href,
      text: normaliseText($a.text()) || ($a.attr("aria-label") || ""),
    });
  });

  return {
    query,
    url: finalUrl || `https://www.google.com/search?q=${encodeURIComponent(query)}&udm=50`,
    response_text: responseText,
    citations,
    links,
  };
}

function normaliseText(s) {
  return String(s || "").replace(/\s+/g, " ").trim();
}

function domainOf(url) {
  try {
    let host = new URL(url).hostname || "";
    if (host.startsWith("www.")) host = host.slice(4);
    return host;
  } catch {
    return "";
  }
}
