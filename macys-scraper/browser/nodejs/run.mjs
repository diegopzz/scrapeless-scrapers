// Run the scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapeProduct, scrapeSearch } from "./macys.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_PRODUCT_URLS = [
  "https://www.macys.com/shop/product/levis-mens-541-athletic-fit-jean?ID=2061867",
  "https://www.macys.com/shop/product/calvin-klein-mens-slim-fit-stretch-jeans?ID=10068466",
];
const DEFAULT_CATEGORY_URL = "https://www.macys.com/shop/mens-clothing/mens-jeans?id=17979";

const SAMPLE_PRODUCT_URLS = process.env.MACYS_SAMPLE_PRODUCT_URLS
  ? process.env.MACYS_SAMPLE_PRODUCT_URLS.split(",").map((s) => s.trim())
  : DEFAULT_PRODUCT_URLS;
const SAMPLE_CATEGORY_URL = process.env.MACYS_SAMPLE_CATEGORY_URL ?? DEFAULT_CATEGORY_URL;

const HERE = path.dirname(fileURLToPath(import.meta.url));
const RESULTS_DIR = path.resolve(HERE, "results");

function saveOrPrint(name, payload) {
  const json = JSON.stringify(payload, null, 2);
  if ((process.env.SAVE_TEST_RESULTS ?? "").toLowerCase() === "true") {
    fs.mkdirSync(RESULTS_DIR, { recursive: true });
    const out = path.join(RESULTS_DIR, `${name}.json`);
    fs.writeFileSync(out, json, "utf-8");
    console.error(`wrote ${out}`);
  } else {
    console.log(json);
  }
}

async function safeRun(label, fn, fallback) {
  console.error(`== ${label} ==`);
  try {
    return await fn();
  } catch (e) {
    console.error(`!! ${label} failed: ${e.message}`);
    return fallback;
  }
}

const productResults = await safeRun(
  `product ${SAMPLE_PRODUCT_URLS.join(", ")}`,
  () => scrapeProduct(SAMPLE_PRODUCT_URLS),
  []
);
// Drop entries where the page returned but rendered no product DOM (Akamai pass-through).
const filteredProducts = productResults.filter((p) => p && (p.name || p.brand || p.price != null));
saveOrPrint("product", filteredProducts);

const searchResults = await safeRun(
  `search ${SAMPLE_CATEGORY_URL}`,
  () => scrapeSearch(SAMPLE_CATEGORY_URL, 1),
  []
);
saveOrPrint("search", searchResults);
