// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeCompanies, scrapeSearch } from "./wellfound.mjs";

const ROLE = process.env.WELLFOUND_ROLE ?? "engineer";
const LOCATION = process.env.WELLFOUND_LOCATION ?? "";
const COMPANY_URLS = (process.env.WELLFOUND_COMPANY_URLS ?? "https://wellfound.com/company/openai").split(",");

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const CompanySchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  slug: z.string().min(1),
  badges: z.array(z.any()).optional(),
  companySize: z.string().nullable().optional(),
  highConcept: z.string().nullable().optional(),
  logoUrl: z.string().nullable().optional(),
  highlightedJobListings: z.array(z.any()).optional(),
}).passthrough();

test("search schema", async () => {
  const results = await scrapeSearch(ROLE, LOCATION, 1);
  assert.ok(results.length >= 1, `expected >=1 results, got ${results.length}`);
  for (const c of results) CompanySchema.parse(c);
});

test("companies schema", async () => {
  const results = await scrapeCompanies(COMPANY_URLS);
  assert.ok(results.length >= 1);
  for (const c of results) CompanySchema.parse(c);
});
