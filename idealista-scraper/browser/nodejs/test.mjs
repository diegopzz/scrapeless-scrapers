// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProperties, scrapeProvinces, scrapeSearch } from "./idealista.mjs";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const PropertySchema = z.object({
  url: z.string().min(1),
  title: z.string(),
  location: z.string(),
  price: z.number().int(),
  currency: z.string(),
  description: z.string(),
  updated: z.string().optional(),
  features: z.record(z.array(z.string())),
  images: z.record(z.array(z.string())),
  plans: z.array(z.string()),
}).passthrough();

const SearchSchema = z.object({
  title: z.string(),
  link: z.string().min(1),
  picture: z.string().nullable(),
  price: z.number().int(),
  currency: z.string(),
  parking_included: z.boolean(),
  details: z.array(z.string()),
  description: z.string(),
  tags: z.array(z.string()),
  listing_company: z.string().nullable(),
  listing_company_url: z.string().nullable(),
}).passthrough();

const SAMPLE_PROPERTIES = ["https://www.idealista.com/en/inmueble/109061254/"];
const SAMPLE_SEARCH = "https://www.idealista.com/en/venta-viviendas/marbella-malaga/con-chalets/";
const SAMPLE_PROVINCES = ["https://www.idealista.com/venta-viviendas/almeria-provincia/municipios"];

test("properties schema", async () => {
  const results = await scrapeProperties(SAMPLE_PROPERTIES);
  assert.ok(results.length >= 1);
  for (const r of results) PropertySchema.parse(r);
});

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_SEARCH, 1);
  assert.ok(results.length >= 1);
  for (const r of results) SearchSchema.parse(r);
});

test("provinces schema", async () => {
  const urls = await scrapeProvinces(SAMPLE_PROVINCES);
  assert.ok(Array.isArray(urls));
  for (const u of urls) assert.equal(typeof u, "string");
});
