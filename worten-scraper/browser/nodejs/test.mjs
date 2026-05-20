// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import { z } from "zod";
import { scrapeProduct, scrapeCategory } from "./worten.mjs";

const SAMPLE_PRODUCT_URL =
  process.env.WORTEN_SAMPLE_PRODUCT_URL ??
  "https://www.worten.pt/produtos/iphone-15-pro-max-apple-6-7-256-gb-titanio-branco-7851167";
const SAMPLE_CATEGORY_URL =
  process.env.WORTEN_SAMPLE_CATEGORY_URL ?? "https://www.worten.pt/promocoes/pequenos-eletrodomesticos";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const ProductSchema = z.object({
  sku: z.string().min(1),
  name: z.string().min(1),
  brand: z.string().nullable(),
  description: z.string().nullable(),
  image: z.string().nullable(),
  price: z.string().nullable(),
  priceCurrency: z.string().nullable(),
  availability: z.string().nullable(),
  ratingValue: z.number().nullable(),
  reviewCount: z.number().nullable(),
  url: z.string().min(1),
  breadcrumb: z.array(z.object({
    name: z.string().nullable(),
    url: z.string().nullable(),
    position: z.number().nullable(),
  })),
}).passthrough();

const CategorySchema = z.object({
  name: z.string().min(1),
  title: z.string().nullable(),
  description: z.string().nullable(),
  url: z.string().min(1),
  breadcrumb: z.array(z.object({
    name: z.string().nullable(),
    url: z.string().nullable(),
    position: z.number().nullable(),
  })),
}).passthrough();

test("product schema", async () => {
  const product = await scrapeProduct(SAMPLE_PRODUCT_URL);
  ProductSchema.parse(product);
});

test("category schema", async () => {
  const cat = await scrapeCategory(SAMPLE_CATEGORY_URL);
  CategorySchema.parse(cat);
});
