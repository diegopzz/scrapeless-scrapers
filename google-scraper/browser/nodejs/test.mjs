// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeGoogleMapPlaces, scrapeKeywords, scrapeSerp } from "./google.mjs";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const SAMPLE_QUERY = process.env.GOOGLE_SAMPLE_QUERY ?? "the upstream reference blog web scraping";
const SAMPLE_KEYWORD_QUERY = process.env.GOOGLE_SAMPLE_QUERY ?? "web scraping emails";
const SAMPLE_PLACE_URL = process.env.GOOGLE_SAMPLE_PLACE_URL ??
  "https://www.google.com/maps/place/Mus%C3%A9e+d%27Orsay/data=!4m7!3m6!1s0x47e66e2bb630941b:0xd071bd8cb14423d8!8m2!3d48.8599614!4d2.3265614!16zL20vMGYzYjk!19sChIJG5Qwtitu5kcR2CNEsYy9cdA";

const SerpSchema = z.object({
  position: z.number().int().min(1),
  title: z.string().min(1),
  url: z.string().min(1),
  origin: z.string(),
  domain: z.string(),
  description: z.string(),
  date: z.string(),
}).passthrough();

const KeywordsSchema = z.object({
  related_search: z.array(z.string()),
  people_ask_for: z.array(z.string()),
}).passthrough();

const PlaceSchema = z.object({
  name: z.string().min(1),
  category: z.string(),
  address: z.string(),
  website: z.string(),
  phone: z.string(),
  review_count: z.string(),
  stars: z.string(),
  "5_stars": z.string(),
  "4_stars": z.string(),
  "3_stars": z.string(),
  "2_stars": z.string(),
  "1_stars": z.string(),
}).passthrough();

test("serp schema", async () => {
  const results = await scrapeSerp(SAMPLE_QUERY, 1);
  assert.ok(results.length >= 1, `expected >=1 SERP results, got ${results.length}`);
  for (const r of results) SerpSchema.parse(r);
});

test("keywords schema", async () => {
  const result = await scrapeKeywords(SAMPLE_KEYWORD_QUERY);
  KeywordsSchema.parse(result);
});

test("google_map_places schema", async () => {
  const results = await scrapeGoogleMapPlaces([SAMPLE_PLACE_URL]);
  assert.equal(results.length, 1);
  PlaceSchema.parse(results[0]);
});
