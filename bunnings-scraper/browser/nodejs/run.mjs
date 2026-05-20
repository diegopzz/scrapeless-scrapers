// Run the scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapeProduct, scrapeSearch } from "./bunnings.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_PRODUCT_URL =
  "https://www.bunnings.com.au/ozito-pxc-18v-cordless-drill-driver-kit-pxddk-250c_p0299323";
const DEFAULT_QUERY = "cordless drill";

const SAMPLE_PRODUCT_URL = process.env.BUNNINGS_SAMPLE_PRODUCT_URL ?? DEFAULT_PRODUCT_URL;
const SAMPLE_QUERY = process.env.BUNNINGS_SAMPLE_QUERY ?? DEFAULT_QUERY;
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

console.error(`== product ${SAMPLE_PRODUCT_URL} ==`);
saveOrPrint("product", await scrapeProduct(SAMPLE_PRODUCT_URL));

console.error(`== search '${SAMPLE_QUERY}' ==`);
saveOrPrint("search", await scrapeSearch(SAMPLE_QUERY, 1));
