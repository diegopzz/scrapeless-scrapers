// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapePages, scrapeSearch } from "./yellowpages.mjs";

const QUERY = process.env.YELLOWPAGES_QUERY ?? "Plumber";
const LOCATION = process.env.YELLOWPAGES_LOCATION ?? "San Francisco, CA";
const URLS = (process.env.YELLOWPAGES_URLS
  ?? "https://www.yellowpages.com/san-francisco-ca/mip/abc-plumbing").split(",");

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const SearchSchema = z.object({
  data: z.array(z.any()),
  total_pages: z.number().nullable().optional(),
}).passthrough();

const PageSchema = z.object({
  name: z.string().min(1),
  categories: z.array(z.string()).optional(),
  rating: z.string().optional(),
  ratingCount: z.string().optional(),
  phone: z.string().optional(),
  website: z.string().optional(),
  address: z.string().optional(),
  workingHours: z.record(z.string()).optional(),
}).passthrough();

test("search schema", async () => {
  const pages = await scrapeSearch(QUERY, LOCATION, 1);
  assert.ok(pages.length >= 1);
  for (const p of pages) SearchSchema.parse(p);
});

test("pages schema", async () => {
  const pages = await scrapePages(URLS);
  assert.equal(pages.length, URLS.length);
  for (const p of pages) PageSchema.parse(p);
});
