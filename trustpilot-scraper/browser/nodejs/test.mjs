// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeCompany, scrapeReviews, scrapeSearch } from "./trustpilot.mjs";

const SAMPLE_COMPANY_URL = process.env.TRUSTPILOT_SAMPLE_COMPANY_URL ?? "https://www.trustpilot.com/review/www.bhphotovideo.com";
const SAMPLE_SEARCH_URL = process.env.TRUSTPILOT_SAMPLE_SEARCH_URL ?? "https://www.trustpilot.com/categories/electronics_technology";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const CompanySchema = z.object({
  pageUrl: z.string().min(1),
  companyDetails: z.object({}).passthrough(),
  reviews: z.array(z.any()),
}).passthrough();

const SearchSchema = z.object({
  identifyingName: z.string().min(1),
  displayName: z.string().min(1),
}).passthrough();

const ReviewSchema = z.object({
  id: z.string().min(1),
  consumer: z.object({}).passthrough(),
  rating: z.number().int().min(1).max(5),
  dates: z.object({}).passthrough(),
}).passthrough();

test("company schema", async () => {
  const companies = await scrapeCompany([SAMPLE_COMPANY_URL]);
  assert.equal(companies.length, 1);
  CompanySchema.parse(companies[0]);
});

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_SEARCH_URL, 1);
  assert.ok(results.length >= 1, `expected >=1 results, got ${results.length}`);
  for (const r of results) SearchSchema.parse(r);
});

test("reviews schema", async () => {
  const reviews = await scrapeReviews(SAMPLE_COMPANY_URL, 1);
  assert.ok(reviews.length >= 1, `expected >=1 reviews, got ${reviews.length}`);
  for (const r of reviews) ReviewSchema.parse(r);
});
