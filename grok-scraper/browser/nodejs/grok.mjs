// Grok scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Grok conversation sessions require login, but shared conversations at
// grok.com/share/<id> are publicly readable without authentication.
//
// Flow:
// - Mint a cloud browser session (CDP WS endpoint).
// - puppeteer-core connects, opens the grok.com/share/<id> URL.
// - The page renders user turns in [data-testid="user-message"] elements
//   and assistant turns in [data-testid="assistant-message"] elements.
// - parseShare() reads those elements and returns a SharedConversation.
//
// Public/shared content only.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 300;

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

async function withSessionRetry(fn, { retries = 2, label = "grok" } = {}) {
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
    if (attempt < retries) await new Promise((r) => setTimeout(r, 5000 * Math.pow(2, attempt)));
  }
  throw new Error(`${label}: giving up after ${retries + 1} attempts: ${lastError?.message ?? lastError}`);
}

// Strip the ?rid=... redirect token Grok appends to share URLs.
function cleanShareUrl(url) {
  try {
    const u = new URL(url);
    u.searchParams.delete("rid");
    return u.toString().replace(/\?$/, "");
  } catch {
    return url;
  }
}

// ---------------- parser ----------------

/**
 * Parse a Grok shared-conversation HTML page.
 *
 * Stable anchors (live-verified 2026-05-21):
 *   [data-testid="user-message"]      — each user turn
 *   [data-testid="assistant-message"] — each assistant turn
 *   <title>                           — "{topic} | Shared Grok Conversation"
 *
 * DOM order matches conversation order (user first, repeating).
 */
export function parseShare(html, finalUrl) {
  const $ = cheerio.load(html);

  const url = cleanShareUrl(finalUrl);
  const title = $("title").first().text().trim();

  const messages = [];

  // Walk all [data-testid] elements that match our turn markers.
  // cheerio preserves DOM order.
  $("[data-testid='user-message'], [data-testid='assistant-message']").each((_, el) => {
    const testid = $(el).attr("data-testid") || "";
    const text = $(el).text().replace(/\s+/g, " ").trim();
    if (!text) return;
    const role = testid === "user-message" ? "user" : "assistant";
    messages.push({ role, content: text });
  });

  return { url, title, messages };
}

// ---------------- scrape function ----------------

/**
 * Open a public Grok shared-conversation page and return its transcript.
 *
 * `url` must be a grok.com/share/<id> URL. The page renders the full
 * conversation without authentication.
 */
export async function scrapeShare(url) {
  return withSessionRetry(async (page) => {
    // Grok's Cloudflare layer sometimes aborts / times out the first navigation
    // even though the page is already rendered by the time goto throws.
    // Catch timeouts and proceed to read the live DOM via page.evaluate().
    try {
      await page.goto(url, { waitUntil: "load", timeout: 30000 });
    } catch (e) {
      if (!String(e?.message ?? e).includes("Timeout") && !isTransientError(e)) throw e;
    }

    // Extract from the live DOM — Grok's content is JS-rendered so
    // page.content() returns the static shell; evaluate() reads the live DOM.
    const raw = await page.evaluate(() => {
      const cleanUrl = (location.href || "").replace(/\?rid=[^&]+(&|$)/, "").replace(/\?$/, "");
      const title = document.title || "";
      const msgs = [];
      document
        .querySelectorAll("[data-testid='user-message'], [data-testid='assistant-message']")
        .forEach((el) => {
          const testid = el.getAttribute("data-testid") || "";
          const text = (el.textContent || "").replace(/\s+/g, " ").trim();
          if (!text) return;
          msgs.push({ role: testid === "user-message" ? "user" : "assistant", content: text });
        });
      return { url: cleanUrl, title, messages: msgs };
    });

    return raw;
  }, { label: "scrape_share" });
}
