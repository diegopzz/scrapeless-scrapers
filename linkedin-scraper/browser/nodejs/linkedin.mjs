// LinkedIn scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// the function names and emitted field names match verbatim.
//
// Public surfaces only: profiles, company pages (incl. /life), the unauthenticated
// jobs guest API, job pages, and Pulse articles. No authenticated scraping.

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
function client() { return new Scrapeless({ apiKey: requireKey() }); }

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
      if (readySelector) {
        try { await page.waitForSelector(readySelector, { timeout: 15000 }); } catch (_) {}
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

function readJsonLdGraph($) {
  const graph = [];
  $('script[type="application/ld+json"]').each((_, el) => {
    const raw = $(el).contents().text();
    try {
      const data = JSON.parse(raw);
      if (data && typeof data === "object") {
        if (Array.isArray(data)) graph.push(...data);
        else if (Array.isArray(data["@graph"])) graph.push(...data["@graph"]);
        else graph.push(data);
      }
    } catch (_) {}
  });
  return graph;
}
function findNode(graph, typeName) {
  return graph.find((n) => {
    const t = n["@type"];
    return t === typeName || (Array.isArray(t) && t.includes(typeName));
  });
}

// ---------------- parsers ----------------

export function parseProfile(html) {
  const $ = cheerio.load(html);
  const graph = readJsonLdGraph($);
  return {
    profile: findNode(graph, "Person") ?? {},
    posts: graph.filter((n) => {
      const t = n["@type"];
      return t === "Article" || (Array.isArray(t) && t.includes("Article"));
    }),
  };
}

export function parseCompany(html) {
  const $ = cheerio.load(html);
  const graph = readJsonLdGraph($);
  const org = findNode(graph, "Organization") ?? {};
  const out = {
    name: org.name ?? "",
    url: org.url ?? "",
    mainAddress: org.address ?? null,
    description: org.description ?? null,
    numberOfEmployees: org.numberOfEmployees ?? null,
    logo: org.logo ?? null,
  };
  $('[data-test-id*="about-us"] dl > div').each((_, row) => {
    const key = $(row).find("dt").text().trim();
    const val = $(row).find("dd").text().trim();
    if (key) out[key] = val;
  });

  const leaders = [];
  $('[data-test-id="leaders-at"] li').each((_, li) => {
    leaders.push({
      name: $(li).find("h3").first().text().trim(),
      linkedinProfileLink: $(li).find("a").first().attr("href") ?? "",
    });
  });
  if (leaders.length) out.leaders = leaders;

  const collect = (sel) => {
    const items = [];
    $(sel).each((_, li) => {
      items.push({
        name: $(li).find("h3").first().text().trim(),
        industry: $(li).find("p").eq(0).text().trim(),
        address: $(li).find("p").eq(1).text().trim(),
        linkeinUrl: $(li).find("a").first().attr("href") ?? "",
      });
    });
    return items;
  };
  const aff = collect('[data-test-id="affiliated-pages"] ul > li');
  const sim = collect('[data-test-id="similar-pages"] ul > li');
  if (aff.length) out.affiliatedPages = aff;
  if (sim.length) out.similarPages = sim;
  return out;
}

export function parseJobSearch(html) {
  const $ = cheerio.load(html);
  // LinkedIn's public jobs search renders one <li> per card under
  // ul.jobs-search__results-list with a div.base-search-card inside it. Older
  // layouts used section.results-list ul > li.
  let cards = $("ul.jobs-search__results-list > li").filter((_, li) => $(li).find("div.base-search-card, a.base-card__full-link, h3").length > 0);
  if (!cards.length) cards = $("section.results-list ul > li");
  if (!cards.length) cards = $("li.jobs-search-results__list-item, li.result-card");
  if (!cards.length) cards = $("div.base-search-card, div.job-search-card");
  const data = [];
  cards.each((_, li) => {
    const $li = $(li);
    const title = $li.find("h3.base-search-card__title, h3").first().text().trim();
    const company = $li.find("h4.base-search-card__subtitle a, h4.base-search-card__subtitle, h4").first().text().trim();
    if (!title && !company) return;
    data.push({
      title,
      company,
      address: $li.find(".job-search-card__location").first().text().trim(),
      timeAdded: $li.find("time").first().attr("datetime") ?? "",
      jobUrl: $li.find("a.base-card__full-link").first().attr("href")
        ?? $li.find("a").first().attr("href") ?? "",
      companyUrl: $li.find("h4 a").first().attr("href") ?? "",
    });
  });
  const totalText = $(".results-context-header__job-count").first().text();
  let total_results = null;
  if (totalText) {
    const digits = totalText.replace(/\D/g, "");
    if (digits) total_results = Number(digits);
  }
  return { data, total_results };
}

export function parseJobPage(html) {
  const $ = cheerio.load(html);
  const graph = readJsonLdGraph($);
  const payload = findNode(graph, "JobPosting") ?? {};
  const bullets = $("div.show-more ul > li")
    .map((_, li) => $(li).text().trim())
    .get()
    .filter(Boolean);
  if (bullets.length) payload.jobDescription = bullets;
  return payload;
}

export function parseArticlePage(html) {
  const $ = cheerio.load(html);
  const graph = readJsonLdGraph($);
  const payload = findNode(graph, "Article") ?? {};
  const parts = $('article div[data-test-id="article-content-blocks"] div p span')
    .map((_, el) => $(el).text().trim())
    .get()
    .filter(Boolean);
  if (parts.length) payload.articleBody = parts.join("\n");
  return payload;
}

// ---------------- scrape functions ----------------

export async function scrapeProfile(urls) {
  const out = [];
  for (const url of urls) {
    const html = await fetchRenderedHtml(url, 'script[type="application/ld+json"]');
    out.push(parseProfile(html));
  }
  return out;
}

export async function scrapeCompany(urls) {
  const out = [];
  for (const url of urls) {
    const html = await fetchRenderedHtml(url, 'script[type="application/ld+json"]');
    out.push(parseCompany(html));
  }
  return out;
}

export async function scrapeJobSearch(keyword, location, maxPages = null) {
  const first = `https://www.linkedin.com/jobs/search?keywords=${encodeURIComponent(keyword)}&location=${encodeURIComponent(location)}`;
  const firstHtml = await fetchRenderedHtml(first, "section.results-list, ul");
  const pages = [parseJobSearch(firstHtml)];
  const toFetch = maxPages ?? 1;
  for (let i = 1; i < toFetch; i++) {
    const start = i * 25;
    const url = `https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=${encodeURIComponent(keyword)}&location=${encodeURIComponent(location)}&start=${start}`;
    try {
      const html = await fetchRenderedHtml(url);
      pages.push(parseJobSearch(html));
    } catch (_) { break; }
  }
  return pages;
}

export async function scrapeJobs(urls) {
  const out = [];
  for (const url of urls) {
    const html = await fetchRenderedHtml(url, 'script[type="application/ld+json"]');
    out.push(parseJobPage(html));
  }
  return out;
}

export async function scrapeArticles(urls) {
  const out = [];
  for (const url of urls) {
    const html = await fetchRenderedHtml(url, 'script[type="application/ld+json"]');
    out.push(parseArticlePage(html));
  }
  return out;
}
