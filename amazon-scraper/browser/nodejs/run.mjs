// Run the scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapeProduct, scrapeReviews, scrapeSearch } from "./amazon.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SAMPLE_SEARCH_URL = process.env.AMAZON_SAMPLE_SEARCH_URL ?? "https://www.amazon.com/s?k=kindle";
const SAMPLE_PRODUCT_URL = process.env.AMAZON_SAMPLE_PRODUCT_URL
  ?? "https://www.amazon.com/PlayStation-5-Console-CFI-1215A01X/dp/B0BCNKKZ91/";

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

console.error(`== search ${SAMPLE_SEARCH_URL} ==`);
saveOrPrint("search", await scrapeSearch(SAMPLE_SEARCH_URL, 2));

console.error(`== product ${SAMPLE_PRODUCT_URL} ==`);
saveOrPrint("product", await scrapeProduct(SAMPLE_PRODUCT_URL));

console.error(`== reviews ${SAMPLE_PRODUCT_URL} ==`);
saveOrPrint("reviews", await scrapeReviews(SAMPLE_PRODUCT_URL));
