// Run the scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapeProduct, scrapeSearch } from "./redbubble.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_PRODUCT_URLS = [
  "https://www.redbubble.com/i/sticker/Everything-s-good-cat-by-blah707/43977882/7sgk",
  "https://www.redbubble.com/i/sticker/Black-cat-by-Flora22/110162644/7sgk",
];
const DEFAULT_QUERY = "cat";

const SAMPLE_PRODUCT_URLS = process.env.REDBUBBLE_SAMPLE_PRODUCT_URLS
  ? process.env.REDBUBBLE_SAMPLE_PRODUCT_URLS.split(",").map((s) => s.trim())
  : DEFAULT_PRODUCT_URLS;
const SAMPLE_QUERY = process.env.REDBUBBLE_SAMPLE_QUERY ?? DEFAULT_QUERY;

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

console.error(`== product ${SAMPLE_PRODUCT_URLS.join(", ")} ==`);
saveOrPrint("product", await scrapeProduct(SAMPLE_PRODUCT_URLS));

console.error(`== search '${SAMPLE_QUERY}' ==`);
saveOrPrint("search", await scrapeSearch(SAMPLE_QUERY, 1));
