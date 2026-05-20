// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import {
  scrapePropertyForRent,
  scrapePropertyForSale,
  scrapeSearch,
} from "./redfin.mjs";

const DEFAULT_SEARCH_URL =
  "https://www.redfin.com/stingray/api/gis?al=1&include_nearby_homes=true" +
  "&market=seattle&num_homes=350&ord=redfin-recommended-asc&page_number=1" +
  "&poly=-122.54472%2047.44109%2C-122.11144%2047.44109%2C-122.11144%2047.78363" +
  "%2C-122.54472%2047.78363%2C-122.54472%2047.44109&sf=1,2,3,5,6,7&start=0" +
  "&status=1&uipt=1,2,3,4,5,6,7,8&v=8&zoomLevel=11";
const DEFAULT_SALE_URL = "https://www.redfin.com/WA/Seattle/506-E-Howell-St-98122/unit-W303/home/46456";
const DEFAULT_RENT_URL = "https://www.redfin.com/WA/Seattle/Onni-South-Lake-Union/apartment/147020546";

const SEARCH_URL = process.env.REDFIN_SEARCH_URL ?? DEFAULT_SEARCH_URL;
const SALE_URL = process.env.REDFIN_SALE_URL ?? DEFAULT_SALE_URL;
const RENT_URL = process.env.REDFIN_RENT_URL ?? DEFAULT_RENT_URL;

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const SearchResultSchema = z.object({
  propertyId: z.number(),
  url: z.string(),
}).passthrough();

const PropertyForSaleSchema = z.object({
  address: z.string(),
  description: z.string().nullable(),
  price: z.string().nullable(),
  estimatedMonthlyPrice: z.string().nullable(),
  propertyUrl: z.string(),
  attachments: z.array(z.any()),
  details: z.array(z.any()),
  features: z.record(z.any()),
}).passthrough();

test("search schema", async () => {
  const results = await scrapeSearch(SEARCH_URL);
  assert.ok(results.length >= 1);
  for (const r of results.slice(0, 5)) SearchResultSchema.parse(r);
});

test("property_for_sale schema", async () => {
  const results = await scrapePropertyForSale([SALE_URL]);
  assert.equal(results.length, 1);
  PropertyForSaleSchema.parse(results[0]);
});

test("property_for_rent schema", async () => {
  const results = await scrapePropertyForRent([RENT_URL]);
  for (const r of results) assert.equal(typeof r, "object");
});
