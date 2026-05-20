// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import {
  scrapeSitemaps,
  scrapeTrendings,
  scrapeWebsite,
  scrapeWebsiteCompare,
} from "./similarweb.mjs";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const SAMPLE_DOMAIN = process.env.SIMILARWEB_SAMPLE_DOMAIN ?? "google.com";

const WebsiteSchema = z.object({
  overview: z.record(z.any()),
}).passthrough();

const TrendingSchema = z.object({
  name: z.string(),
  url: z.string().min(1),
  list: z.array(z.any()),
}).passthrough();

test("website schema", async () => {
  const results = await scrapeWebsite([SAMPLE_DOMAIN]);
  assert.equal(results.length, 1);
  WebsiteSchema.parse(results[0]);
});

test("website_compare schema", async () => {
  const result = await scrapeWebsiteCompare("google.com", "youtube.com");
  assert.ok("google.com" in result && "youtube.com" in result);
});

test("sitemaps schema", async () => {
  const urls = await scrapeSitemaps("https://www.similarweb.com/sitemaps/top-websites/top-websites-001.xml.gz");
  assert.ok(Array.isArray(urls) && urls.length >= 1);
  for (const u of urls) assert.equal(typeof u, "string");
});

test("trendings schema", async () => {
  const url = "https://www.similarweb.com/top-websites/computers-electronics-and-technology/programming-and-developer-software/";
  const results = await scrapeTrendings([url]);
  assert.equal(results.length, 1);
  TrendingSchema.parse(results[0]);
});
