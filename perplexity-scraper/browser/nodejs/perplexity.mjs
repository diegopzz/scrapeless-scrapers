// Perplexity scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Perplexity gates its answer pages behind Cloudflare and renders the
// input as a Lexical contenteditable, not a `<textarea>`. The scraper:
//   1. Warms up on the homepage to clear the Cloudflare cookie challenge.
//   2. Focuses `[role='textbox']`, types the prompt, presses Enter.
//   3. Waits for the URL to settle on `/search/<uuid>` and the answer
//      prose to render.
//   4. Extracts the question (`<h1 class="group/query …">`), the answer
//      (`<div class="prose …">`), and outbound citation `<a href>` links.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 360;

const TRANSIENT_NET_ERRORS = [
  "ERR_TUNNEL_CONNECTION_FAILED",
  "ERR_CONNECTION_CLOSED",
  "ERR_CONNECTION_RESET",
  "ERR_CONNECTION_REFUSED",
  "ERR_TIMED_OUT",
  "ERR_NETWORK_CHANGED",
  "ERR_EMPTY_RESPONSE",
  "ERR_PROXY_CONNECTION_FAILED",
  "Navigation timeout",
  "net::",
];

function isTransientError(err) {
  const msg = String(err?.message ?? err ?? "");
  return TRANSIENT_NET_ERRORS.some((s) => msg.includes(s));
}

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function withSessionRetry(fn, { retries = 2, label = "perplexity" } = {}) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const { browserWSEndpoint } = await client().browser.create({
      proxyCountry: DEFAULT_PROXY_COUNTRY,
      sessionTTL: DEFAULT_SESSION_TTL,
    });
    let browser;
    try {
      browser = await puppeteer.connect({ browserWSEndpoint });
      const page = await browser.newPage();
      await page.setViewport({ width: 1366, height: 900 });
      return await fn(page, browser);
    } catch (e) {
      lastError = e;
      if (!isTransientError(e) && attempt > 0) throw e;
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
    if (attempt < retries) await new Promise((r) => setTimeout(r, 4000 + attempt * 3000));
  }
  throw new Error(`${label}: giving up after ${retries + 1} attempts: ${lastError?.message ?? lastError}`);
}

async function warmupPerplexity(page) {
  await page.goto("https://www.perplexity.ai/", { waitUntil: "domcontentloaded", timeout: 60000 });
  await new Promise((r) => setTimeout(r, 8000));
}

async function submitPrompt(page, prompt) {
  await page.waitForSelector("[role='textbox'], [contenteditable='true']", { timeout: 25000 });
  await page.click("[role='textbox'], [contenteditable='true']");
  await page.keyboard.type(prompt, { delay: 30 });
  await new Promise((r) => setTimeout(r, 800));
  await page.keyboard.press("Enter");
}

async function waitForAnswer(page, { timeoutMs = 60000 } = {}) {
  // 1. URL settles on `/search/<uuid>`.
  const urlDeadline = Date.now() + 20000;
  while (Date.now() < urlDeadline) {
    if (/\/search\/[0-9a-f-]{8,}/i.test(page.url())) break;
    await new Promise((r) => setTimeout(r, 500));
  }
  // 2. Answer prose renders. Bail once it stops growing for ~3s or after the cap.
  const start = Date.now();
  let lastLen = 0;
  let lastChange = Date.now();
  while (Date.now() - start < timeoutMs) {
    await new Promise((r) => setTimeout(r, 800));
    let len = 0;
    try {
      len = await page.evaluate(() => {
        const el = document.querySelector("div.prose");
        return el ? (el.innerText || "").length : 0;
      });
    } catch (_) {}
    if (len !== lastLen) {
      lastLen = len;
      lastChange = Date.now();
    } else if (lastLen > 50 && Date.now() - lastChange >= 3000) {
      return;
    }
  }
}

// ---------------- scrape functions ----------------

export async function scrapeSearch(prompt) {
  return withSessionRetry(async (page) => {
    await warmupPerplexity(page);
    await submitPrompt(page, prompt);
    await waitForAnswer(page);
    const html = await page.content();
    const finalUrl = page.url();
    return parseSearch(html, prompt, finalUrl);
  }, { label: "scrape_search" });
}

// ---------------- parser ----------------

export function parseSearch(html, prompt, finalUrl) {
  const $ = cheerio.load(html);

  // Question — rendered inside the very first `h1.group/query` heading.
  // Cheerio's CSS uses dot-class so `.group\\/query` would otherwise need
  // an escaped slash; fall back to an attribute-contains match.
  let queryText = $("h1[class*='group/query']").first().text().trim();
  if (!queryText) queryText = prompt;
  queryText = queryText.replace(/\s+/g, " ").trim();

  // Answer — the first `<div class="prose ...">` block contains the
  // streamed response. Newer Perplexity layouts may render the answer in a
  // sibling `<div class="prose dark:prose-invert ...">` — match on `prose`.
  const proseNode = $("div[class*='prose']").first();
  const answerText = proseNode.text().replace(/\s+/g, " ").trim();

  // Citations — every external `<a href="https?://...">` that isn't a
  // perplexity-internal link or one of the layout chrome links. Deduped on
  // href.
  const seen = new Set();
  const citations = [];
  $("a[href^='http']").each((_, el) => {
    const href = $(el).attr("href") || "";
    if (!href || seen.has(href)) return;
    if (/perplexity\.ai/.test(href)) return;
    if (/\.perplexity\.ai\//.test(href)) return;
    if (/cloudflare\.com|gstatic\.com|twitter\.com\/PerplexityAI/.test(href)) return;
    seen.add(href);
    const title = $(el).text().replace(/\s+/g, " ").trim();
    citations.push({
      url: href,
      domain: domainOf(href),
      title,
    });
  });

  return {
    query: queryText,
    url: finalUrl,
    answer_text: answerText,
    citations,
  };
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
