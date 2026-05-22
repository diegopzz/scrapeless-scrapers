// Google Jobs scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Google renders a Jobs panel inside the standard SERP when a job-related query is
// made. The panel data is embedded in the rendered HTML card text — no special
// ibp=htl;jobs endpoint is needed. We wait for networkidle, then parse the visible
// card text from "Job postings" heading to the "more jobs" sentinel.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 180;
const GOOGLE_SEARCH_BASE = "https://www.google.com/search";

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function newClient() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function fetchRenderedHtml(url, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 2 } = {}) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const { browserWSEndpoint } = await newClient().browser.create({
      proxyCountry,
      sessionTTL: DEFAULT_SESSION_TTL,
    });
    let browser;
    try {
      browser = await puppeteer.connect({ browserWSEndpoint });
      const page = await browser.newPage();
      await page.setViewport({ width: 1366, height: 900 });
      await page.goto(url, { waitUntil: "networkidle2", timeout: 60000 });
      const html = await page.content();
      if (html && html.length > 5000) return html;
      lastError = new Error(`short HTML len=${html?.length}`);
    } catch (e) {
      lastError = e;
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
  }
  throw new Error(`giving up after ${retries + 1} attempts: ${lastError?.message}`);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const TIME_RE = /^\d+\s+(?:second|minute|hour|day|week|month)s?\s+ago$/i;
const SALARY_RE = /^\$[\d,]+|^\d+[–\-]\d+\s+an?\s+(?:hour|year)|^\d[\d,]*\s*(?:a|per)\s+(?:hour|year)/i;
const LOCATION_VIA_RE = /^.+,\s+[A-Z]{2}\s+•\s+via\s+/;
const JOB_TYPE_RE = /^(?:Full-time|Part-time|Contractor|Internship|Temporary)/i;
const SKIP_LINES = new Set(["Saved jobs", "Following", "Feedback", "Learn more", "Follow", "Search Results"]);

export function parseJobs(html) {
  const $ = cheerio.load(html);
  const lines = [];
  $("body *").contents().filter((_, node) => node.type === "text").each((_, node) => {
    const text = (node.data ?? "").trim();
    if (text) lines.push(text);
  });

  const results = [];
  let inJobs = false;
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    if (line === "Job postings") { inJobs = true; i++; continue; }
    if (!inJobs) { i++; continue; }
    if (line === "More jobs" || line === "Web results" || /\d+\+?\s+more jobs/.test(line)) break;
    if (SKIP_LINES.has(line) || TIME_RE.test(line) || SALARY_RE.test(line) || JOB_TYPE_RE.test(line)) { i++; continue; }

    if (line.length > 5 && !LOCATION_VIA_RE.test(line) && !line.startsWith("No degree")) {
      const title = line;
      let company = "", location = "", source = "", postedAt = "", salary = "", jobType = "";
      let j = i + 1;

      while (j < lines.length && j < i + 10) {
        const nxt = lines[j];
        if (TIME_RE.test(nxt)) { postedAt = nxt; j++; continue; }
        if (SALARY_RE.test(nxt)) { salary = nxt; j++; continue; }
        if (JOB_TYPE_RE.test(nxt)) { jobType = nxt; j++; continue; }
        if (nxt.startsWith("No degree")) { j++; continue; }
        if (LOCATION_VIA_RE.test(nxt)) {
          const parts = nxt.split(" • via ");
          location = parts[0].trim();
          source = parts[1]?.trim() ?? "";
          j++; continue;
        }
        if (!company && nxt && nxt !== title && !SKIP_LINES.has(nxt)) { company = nxt; j++; continue; }
        break;
      }

      if (company && (postedAt || location)) {
        results.push({
          title, company,
          location: location || null,
          source: source || null,
          posted_at: postedAt || null,
          salary: salary || null,
          job_type: jobType || null,
          url: null,
        });
        i = j;
        continue;
      }
    }
    i++;
  }
  return results;
}

export async function scrapeJobs(query, { proxyCountry = DEFAULT_PROXY_COUNTRY } = {}) {
  const url = `${GOOGLE_SEARCH_BASE}?q=${encodeURIComponent(query)}&gl=us&hl=en`;
  const html = await fetchRenderedHtml(url, { proxyCountry });
  return parseJobs(html);
}
