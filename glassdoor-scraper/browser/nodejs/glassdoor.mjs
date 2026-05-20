// Glassdoor scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// the function names and emitted field shapes match verbatim, so downstream code
// can import { Scrapeless } from "@scrapeless-ai/sdk";
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

async function fetchRendered(url, readySelector, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 1 } = {}) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const { browserWSEndpoint } = await client().browser.create({ proxyCountry, sessionTTL: DEFAULT_SESSION_TTL });
    let browser;
    try {
      browser = await puppeteer.connect({ browserWSEndpoint });
      const page = await browser.newPage();
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
      if (readySelector) {
        try { await page.waitForSelector(readySelector, { timeout: 15000 }); } catch (_) {}
      }
      const html = await page.content();
      const finalUrl = page.url();
      if (html) return { html, finalUrl };
      lastError = new Error("empty HTML");
    } catch (e) {
      lastError = e;
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
  }
  throw new Error(`giving up after ${retries + 1} attempts: ${lastError?.message}`);
}

async function fetchJson(url, { proxyCountry = DEFAULT_PROXY_COUNTRY } = {}) {
  const { browserWSEndpoint } = await client().browser.create({ proxyCountry, sessionTTL: DEFAULT_SESSION_TTL });
  let browser;
  try {
    browser = await puppeteer.connect({ browserWSEndpoint });
    const page = await browser.newPage();
    try { await page.goto("https://www.glassdoor.com/", { waitUntil: "domcontentloaded", timeout: 30000 }); } catch (_) {}
    return await page.evaluate(async (u) => {
      const r = await fetch(u, { credentials: "include" });
      return await r.text();
    }, url);
  } finally {
    try { await browser?.close(); } catch (_) {}
  }
}

async function postJson(url, body, { proxyCountry = DEFAULT_PROXY_COUNTRY } = {}) {
  const { browserWSEndpoint } = await client().browser.create({ proxyCountry, sessionTTL: DEFAULT_SESSION_TTL });
  let browser;
  try {
    browser = await puppeteer.connect({ browserWSEndpoint });
    const page = await browser.newPage();
    try { await page.goto("https://www.glassdoor.com/", { waitUntil: "domcontentloaded", timeout: 30000 }); } catch (_) {}
    return await page.evaluate(async ([u, b]) => {
      const r = await fetch(u, {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(b),
      });
      return await r.text();
    }, [url, body]);
  } finally {
    try { await browser?.close(); } catch (_) {}
  }
}

// ---------------- hidden Apollo data ----------------

export function findHiddenData(html, url = "") {
  const $ = cheerio.load(html);
  let data;
  const next = $("script#__NEXT_DATA__").first().contents().text();
  if (next) {
    try { data = JSON.parse(next).props.pageProps.apolloCache; } catch (_) { return null; }
  } else {
    const m = html.match(/apolloState":\s*({.+})};/);
    if (m) {
      try { data = JSON.parse(m[1]); } catch (_) { return null; }
    } else {
      return null;
    }
  }
  const resolveRefs = (node, root) => {
    if (Array.isArray(node)) return node.map((n) => resolveRefs(n, root));
    if (node && typeof node === "object") {
      if ("__ref" in node) return resolveRefs(root[node.__ref], root);
      const out = {};
      for (const [k, v] of Object.entries(node)) out[k] = resolveRefs(v, root);
      return out;
    }
    return node;
  };
  if (!data) return {};
  return resolveRefs(data.ROOT_QUERY ?? data, data);
}

// ---------------- jobs ----------------

export function parseJobs(html, url) {
  const $ = cheerio.load(html);
  const jobData = [];
  $("div[class*='jobCard']").filter((_, el) => /JobCard/.test($(el).attr("class") || "")).each((_, box) => {
    const $b = $(box);
    jobData.push({
      jobTitle: $b.find("a").first().text() || null,
      jobLink: $b.find("a").first().attr("href") ?? null,
      job_location: $b.find("div[data-test='emp-location']").text() || null,
      jobSalary: $b.find("div[data-test='detailSalary']").text() || null,
      jobDate: $("div[data-test='job-age']").first().text() || null,
    });
  });

  const scriptData = $("script").filter((_, s) => $(s).text().includes("paginationLinks")).first().text();
  const otherPages = [];
  if (scriptData) {
    const m = scriptData.match(/\\"paginationLinks\\":\s*(\[.*?\])\s*,\s*\\"searchResultsMetadata\\"/);
    if (m) {
      try {
        const unescaped = m[1].replace(/\\"/g, '"').replace(/\\u0026/g, "&");
        const links = JSON.parse(unescaped);
        for (const p of links) {
          if (!p.isCurrentPage) otherPages.push(new URL(p.urlLink, url).toString());
        }
      } catch (_) {}
    }
  }
  return [jobData, otherPages];
}

export async function scrapeJobs(url, maxPages = null) {
  const { html, finalUrl } = await fetchRendered(url, "div[class*='jobCard']");
  let [jobs, otherPageUrls] = parseJobs(html, finalUrl);
  const totalPages = otherPageUrls.length + 1;
  if (maxPages && totalPages > maxPages) otherPageUrls = otherPageUrls.slice(0, maxPages - 1);
  for (const pageUrl of otherPageUrls) {
    try {
      const { html: html2, finalUrl: f2 } = await fetchRendered(pageUrl, "div[class*='jobCard']");
      const [more] = parseJobs(html2, f2);
      jobs.push(...more);
    } catch (_) {}
  }
  return jobs;
}

// ---------------- reviews ----------------

export function parseReviewsApiMetadata(html) {
  const $ = cheerio.load(html);
  const scriptData = $("script").filter((_, s) => $(s).text().includes("profileId")).first().text();
  if (!scriptData) throw new Error("reviews api metadata not found on page");
  const employerMatch = scriptData.match(/"employer"\s*:\s*(\{[^}]+\})/);
  if (!employerMatch) throw new Error("could not parse employer metadata");
  const employer = JSON.parse(employerMatch[1]);
  return { employer_id: parseInt(employer.id, 10), dynamic_profile_id: parseInt(employer.profileId, 10) };
}

export async function scrapeReviews(url, maxPages = null) {
  const { html } = await fetchRendered(url, "script");
  const metadata = parseReviewsApiMetadata(html);
  const apiUrl = "https://www.glassdoor.com/bff/employer-profile-mono/employer-reviews";
  const body = (page) => ({
    applyDefaultCriteria: true,
    employerId: metadata.employer_id,
    employmentStatuses: ["REGULAR", "PART_TIME"],
    jobTitle: null,
    goc: null,
    location: {},
    defaultLanguage: "eng",
    language: "eng",
    mlHighlightSearch: null,
    onlyCurrentEmployees: false,
    overallRating: null,
    pageSize: 5,
    page,
    preferredTldId: 0,
    reviewCategories: [],
    sort: "DATE",
    textSearch: "",
    worldwideFilter: false,
    dynamicProfileId: metadata.dynamic_profile_id,
    useRowProfileTldForRatings: true,
    enableKeywordSearch: true,
  });
  const firstText = await postJson(apiUrl, body(1));
  const first = JSON.parse(firstText);
  const reviewData = [...first.data.employerReviews.reviews];
  let totalPages = first.data.employerReviews.numberOfPages;
  if (maxPages && maxPages < totalPages) totalPages = maxPages;
  for (let page = 2; page <= totalPages; page++) {
    try {
      const text = await postJson(apiUrl, body(page));
      const pageData = JSON.parse(text);
      reviewData.push(...pageData.data.employerReviews.reviews);
    } catch (_) {}
  }
  return reviewData;
}

// ---------------- salaries ----------------

export function parseSalaries(html) {
  const $ = cheerio.load(html);
  const salaryData = { results: [], numPages: 1, salaryCount: 0, jobTitleCount: 0 };
  $("[data-test='salary-item']").each((_, el) => {
    const $i = $(el);
    const jobTitle = $i.find(".SalaryItem_jobTitle__XWGpT").text();
    if (!jobTitle) return;
    const salaryRange = $i.find(".SalaryItem_salaryRange__UL9vQ").text();
    const salaryCountText = $i.find(".SalaryItem_salaryCount__GT665").text() || "";
    let salaryCount = 0;
    if (salaryCountText.includes("Salaries submitted")) {
      const n = parseInt(salaryCountText.split(/\s+/)[0] || "0", 10);
      if (!Number.isNaN(n)) salaryCount = n;
    }
    const entry = { jobTitle: { text: jobTitle }, salaryCount, basePayStatistics: { percentiles: [] } };
    if (salaryRange) {
      const clean = salaryRange.replace(/\$/g, "").replace(/K/g, "000");
      if (clean.includes(" - ")) {
        const [a, b] = clean.split(" - ");
        const minVal = parseFloat(a.replace(/,/g, ""));
        const maxVal = parseFloat(b.replace(/,/g, ""));
        if (!Number.isNaN(minVal) && !Number.isNaN(maxVal)) {
          entry.basePayStatistics.percentiles = [
            { ident: "min", value: minVal },
            { ident: "max", value: maxVal },
          ];
        }
      }
    }
    salaryData.results.push(entry);
  });
  const pageLinks = $(".pagination_PageNumberText__F7427").map((_, p) => $(p).text()).get();
  if (pageLinks.length) {
    const nums = pageLinks.map((p) => parseInt(p, 10)).filter((n) => !Number.isNaN(n));
    if (nums.length) salaryData.numPages = Math.max(...nums);
  }
  const countText = $(".SortBar_SearchCount__cYwt6").text() || "";
  if (countText.includes("job titles")) {
    const n = parseInt((countText.split(/\s+/)[0] || "0").replace(/,/g, ""), 10);
    if (!Number.isNaN(n)) salaryData.jobTitleCount = n;
  }
  salaryData.salaryCount = salaryData.results.length;
  return salaryData;
}

export async function scrapeSalaries(url, maxPages = null) {
  const { html, finalUrl } = await fetchRendered(url, "[data-test='salary-item']");
  const salaries = parseSalaries(html);
  let totalPages = salaries.numPages;
  if (maxPages && totalPages > maxPages) totalPages = maxPages;
  for (let page = 2; page <= totalPages; page++) {
    const pageUrl = Url.changePage(finalUrl, page);
    try {
      const { html: html2 } = await fetchRendered(pageUrl, "[data-test='salary-item']");
      salaries.results.push(...parseSalaries(html2).results);
    } catch (_) {}
  }
  salaries.salaryCount = salaries.results.length;
  return salaries;
}

// ---------------- find companies ----------------

export async function findCompanies(query) {
  const url = `https://www.glassdoor.com/autocomplete/employers?term=${encodeURIComponent(query)}`;
  const text = await fetchJson(url);
  const data = JSON.parse(text);
  return data.map((r) => ({
    name: r.label,
    id: r.id,
    shortName: r.shortName ?? "",
    logoURL: r.logoURL ?? null,
    websiteURL: r.websiteURL ?? "",
  }));
}

// ---------------- URL helpers + Region enum ----------------

export const Region = Object.freeze({
  UNITED_STATES: "1",
  UNITED_KINGDOM: "2",
  CANADA_ENGLISH: "3",
  INDIA: "4",
  AUSTRALIA: "5",
  FRANCE: "6",
  GERMANY: "7",
  SPAIN: "8",
  BRAZIL: "9",
  NETHERLANDS: "10",
  AUSTRIA: "11",
  MEXICO: "12",
  ARGENTINA: "13",
  BELGIUM_NEDERLANDS: "14",
  BELGIUM_FRENCH: "15",
  SWITZERLAND_GERMAN: "16",
  SWITZERLAND_FRENCH: "17",
  IRELAND: "18",
  CANADA_FRENCH: "19",
  HONG_KONG: "20",
  NEW_ZEALAND: "21",
  SINGAPORE: "22",
  ITALY: "23",
});

export const Url = {
  overview(employer, employerId, region = null) {
    employer = employer.replace(/ /g, "-");
    let url = `https://www.glassdoor.com/Overview/Working-at-${employer}-EI_IE${employerId}`;
    const after = url.split("/Overview/")[1];
    const start = after.indexOf(employer);
    const end = start + employer.length;
    url += `.${start},${end}.htm`;
    if (region) url += `?filter.countryId=${region}`;
    return url;
  },
  reviews(employer, employerId, region = null) {
    employer = employer.replace(/ /g, "-");
    let url = `https://www.glassdoor.com/Reviews/${employer}-Reviews-E${employerId}.htm?`;
    if (region) url += `?filter.countryId=${region}`;
    return url;
  },
  salaries(employer, employerId, region = null) {
    employer = employer.replace(/ /g, "-");
    let url = `https://www.glassdoor.com/Salary/${employer}-Salaries-E${employerId}.htm?`;
    if (region) url += `?filter.countryId=${region}`;
    return url;
  },
  jobs(employer, employerId, region = null) {
    employer = employer.replace(/ /g, "-");
    let url = `https://www.glassdoor.com/Jobs/${employer}-Jobs-E${employerId}.htm?`;
    if (region) url += `?filter.countryId=${region}`;
    return url;
  },
  changePage(url, page) {
    let updated;
    if (/_P\d+\.htm/.test(url)) {
      updated = url.replace(/(?:_P\d+)*\.htm/, `_P${page}.htm`);
    } else {
      updated = url.replace(/\.htm/, `_P${page}.htm`);
    }
    if (updated === url) throw new Error("changePage did not modify URL");
    return updated;
  },
};
