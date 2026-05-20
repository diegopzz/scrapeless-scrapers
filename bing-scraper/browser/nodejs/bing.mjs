// Bing scraper using @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Mirrors  —
// function names and emitted field names match verbatim.

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
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
      try {
        await page.waitForSelector(readySelector, { timeout: 15000 });
      } catch (_) {}
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

function domainOf(url) {
  try {
    let host = new URL(url).hostname || "";
    if (host.startsWith("www.")) host = host.slice(4);
    return host;
  } catch {
    return "";
  }
}

// ---------------- scrape functions ----------------

export async function scrapeSearch(query, maxPages = 1) {
  const pages = maxPages ?? 1;
  const out = [];
  let position = 0;
  for (let p = 0; p < pages; p++) {
    const first = p * 10 + 1;
    const url = `https://www.bing.com/search?q=${encodeURIComponent(query)}&first=${first}`;
    const html = await fetchRenderedHtml(url, "li.b_algo");
    for (const item of parseSearch(html)) {
      position += 1;
      item.position = position;
      out.push(item);
    }
  }
  return out;
}

export async function scrapeKeywords(query) {
  // Bing's classic SERP `li.b_ans` related-searches block has been replaced
  // by Copilot in 2024. The autosuggest endpoint (which still powers the
  // homepage search box) returns the same related-keyword list as a snippet
  // of escaped HTML, which we unescape + parse for the `query` attribute.
  const url = `https://www.bing.com/AS/Suggestions?qry=${encodeURIComponent(query)}&cvid=test&cp=${query.length}&msbqf=false&cc=us&FORM=BESBTB`;
  const html = await fetchRenderedHtml(url, "pre");
  return parseKeywords(html);
}

// ---------------- parsers ----------------

export function parseSearch(html) {
  const $ = cheerio.load(html);
  const out = [];
  $("li.b_algo").each((_, el) => {
    const card = $(el);
    const url = card.find("h2 a").first().attr("href") ?? "";
    const title = card.find("h2 a").first().text().trim();
    const origin = card.find("cite").first().text().trim();
    let description = card.find(".b_caption p").first().text().trim();
    let date = "";
    const m = description.match(/^(.*?)\s+[·—\-]\s+(.*)$/);
    if (m && m[1].length <= 40) {
      date = m[1].trim();
      description = m[2].trim();
    }
    out.push({
      position: 0,
      title,
      url,
      origin,
      domain: domainOf(url),
      description,
      date,
    });
  });
  return out;
}

export function parseKeywords(html) {
  // The autosuggest endpoint embeds escaped HTML inside a <pre> block.
  // Unescape it and read `li[query]` attributes. As a safety net we also try
  // the classic `li.b_ans` related-searches selector for older SERPs.
  let $ = cheerio.load(html);
  const seen = [];
  $("li.b_ans > div > ul > li").each((_, el) => {
    const v = $(el).text().trim();
    if (v && !seen.includes(v)) seen.push(v);
  });
  if (seen.length === 0) {
    const pre = $("pre").first().text() || $("body").text();
    if (pre) {
      const unescaped = pre
        .replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">")
        .replace(/&quot;/g, '"')
        .replace(/&amp;/g, "&");
      const $$ = cheerio.load(unescaped);
      $$("li[query]").each((_, el) => {
        const q = $$(el).attr("query");
        if (q && !seen.includes(q)) seen.push(q);
      });
    }
  }
  return seen;
}
