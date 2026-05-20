// Indeed scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
//
// Indeed embeds two JSON blobs in every page:
//   - Search: window.mosaic.providerData["mosaic-provider-jobcards"]
//   - Job:    _initialData={...};
// Both are extracted with regex and surfaced with unchanged top-level keys.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 180;

const SEARCH_JSON_RE = /window\.mosaic\.providerData\["mosaic-provider-jobcards"\]=(\{.+?\});/s;
const JOB_JSON_RE = /_initialData=(\{.+?\});/s;

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

function looksAuthWalled(html, finalUrl) {
  if (!html) return true;
  if (typeof finalUrl === "string" && /secure\.indeed\.com\/auth/.test(finalUrl)) return true;
  if (/Sign In \| Indeed Accounts/i.test(html)) return true;
  if (/Just a moment/i.test(html) && html.length < 90000) return true;
  return false;
}

async function fetchRenderedHtml(url, readySelector, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 2, warmup = true } = {}) {
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
      // Warmup: hit indeed.com first so Cloudflare cookies attach to this
      // session before we open the deeper URL. Without this, /viewjob bounces
      // straight to secure.indeed.com/auth?from=bot-detection-anonymous.
      if (warmup) {
        try {
          await page.goto("https://www.indeed.com/", { waitUntil: "domcontentloaded", timeout: 30000 });
          // Let Cloudflare's challenge complete if there is one.
          for (let i = 0; i < 6; i++) {
            await new Promise((r) => setTimeout(r, 2000));
            const h = await page.content();
            if (h && !h.includes("Just a moment") && h.length > 30000) break;
          }
        } catch (_) {}
      }
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
      // Wait for either the ready selector or the Cloudflare challenge to clear.
      let html = "";
      for (let i = 0; i < 6; i++) {
        if (readySelector) {
          try { await page.waitForSelector(readySelector, { timeout: 5000 }); break; } catch (_) {}
        }
        await new Promise((r) => setTimeout(r, 2000));
        html = await page.content();
        if (html && !html.includes("Just a moment")) break;
      }
      const finalUrl = await page.url();
      if (!html) html = await page.content();
      if (html && !looksAuthWalled(html, finalUrl)) return html;
      lastError = new Error(looksAuthWalled(html, finalUrl) ? `auth-wall (final=${finalUrl.slice(0, 60)})` : "empty HTML");
    } catch (e) {
      lastError = e;
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
  }
  throw new Error(`giving up after ${retries + 1} attempts: ${lastError?.message}`);
}

function addUrlParameter(url, params) {
  const u = new URL(url);
  for (const [k, v] of Object.entries(params)) u.searchParams.set(k, String(v));
  return u.toString();
}

// ---------------- parsers (verbatim shape) ----------------

export function parseSearchPage(html) {
  const m = html.match(SEARCH_JSON_RE);
  if (!m) return { results: [], meta: [] };
  const data = JSON.parse(m[1]);
  const model = data?.metaData?.mosaicProviderJobCardsModel ?? {};
  return {
    results: model.results ?? [],
    meta: model.tierSummaries ?? [],
  };
}

export function parseJobPage(html) {
  // Indeed serves the job blob via several regex shapes — try each in turn.
  let raw = null;
  for (const re of [
    JOB_JSON_RE,
    /window\._initialData\s*=\s*(\{[\s\S]+?\});/,
    /_initialData\s*=\s*JSON\.parse\("(.+?)"\);/,
  ]) {
    const m = html.match(re);
    if (m) { raw = m[1]; break; }
  }
  if (!raw) return {};
  let data;
  try {
    // Handle the JSON.parse-escaped variant.
    if (raw.startsWith("{")) data = JSON.parse(raw);
    else data = JSON.parse(JSON.parse('"' + raw + '"'));
  } catch (_) {
    return {};
  }
  const job = {};
  try {
    job.description = data.jobInfoWrapperModel.jobInfoModel.sanitizedJobDescription;
  } catch (_) {
    job.description = "";
  }
  for (const k of ["jobMetadataHeaderModel", "jobTagModel", "jobInfoHeaderModel"]) {
    const sub = data?.[k];
    if (sub && typeof sub === "object") Object.assign(job, sub);
  }
  return job;
}

// ---------------- scrape functions (mirror the upstream reference's exports) ----------------

export async function scrapeSearch(url, maxResults = 1000) {
  const first = await fetchRenderedHtml(url, "#mosaic-provider-jobcards");
  const firstPage = parseSearchPage(first);
  const all = [...(firstPage.results ?? [])];
  let total = maxResults;
  try {
    total = Math.min(maxResults, Number(firstPage.meta?.[0]?.jobCount));
  } catch (_) {}
  if (!Number.isFinite(total)) total = maxResults;
  const others = [];
  for (let start = 10; start < total; start += 10) {
    others.push(addUrlParameter(url, { start }));
  }
  for (const pageUrl of others) {
    try {
      const html = await fetchRenderedHtml(pageUrl, "#mosaic-provider-jobcards");
      const parsed = parseSearchPage(html);
      all.push(...(parsed.results ?? []));
      if (all.length >= maxResults) break;
    } catch (_) {
      break;
    }
  }
  return all.slice(0, maxResults);
}

export async function scrapeJobs(jobKeys) {
  const out = [];
  for (const jk of jobKeys) {
    const url = `https://www.indeed.com/viewjob?jk=${jk}`;
    try {
      const html = await fetchRenderedHtml(url, "#jobDescriptionText");
      const parsed = parseJobPage(html);
      if (parsed && Object.keys(parsed).length) out.push(parsed);
    } catch (e) {
      // Indeed often locks /viewjob behind a bot-detection sign-in wall when
      // the proxy is fresh. Skip rather than poison the result file.
      console.warn(`skip jk=${jk}: ${e.message}`);
    }
  }
  return out;
}
