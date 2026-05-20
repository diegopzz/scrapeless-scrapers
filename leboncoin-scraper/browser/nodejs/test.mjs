// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeAd, scrapeSearch } from "./leboncoin.mjs";

const SAMPLE_SEARCH =
  process.env.LEBONCOIN_SAMPLE_SEARCH ?? "https://www.leboncoin.fr/recherche?text=coffe";
const SAMPLE_AD =
  process.env.LEBONCOIN_SAMPLE_AD ??
  "https://www.leboncoin.fr/ad/ventes_immobilieres/2919253293";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const AdSchema = z.object({
  list_id: z.number(),
  subject: z.string().min(1),
  body: z.string().nullable().optional(),
  url: z.string(),
  category_id: z.any().nullable().optional(),
  category_name: z.any().nullable().optional(),
  price: z.any().nullable().optional(),
  images: z.any().nullable().optional(),
  attributes: z.any().nullable().optional(),
  location: z.any().nullable().optional(),
  owner: z.any().nullable().optional(),
}).passthrough();

const SearchAdSchema = z.object({
  list_id: z.number(),
  subject: z.string().min(1),
  url: z.string(),
  category_id: z.any().nullable().optional(),
  category_name: z.any().nullable().optional(),
  price: z.any().nullable().optional(),
}).passthrough();

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_SEARCH, false, 1);
  assert.ok(results.length >= 1, `expected >=1 results, got ${results.length}`);
  for (const r of results) SearchAdSchema.parse(r);
});

test("ad schema", async () => {
  const ad = await scrapeAd(SAMPLE_AD);
  assert.ok(ad, "expected ad payload, got null (DataDome block?)");
  AdSchema.parse(ad);
});
