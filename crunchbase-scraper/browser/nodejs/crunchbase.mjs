// Crunchbase scraper using @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// Mirrors  —
// function names and emitted field names match verbatim.
//
// Crunchbase is an Angular app. State arrives as JSON inside `<script id="ng-state">`
// (newer pages) or `<script id="client-app-state">` (legacy). Both targets parse
// that embedded payload — the rendered DOM is unstable.

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
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
      try {
        await page.waitForSelector(readySelector, { timeout: 20000 });
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

// ---------------- Angular state extraction ----------------

function parseNgState(html) {
  const $ = cheerio.load(html);
  let raw = $("script#ng-state").first().text();
  if (!raw) raw = $("script#client-app-state").first().text();
  if (!raw) throw new Error("could not locate Angular state script (ng-state / client-app-state)");
  return JSON.parse(raw);
}

function walkHttpState(state, keySubstr) {
  const httpState = state?.HttpState ?? {};
  const matches = [];
  for (const [cacheKey, payload] of Object.entries(httpState)) {
    if (cacheKey.includes(keySubstr) && payload && typeof payload === "object") {
      const body = payload.body ?? payload.data ?? payload;
      if (body && typeof body === "object") matches.push(body);
    }
  }
  return matches;
}

// ---------------- Field reducers ----------------

const ORG_FIELDS = [
  "id", "name", "logo", "description", "linkedin", "facebook", "twitter", "email",
  "phone", "website", "ipo_status", "rank_org_company", "semrush_global_rank",
  "semrush_visits_latest_month", "semrush_id", "categories", "legal_name",
  "operating_status", "last_funding_type", "founded_on", "location_groups",
  "trademarks", "trademark_popular_class", "patents", "patent_popular_category",
  "investments", "investors", "acquisitions", "contacts", "funding_total_usd",
  "stock_symbol", "exits", "similar_orgs", "current_positions", "investors_lead",
  "investments_lead", "funding_rounds", "event_appearances", "advisors",
  "buildwith_tech_used", "timeline", "events", "similar",
];

function reduceOrg(raw) {
  if (!raw || typeof raw !== "object") return {};
  const cards = (raw.cards && typeof raw.cards === "object") ? raw.cards : {};
  const flat = {};
  for (const section of Object.values(cards)) {
    if (section && typeof section === "object") Object.assign(flat, section);
  }
  const props = (raw.properties && typeof raw.properties === "object") ? raw.properties : {};
  Object.assign(flat, props);
  const out = {};
  for (const k of ORG_FIELDS) if (k in flat) out[k] = flat[k];
  return out;
}

function reduceEmployees(payload) {
  if (!payload || typeof payload !== "object") return [];
  const items = payload.entities ?? payload.items ?? [];
  if (!Array.isArray(items)) return [];
  return items
    .map((it) => {
      const props = it?.properties ?? it ?? {};
      return {
        name: props.name ?? ((props.first_name ?? "") + " " + (props.last_name ?? "")).trim(),
        linkedin: props.linkedin ?? props.linkedin_url ?? null,
        job_levels: props.job_levels ?? null,
        job_departments: props.job_departments ?? null,
      };
    })
    .filter((r) => r && (r.name || r.linkedin));
}

const PERSON_FIELDS = [
  "name", "title", "description", "type", "gender", "location_groups", "location",
  "current_jobs", "past_jobs", "linkedin", "twitter", "facebook",
  "current_advisor_jobs", "founded_orgs", "portfolio_orgs", "rank_principal_investor",
  "education", "timeline", "investments", "exits",
];

function reducePerson(raw) {
  if (!raw || typeof raw !== "object") return {};
  const cards = (raw.cards && typeof raw.cards === "object") ? raw.cards : {};
  const flat = {};
  for (const section of Object.values(cards)) {
    if (section && typeof section === "object") Object.assign(flat, section);
  }
  const props = (raw.properties && typeof raw.properties === "object") ? raw.properties : {};
  Object.assign(flat, props);
  const out = {};
  for (const k of PERSON_FIELDS) if (k in flat) out[k] = flat[k];
  return out;
}

// ---------------- scrape functions ----------------

export async function scrapeCompany(url) {
  const html = await fetchRenderedHtml(url, "script#ng-state, script#client-app-state");
  const state = parseNgState(html);
  const orgPayloads = walkHttpState(state, "entities/organizations/");
  const organization = orgPayloads.length ? reduceOrg(orgPayloads[0]) : {};
  const employeesPayloads = walkHttpState(state, "/data/searches/contacts");
  const employees = employeesPayloads.length ? reduceEmployees(employeesPayloads[0]) : [];
  return { organization, employees };
}

export async function scrapePerson(url) {
  const html = await fetchRenderedHtml(url, "script#ng-state, script#client-app-state");
  const state = parseNgState(html);
  const personPayloads = walkHttpState(state, "data/entities");
  return personPayloads.length ? reducePerson(personPayloads[0]) : {};
}
