// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeCollection, scrapeAsset } from "./opensea.mjs";

const SAMPLE_SLUG = process.env.OPENSEA_SAMPLE_SLUG ?? "boredapeyachtclub";
const SAMPLE_CHAIN = process.env.OPENSEA_SAMPLE_CHAIN ?? "ethereum";
const SAMPLE_CONTRACT = process.env.OPENSEA_SAMPLE_CONTRACT ?? "0xbc4ca0eda7647a8ab7c2061c2e118a18a936f13d";
const SAMPLE_TOKEN_ID = process.env.OPENSEA_SAMPLE_TOKEN_ID ?? "1";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const CollectionSchema = z.object({
  slug: z.string().min(1),
  name: z.string().min(1),
  description: z.string(),
  chain: z.string(),
  total_supply: z.number().int().nullable(),
  floor_price: z.number().nullable(),
  floor_currency: z.string(),
  floor_price_usd: z.number().nullable(),
  volume_native: z.number().nullable(),
  volume_usd: z.number().nullable(),
  image: z.string(),
  url: z.string().min(1),
}).passthrough();

const TraitSchema = z.object({
  trait_type: z.string(),
  value: z.string(),
}).passthrough();

const AssetSchema = z.object({
  chain: z.string().min(1),
  contract: z.string().min(1),
  token_id: z.string().min(1),
  name: z.string(),
  collection_slug: z.string(),
  collection_name: z.string(),
  owner: z.string(),
  owner_address: z.string(),
  rarity_rank: z.number().int().nullable(),
  image: z.string(),
  traits: z.array(TraitSchema),
  best_offer: z.number().nullable(),
  best_offer_currency: z.string(),
  url: z.string().min(1),
}).passthrough();

test("collection schema", async () => {
  const c = await scrapeCollection(SAMPLE_SLUG);
  CollectionSchema.parse(c);
  assert.equal(c.slug, SAMPLE_SLUG);
});

test("asset schema", async () => {
  const a = await scrapeAsset(SAMPLE_CHAIN, SAMPLE_CONTRACT, SAMPLE_TOKEN_ID);
  AssetSchema.parse(a);
  assert.equal(a.token_id, SAMPLE_TOKEN_ID);
});
