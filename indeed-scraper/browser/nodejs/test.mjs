// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeJobs, scrapeSearch } from "./indeed.mjs";

const SAMPLE_URL = process.env.INDEED_SAMPLE_URL ?? "https://www.indeed.com/jobs?q=python&l=Texas";
const SAMPLE_JOB_KEYS = (process.env.INDEED_SAMPLE_JOB_KEYS ?? "fc5ec64fc4d62cea")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

// Indeed search items come from mosaicProviderJobCardsModel.results — passthrough.
const SearchResultSchema = z.object({
  jobkey: z.string().min(1),
}).passthrough();

const JobSchema = z.object({
  description: z.string().min(1),
}).passthrough();

test("search shape", async () => {
  const results = await scrapeSearch(SAMPLE_URL, 10);
  assert.ok(results.length >= 1, `expected >=1 results, got ${results.length}`);
  for (const r of results) SearchResultSchema.parse(r);
});

test("jobs shape", async () => {
  const jobs = await scrapeJobs(SAMPLE_JOB_KEYS);
  assert.equal(jobs.length, SAMPLE_JOB_KEYS.length);
  for (const j of jobs) JobSchema.parse(j);
});
