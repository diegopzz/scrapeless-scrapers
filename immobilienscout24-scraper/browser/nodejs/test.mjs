// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProperties, scrapeSearch } from "./immobilienscout24.mjs";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const PropertySchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string().nullable(),
  address: z.string().nullable(),
  propertyLlink: z.string(),
  propertySepcs: z.object({}).passthrough(),
  price: z.object({}).passthrough(),
  building: z.object({}).passthrough(),
  attachments: z.object({}).passthrough(),
  agencyName: z.string().nullable(),
  agencyAddress: z.string().nullable(),
}).passthrough();

const SAMPLE_PROPERTIES = ["https://www.immobilienscout24.de/expose/160519246"];
const SAMPLE_SEARCH = "https://www.immobilienscout24.de/Suche/de/bayern/muenchen/wohnung-mieten";

test("properties schema", async () => {
  const results = await scrapeProperties(SAMPLE_PROPERTIES);
  assert.ok(results.length >= 1);
  for (const r of results) PropertySchema.parse(r);
});

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_SEARCH, false, 1);
  assert.ok(results.length >= 1);
  for (const r of results) PropertySchema.parse(r);
});
